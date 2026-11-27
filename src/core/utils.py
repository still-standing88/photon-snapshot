from PIL import Image as PILImage, ImageQt
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt
import io


def pil_to_qpixmap(pil_image: PILImage.Image) -> QPixmap:
    # Pillow's ImageQt already performs the RGB(A) -> QImage BGRA byte
    # reordering internally (see PIL.ImageQt._toqclass_helper), so the
    # channels must be passed through untouched - manually swapping R and B
    # here double-swapped them, rendering every image with red and blue
    # exchanged. Only normalize modes ImageQt can't consume directly.
    if pil_image.mode not in ("RGB", "RGBA"):
        pil_image = pil_image.convert("RGBA")
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
    from .formats import FORMATS
    return {f.id: ' '.join('*' + e for e in f.extensions) for f in FORMATS if f.readable}


def get_all_image_filter():
    from .formats import file_filter
    return file_filter(projects=True)


def get_save_formats():
    from .formats import FORMATS
    return [f.id for f in FORMATS if f.writable]


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
    from .formats import is_image_file as supported
    return supported(filename) or str(filename).lower().endswith('.photonanim')
