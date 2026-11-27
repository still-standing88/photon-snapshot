"""Shared still/animation encoding and decode-verified atomic commits."""
from dataclasses import dataclass
from pathlib import Path
import io
import os
import tempfile
from PIL import Image, ImageCms
from .formats import get_format, format_for_path, animation_available


class CancelledError(Exception):
    pass


@dataclass(frozen=True)
class ExportOptions:
    format_id: str = 'PNG'
    quality: int = 90
    optimize: bool = True
    png_compression: int = 6
    lossless: bool = False
    effort: int = 4
    tiff_compression: str = 'tiff_lzw'
    palette_size: int = 256
    dither: bool = True
    alpha_threshold: int = 128
    gif_transparency: bool = True
    background: tuple = (255, 255, 255)
    preserve_metadata: bool = False

    def validate(self):
        fmt = get_format(self.format_id)
        if not fmt.writable:
            raise ValueError(f'{fmt.label} encoder is unavailable')
        limits = {'quality': (1 if fmt.id == 'JPEG' else 0, 95 if fmt.id == 'JPEG' else 100),
                  'png_compression': (0, 9), 'effort': (0, 6),
                  'palette_size': (2, 256), 'alpha_threshold': (0, 255)}
        for key, (low, high) in limits.items():
            value = getattr(self, key)
            if not isinstance(value, int) or not low <= value <= high:
                raise ValueError(f'{key} must be between {low} and {high}')
        if self.tiff_compression not in ('raw', 'tiff_lzw', 'tiff_adobe_deflate'):
            raise ValueError('Unsupported TIFF compression')
        if len(self.background) != 3 or any(not isinstance(v, int) or not 0 <= v <= 255 for v in self.background):
            raise ValueError('Invalid background colour')
        return fmt


def check_cancel(cancel=None):
    if cancel and cancel():
        raise CancelledError('Cancelled')


def flatten(image, background):
    rgba = image.convert('RGBA')
    canvas = Image.new('RGBA', rgba.size, tuple(background) + (255,))
    return Image.alpha_composite(canvas, rgba).convert('RGB')


def normalize_colour(image, profile):
    if not profile:
        return image.copy(), None
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(profile))
        target = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
        alpha = image.convert('RGBA').getchannel('A')
        result = ImageCms.profileToProfile(image, source, target, outputMode='RGB').convert('RGBA')
        result.putalpha(alpha)
        return result, target.tobytes()
    except (OSError, ValueError, ImageCms.PyCMSError) as exc:
        raise ValueError('Unsupported or invalid ICC colour profile') from exc


def prepare_image(image, options, metadata=None):
    fmt = options.validate()
    result = image.copy()
    profile = (metadata or {}).get('icc_profile')
    # Pixel modes changed by editing are RGB(A), so convert a source profile
    # before writing it. Invalid/mismatched profiles must never be relabelled.
    if profile and options.preserve_metadata:
        result, _ = normalize_colour(result, profile)
    if fmt.id in ('JPEG', 'BMP'):
        result = flatten(result, options.background)
    elif result.mode not in ('RGB', 'RGBA', 'L', 'LA', 'P'):
        result = result.convert('RGBA')
    result.info.clear()
    return result


def metadata_options(metadata, options, size):
    if not options.preserve_metadata:
        return {}
    fmt = get_format(options.format_id).id
    result = {}
    metadata = metadata or {}
    if metadata.get('icc_profile') and fmt in ('JPEG', 'PNG', 'TIFF', 'WEBP'):
        result['icc_profile'] = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    if metadata.get('exif') and fmt in ('JPEG', 'PNG', 'TIFF', 'WEBP'):
        exif = Image.Exif()
        exif.load(metadata['exif'])
        for tag in (274, 256, 257, 40962, 40963):
            if tag in exif:
                del exif[tag]
        if 34665 in exif:
            nested = exif.get_ifd(34665)
            nested.pop(40962, None)
            nested.pop(40963, None)
        result['exif'] = exif.tobytes()
    return result


def encoder_options(options):
    fmt = options.validate().id
    if fmt == 'JPEG':
        return {'quality': options.quality, 'optimize': options.optimize}
    if fmt == 'PNG':
        return {'compress_level': options.png_compression}
    if fmt == 'WEBP':
        return {'quality': options.quality, 'lossless': options.lossless, 'method': options.effort}
    if fmt == 'TIFF':
        return {'compression': options.tiff_compression}
    return {}


def gif_frames(images, options, cancel=None):
    # Bound palette sampling independently of canvas size and frame count.
    samples = []
    stride = max(1, len(images)//128)
    for image in images[::stride]:
        check_cancel(cancel)
        sample = flatten(image, options.background)
        sample.thumbnail((32, 32))
        samples.extend(list(sample.get_flattened_data() if hasattr(sample, 'get_flattened_data') else sample.getdata()))
    sample_image = Image.new('RGB', (max(1, len(samples)), 1))
    sample_image.putdata(samples or [(0, 0, 0)])
    count = options.palette_size - 1 if options.gif_transparency else options.palette_size
    palette = sample_image.quantize(colors=max(1, count))
    colours = palette.getpalette() or []
    # Quantization may use padded colours; reserve index 255 and remap it.
    colours = (colours + [0]*768)[:768]
    palette.putpalette(colours)
    result = []
    for image in images:
        check_cancel(cancel)
        rgba = image.convert('RGBA')
        quantized = flatten(rgba, options.background).quantize(palette=palette,
            dither=Image.Dither.FLOYDSTEINBERG if options.dither else Image.Dither.NONE)
        if options.gif_transparency:
            used = quantized.point(lambda v: 0 if v >= count else v)
            used.putpalette(colours)
            mask = rgba.getchannel('A').point(lambda a: 255 if a < options.alpha_threshold else 0)
            used.paste(255, mask=mask)
            used.info['transparency'] = 255
            quantized = used
        result.append(quantized)
    return result


def gif_durations(durations):
    total, encoded = 0, 0
    result = []
    for duration in durations:
        total += duration
        next_total = int(total/10 + .5)*10
        effective = max(10, next_total - encoded)
        result.append(effective)
        encoded += effective
    return result


def encode_images(images, durations, total_plays, options, metadata=None, cancel=None):
    fmt = options.validate().id
    check_cancel(cancel)
    prepared = []
    for image in images:
        check_cancel(cancel)
        prepared.append(prepare_image(image, options, metadata))
    images = prepared
    animated = len(images) > 1
    if animated and not animation_available(fmt):
        raise ValueError('Choose GIF/WebP to preserve animation, or explicitly export frames')
    kwargs = encoder_options(options)
    kwargs.update(metadata_options(metadata, options, images[0].size))
    if fmt == 'GIF':
        images = gif_frames(images, options, cancel)
        kwargs['optimize'] = False
        if options.gif_transparency:
            kwargs['transparency'] = 255
        kwargs['disposal'] = 2
    if animated:
        kwargs.update(save_all=True, append_images=images[1:],
                      duration=gif_durations(durations) if fmt == 'GIF' else durations)
        if total_plays == 0:
            kwargs['loop'] = 0
        elif total_plays > 1:
            kwargs['loop'] = total_plays - 1 if fmt == 'GIF' else total_plays
        elif fmt == 'WEBP':
            kwargs['loop'] = 1
    buffer = io.BytesIO()
    images[0].save(buffer, format=fmt, **kwargs)
    check_cancel(cancel)
    return buffer.getvalue()


def atomic_write(path, writer, validator, overwrite=True, cancel=None):
    path = Path(path)
    if not path.parent.is_dir():
        raise OSError('Destination folder does not exist')
    fd, name = tempfile.mkstemp(prefix='.photon-', suffix='.tmp', dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        check_cancel(cancel)
        writer(temporary)
        check_cancel(cancel)
        validator(temporary)
        check_cancel(cancel)
        if overwrite:
            os.replace(temporary, path)
        else:
            # Hard-link commit is atomic and refuses existing destinations.
            os.link(temporary, path)
            temporary.unlink()
    finally:
        temporary.unlink(missing_ok=True)
    return path


def validate_image(path, expected_size=None, expected_format=None, expected_duration=None, expected_plays=None, cancel=None):
    with Image.open(path) as image:
        if expected_format and image.format != expected_format:
            raise ValueError('Encoded format does not match the selected format')
        duration = 0
        raw_loop = image.info.get('loop')
        for index in range(getattr(image, 'n_frames', 1)):
            check_cancel(cancel)
            image.seek(index)
            image.load()
            duration += int(image.info.get('duration', 0) or 0)
            if expected_size and image.size != expected_size:
                raise ValueError('Encoded canvas dimensions changed unexpectedly')
        if expected_duration is not None and duration != expected_duration:
            raise ValueError('Encoded animation timing does not match the requested timing')
        plays = 1 if raw_loop is None else 0 if raw_loop == 0 else raw_loop+1 if image.format == 'GIF' else raw_loop
        if expected_plays is not None and plays != expected_plays:
            raise ValueError('Encoded animation loop policy changed unexpectedly')


def export_images(path, images, durations, total_plays, options, metadata=None, overwrite=True, cancel=None):
    fmt = options.validate().id
    if format_for_path(path).id != fmt:
        raise ValueError('Filename extension and selected format disagree')
    data = encode_images(images, durations, total_plays, options, metadata, cancel)
    expected_duration = sum(gif_durations(durations) if fmt == 'GIF' else durations) if len(images) > 1 else None
    return atomic_write(path, lambda p: p.write_bytes(data),
        lambda p: validate_image(p, images[0].size, fmt, expected_duration, total_plays if len(images) > 1 else None, cancel), overwrite, cancel)


def export_document(path, document, options, renderer=None, overwrite=True, cancel=None, frame_ids=None):
    frames = [f for f in document.frames if frame_ids is None or f.id in frame_ids]
    images = []
    if not frames:
        raise ValueError('Select at least one frame to export')
    for frame in frames:
        check_cancel(cancel)
        if frame.artwork and renderer is None:
            raise ValueError('Artwork requires a native-resolution renderer')
        images.append(renderer(frame) if renderer else frame.image.current)
    return export_images(path, images, [f.duration_ms for f in frames], document.total_plays,
                         options, document.metadata, overwrite, cancel)
