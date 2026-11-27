"""Sequential composite decoding and bounded versioned project archives."""
from pathlib import Path, PurePosixPath
import io
import json
import zipfile
import base64
from PIL import Image, ImageOps
from .document import Document, Frame
from .image import PhotonImage
from .frame_store import FrameStore, DEFAULT_IMPORT_BYTES
from .export import atomic_write, check_cancel, normalize_colour

MAX_FRAMES = 10000
MAX_MANIFEST_BYTES = 8 * 1024**2


def decode_document(path, cancel=None, progress=None, import_limit=DEFAULT_IMPORT_BYTES, cache_bytes=None, sequence_policy=None):
    if Path(path).suffix.lower() == '.photonanim':
        return load_project(path, cancel, import_limit)
    with Image.open(path) as image:
        fmt = image.format
        count = getattr(image, 'n_frames', 1)
        sequence = count > 1 and fmt not in ('GIF', 'WEBP')
        if sequence and sequence_policy not in ('first', 'separate'):
            raise ValueError(f'Multiframe {fmt} is not a supported animation; use explicit frame extraction')
        if sequence and sequence_policy == 'first':
            count = 1
        if count > MAX_FRAMES or image.width * image.height * count * 4 > import_limit:
            raise ValueError('Decoded image exceeds the configured import memory limit')
        store = FrameStore() if cache_bytes is None else FrameStore(cache_bytes)
        metadata = {k: image.info[k] for k in ('icc_profile', 'exif') if k in image.info}
        source_profile = metadata.get('icc_profile')
        raw_loop = image.info.get('loop')
        plays = 1 if raw_loop is None else (0 if raw_loop == 0 else raw_loop + 1 if fmt == 'GIF' else raw_loop)
        frames, notes = [], []
        for index in range(count):
            check_cancel(cancel)
            image.seek(index)
            # Pillow reconstructs disposal/offset/blend operations sequentially.
            image.load()
            normalized = ImageOps.exif_transpose(image)
            pixels, converted_profile = normalize_colour(normalized, source_profile)
            pixels = pixels.convert('RGBA')
            if converted_profile:
                metadata['icc_profile'] = converted_profile
            duration = int(image.info.get('duration', 0) or 0)
            if duration <= 0:
                duration = 100
                if count > 1:
                    notes.append(f'Frame {index+1}: missing/zero duration normalized to 100 ms')
            frames.append(Frame(PhotonImage(pixels, store, fmt), duration))
            if progress:
                progress(index+1, count)
        document = Document(frames, fmt, plays, count > 1 and not sequence, metadata, store=store, import_notes=notes)
        document.validate()
        return document


def save_project(path, document, overwrite=True, cancel=None):
    document.validate()
    def write(temporary):
        manifest = {'version': 1, 'canvas': list(document.canvas_size),
                    'source_format': document.source_format, 'total_plays': document.total_plays,
                    'animation': document.animation, 'frames': [],
                    'metadata': {key: base64.b64encode(value).decode('ascii') for key, value in document.metadata.items()
                                 if key in ('icc_profile', 'exif') and isinstance(value, bytes)}}
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_STORED) as archive:
            for index, frame in enumerate(document.frames):
                check_cancel(cancel)
                name = f'frames/{index:06d}.png'
                buffer = io.BytesIO()
                frame.image.current.save(buffer, format='PNG')
                archive.writestr(name, buffer.getvalue())
                manifest['frames'].append({'path': name, 'id': frame.id, 'duration_ms': frame.duration_ms, 'artwork': frame.artwork})
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
    return atomic_write(path, write, lambda p: load_project(p, cancel), overwrite, cancel)


def load_project(path, cancel=None, import_limit=DEFAULT_IMPORT_BYTES):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        if len(names) != len(set(names)) or len(names) > MAX_FRAMES + 1:
            raise ValueError('Invalid project archive entries')
        if sum(i.file_size for i in infos) > import_limit + MAX_MANIFEST_BYTES:
            raise ValueError('Project archive exceeds decompression limit')
        for name in names:
            parts = PurePosixPath(name)
            if parts.is_absolute() or '..' in parts.parts or '\\' in name or ':' in name:
                raise ValueError('Unsafe project archive path')
        info = archive.getinfo('manifest.json')
        if info.file_size > MAX_MANIFEST_BYTES:
            raise ValueError('Project manifest is too large')
        manifest = json.loads(archive.read(info))
        if manifest.get('version') != 1:
            raise ValueError('Unsupported Photon Animation Project version')
        entries = manifest.get('frames', [])
        canvas = manifest.get('canvas', [])
        if len(canvas) != 2 or any(not isinstance(v, int) or v < 1 or v > 32768 for v in canvas):
            raise ValueError('Invalid project canvas')
        if not 1 <= len(entries) <= MAX_FRAMES or canvas[0]*canvas[1]*len(entries)*4 > import_limit:
            raise ValueError('Project exceeds the decoded memory limit')
        store = FrameStore()
        frames = []
        for entry in entries:
            check_cancel(cancel)
            name = entry['path']
            if not name.startswith('frames/') or name not in names:
                raise ValueError('Invalid project frame path')
            with Image.open(io.BytesIO(archive.read(name))) as image:
                if image.size != tuple(canvas) or image.format != 'PNG':
                    raise ValueError('Invalid project frame pixels')
                artwork = entry.get('artwork', [])
                from .artwork import validate_artwork
                for item in artwork:
                    validate_artwork(item)
                frames.append(Frame(PhotonImage(image.convert('RGBA'), store, 'PNG'), entry['duration_ms'], artwork, entry['id']))
        metadata = {key: base64.b64decode(value, validate=True) for key, value in manifest.get('metadata', {}).items()
                    if key in ('icc_profile', 'exif')}
        document = Document(frames, manifest.get('source_format', 'PNG'), manifest['total_plays'],
                            manifest.get('animation', True), metadata, store=store)
        document.validate()
        return document
