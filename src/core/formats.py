"""Shared, codec-aware image format registry. No Qt dependency."""
from dataclasses import dataclass
from pathlib import Path
from functools import lru_cache
import io
from PIL import Image

@dataclass(frozen=True)
class ImageFormat:
    id: str
    label: str
    extensions: tuple[str, ...]
    alpha: bool = False
    animation: bool = False

    @property
    def extension(self):
        return self.extensions[0]

    @property
    def readable(self):
        Image.init()
        return self.id in Image.OPEN

    @property
    def writable(self):
        Image.init()
        return self.id in Image.SAVE

FORMATS = (
    ImageFormat('JPEG', 'JPEG', ('.jpg', '.jpeg')),
    ImageFormat('PNG', 'PNG', ('.png',), True),
    ImageFormat('BMP', 'BMP', ('.bmp',)),
    ImageFormat('TIFF', 'TIFF', ('.tif', '.tiff'), True),
    ImageFormat('GIF', 'GIF', ('.gif',), True, True),
    ImageFormat('WEBP', 'WebP', ('.webp',), True, True),
)

def get_format(value):
    value = str(value).upper().lstrip('.')
    for fmt in FORMATS:
        if value == fmt.id or ('.' + value.lower()) in fmt.extensions:
            return fmt
    raise ValueError(f'Unsupported image format: {value}')

def format_for_path(path):
    return get_format(Path(path).suffix)

def is_image_file(path):
    return Path(path).suffix.lower() in {e for f in FORMATS if f.readable for e in f.extensions}

def file_filter(save=False, projects=False):
    formats = [f for f in FORMATS if (f.writable if save else f.readable)]
    rows = [f'{f.label} files ({" ".join("*" + e for e in f.extensions)})' for f in formats]
    if not save:
        extensions = [e for f in formats for e in f.extensions]
        if projects:
            extensions.append('.photonanim')
            rows.append('Photon Animation Project (*.photonanim)')
        rows.insert(0, 'Image files (' + ' '.join('*' + e for e in extensions) + ')')
    return ';;'.join(rows)

@lru_cache(maxsize=2)
def animation_available(format_id):
    try:
        fmt = get_format(format_id)
        if not fmt.animation or not fmt.writable:
            return False
        output = io.BytesIO()
        Image.new('RGBA', (2, 2), 'red').save(output, format=fmt.id, save_all=True,
            append_images=[Image.new('RGBA', (2, 2), 'blue')], duration=[30, 70], loop=0)
        output.seek(0)
        with Image.open(output) as decoded:
            decoded.seek(1)
            decoded.load()
            return decoded.n_frames == 2
    except (OSError, ValueError, KeyError):
        return False
