from PIL import Image as PILImage, ImageQt
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt
import io
import os


def pil_to_qpixmap(pil_image: PILImage.Image) -> QPixmap:
    if pil_image.mode == "RGB":
        r, g, b = pil_image.split()
        pil_image = PILImage.merge("RGB", (b, g, r))
    elif pil_image.mode == "RGBA":
        r, g, b, a = pil_image.split()
        pil_image = PILImage.merge("RGBA", (b, g, r, a))
    elif pil_image.mode == "L":
        pil_image = pil_image.convert("RGB")
    
    qim = ImageQt.ImageQt(pil_image)
    qpixmap = QPixmap.fromImage(qim)
    return qpixmap


def qpixmap_to_pil(qpixmap: QPixmap) -> PILImage.Image:
    qimage = qpixmap.toImage()
    buffer = qimage.bits()
    width = qimage.width()
    height = qimage.height()
    
    if qimage.format() == QImage.Format_RGB32:
        pil_image = PILImage.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
    elif qimage.format() == QImage.Format_ARGB32:
        pil_image = PILImage.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
    else:
        qimage = qimage.convertToFormat(QImage.Format_RGB32)
        buffer = qimage.bits()
        pil_image = PILImage.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
    
    return pil_image


def get_image_formats():
    return {
        'JPEG': '*.jpg *.jpeg',
        'PNG': '*.png',
        'BMP': '*.bmp',
        'GIF': '*.gif',
        'TIFF': '*.tiff *.tif',
        'WEBP': '*.webp'
    }


def get_supported_extensions() -> set[str]:
    """Every extension the app claims to open, derived from the same table the
    file dialog filter is built from.

    Single source of truth: ``is_image_file`` used to carry its own hardcoded
    duplicate of this set, and the MSI's file associations a third copy. Both
    now derive from ``get_image_formats()``.
    """
    extensions = set()
    for patterns in get_image_formats().values():
        for pattern in patterns.split():
            extensions.add(pattern.lstrip('*').lower())
    return extensions


def get_supported_extensions_str() -> str:
    """Human-readable list for error messages, e.g. ".bmp, .gif, .jpg, ..."."""
    return ", ".join(sorted(get_supported_extensions()))


def get_all_image_filter():
    formats = get_image_formats()
    all_formats = ' '.join(formats.values())
    return f"Image files ({all_formats})"


def get_save_formats():
    return ['JPEG', 'PNG', 'BMP', 'TIFF', 'WEBP']


def scale_pixmap_smooth(pixmap: QPixmap, size, keep_aspect_ratio=True) -> QPixmap:
    if keep_aspect_ratio:
        return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    else:
        return pixmap.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def create_thumbnail(pil_image: PILImage.Image, size=(128, 128)) -> QPixmap:
    thumbnail = pil_image.copy()
    thumbnail.thumbnail(size, PILImage.Resampling.LANCZOS)
    return pil_to_qpixmap(thumbnail)


def get_file_size_str(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def is_image_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in get_supported_extensions()
