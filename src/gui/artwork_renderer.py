"""Render identical image-space artwork for display and exported pixels."""
from PIL import Image, ImageQt
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPen, QTransform
from PySide6.QtCore import QRectF, Qt

def render_frame(frame):
    image = QImage(ImageQt.ImageQt(frame.image.current.convert('RGBA'))).copy()
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for item in frame.artwork:
        if not item.get('visible', True):
            continue
        painter.save()
        painter.setOpacity(max(0, min(1, item.get('opacity', 1))))
        painter.setTransform(QTransform(*item.get('transform', (1, 0, 0, 1, 0, 0))))
        color = QColor(*item.get('color', (255, 255, 255, 255)))
        painter.setPen(QPen(color, item.get('stroke_width', 2)))
        fill = item.get('fill')
        painter.setBrush(QColor(*fill) if fill else Qt.BrushStyle.NoBrush)
        rect = QRectF(item.get('x', 0), item.get('y', 0), item.get('width', 100), item.get('height', 50))
        kind = item['kind']
        if kind == 'text':
            font = QFont(item.get('font_family', 'Sans Serif'))
            font.setPixelSize(max(1, int(item.get('font_size', 16))))
            font.setBold(item.get('bold', False))
            painter.setFont(font)
            if item.get('background', False):
                painter.fillRect(rect, QColor(0, 0, 0, 160))
            painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, item.get('text', ''))
        elif kind == 'rectangle':
            painter.drawRect(rect)
        elif kind == 'ellipse':
            painter.drawEllipse(rect)
        elif kind == 'line':
            painter.drawLine(rect.topLeft(), rect.bottomRight())
        painter.restore()
    painter.end()
    return ImageQt.fromqimage(image)
