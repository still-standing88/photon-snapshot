from abc import ABC, abstractmethod
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics
from PySide6.QtCore import QRect, QPoint, Qt
from typing import List, Tuple, Optional
from enum import Enum
import math


class AnchorPosition(Enum):
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    TOP_CENTER = "top_center"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_CENTER = "bottom_center"
    LEFT_CENTER = "left_center"
    RIGHT_CENTER = "right_center"
    CENTER = "center"
    CURSOR_OFFSET = "cursor_offset"


class Overlay(ABC):
    def __init__(self, name: str, visible: bool = True):
        self.name = name
        self.visible = visible
        self.opacity = 1.0
        self.color = QColor(255, 255, 255)
        self.padding = 8
        self.anchor_position = AnchorPosition.CURSOR_OFFSET
        self.custom_offset = QPoint(15, -30)
    
    @abstractmethod
    def draw(self, painter: QPainter, image_rect: QRect, zoom_factor: float):
        pass
    
    def set_visible(self, visible: bool):
        self.visible = visible
    
    def set_opacity(self, opacity: float):
        self.opacity = max(0.0, min(1.0, opacity))
    
    def set_color(self, color: QColor):
        self.color = color
    
    def set_anchor_position(self, anchor: AnchorPosition, custom_offset: QPoint = QPoint(15, -30)):
        self.anchor_position = anchor
        self.custom_offset = custom_offset
    
    def _get_anchored_position(self, content_rect: QRect, container_rect: QRect, reference_point: QPoint = None) -> QPoint: # type:ignore
        if self.anchor_position == AnchorPosition.TOP_LEFT:
            return QPoint(container_rect.left() + self.padding, container_rect.top() + self.padding)
        
        elif self.anchor_position == AnchorPosition.TOP_RIGHT:
            return QPoint(container_rect.right() - content_rect.width() - self.padding, 
                          container_rect.top() + self.padding)
        
        elif self.anchor_position == AnchorPosition.BOTTOM_LEFT:
            return QPoint(container_rect.left() + self.padding, 
                          container_rect.bottom() - content_rect.height() - self.padding)
        
        elif self.anchor_position == AnchorPosition.BOTTOM_RIGHT:
            return QPoint(container_rect.right() - content_rect.width() - self.padding, 
                          container_rect.bottom() - content_rect.height() - self.padding)
        
        elif self.anchor_position == AnchorPosition.CENTER:
            return QPoint(container_rect.center().x() - content_rect.width() // 2, 
                          container_rect.center().y() - content_rect.height() // 2)
        
        elif self.anchor_position == AnchorPosition.TOP_CENTER:
            return QPoint(container_rect.center().x() - content_rect.width() // 2, 
                          container_rect.top() + self.padding)
        
        elif self.anchor_position == AnchorPosition.BOTTOM_CENTER:
            return QPoint(container_rect.center().x() - content_rect.width() // 2, 
                          container_rect.bottom() - content_rect.height() - self.padding)
        
        elif self.anchor_position == AnchorPosition.LEFT_CENTER:
            return QPoint(container_rect.left() + self.padding, 
                          container_rect.center().y() - content_rect.height() // 2)
        
        elif self.anchor_position == AnchorPosition.RIGHT_CENTER:
            return QPoint(container_rect.right() - content_rect.width() - self.padding, 
                          container_rect.center().y() - content_rect.height() // 2)
        
        else:
            if reference_point:
                return self._get_safe_position(content_rect, container_rect, self.custom_offset, reference_point)
            else:
                return self._get_safe_position(content_rect, container_rect, self.custom_offset)
    
    def _get_safe_position(self, desired_rect: QRect, container_rect: QRect, offset: QPoint = QPoint(15, -30), reference_point: QPoint = None) -> QPoint: #type:ignore
        if reference_point:
            pos = reference_point + offset
        else:
            pos = desired_rect.topLeft() + offset
        
        if pos.x() + desired_rect.width() > container_rect.right():
            pos.setX(container_rect.right() - desired_rect.width() - self.padding)
        
        if pos.x() < container_rect.left():
            pos.setX(container_rect.left() + self.padding)
        
        if pos.y() < container_rect.top():
            pos.setY(container_rect.top() + self.padding)
        
        if pos.y() + desired_rect.height() > container_rect.bottom():
            pos.setY(container_rect.bottom() - desired_rect.height() - self.padding)
        
        return pos


class GridOverlay(Overlay):
    def __init__(self, grid_size: int = 50, line_width: int = 1):
        super().__init__("Grid")
        self.grid_size = grid_size
        self.line_width = line_width
        self.color = QColor(255, 255, 255, 128)
    
    def draw(self, painter: QPainter, image_rect: QRect, zoom_factor: float):
        if not self.visible:
            return
        
        pen = QPen(self.color, self.line_width)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        
        scaled_grid_size = self.grid_size * zoom_factor
        
        x = image_rect.left()
        while x <= image_rect.right():
            painter.drawLine(int(x), image_rect.top(), int(x), image_rect.bottom())
            x += scaled_grid_size
        

        y = image_rect.top()
        while y <= image_rect.bottom():
            painter.drawLine(image_rect.left(), int(y), image_rect.right(), int(y))
            y += scaled_grid_size


class RulerOverlay(Overlay):
    def __init__(self, show_horizontal: bool = True, show_vertical: bool = True):
        super().__init__("Ruler")
        self.show_horizontal = show_horizontal
        self.show_vertical = show_vertical
        self.color = QColor(255, 255, 0, 200)
        self.ruler_height = 20
        self.tick_interval = 50
    
    def draw(self, painter: QPainter, image_rect: QRect, zoom_factor: float):
        if not self.visible:
            return
        
        pen = QPen(self.color, 1)
        painter.setPen(pen)
        
        font = QFont("Arial", 8)
        painter.setFont(font)
        
        scaled_interval = self.tick_interval * zoom_factor
        
        if self.show_horizontal:
            self._draw_horizontal_ruler(painter, image_rect, scaled_interval)
        
        if self.show_vertical:
            self._draw_vertical_ruler(painter, image_rect, scaled_interval)
    
    def _draw_horizontal_ruler(self, painter: QPainter, image_rect: QRect, scaled_interval: float):
        ruler_rect = QRect(image_rect.left(), image_rect.top() - self.ruler_height, 
                          image_rect.width(), self.ruler_height)
        
        painter.fillRect(ruler_rect, QColor(0, 0, 0, 180))
        
        x = image_rect.left()
        pixel_pos = 0
        while x <= image_rect.right():
            tick_height = 5 if pixel_pos % 100 == 0 else 3
            painter.drawLine(int(x), ruler_rect.bottom() - tick_height, 
                           int(x), ruler_rect.bottom())
            
            if pixel_pos % 100 == 0:
                painter.drawText(int(x + 2), ruler_rect.bottom() - 8, str(pixel_pos))
            
            x += scaled_interval
            pixel_pos += self.tick_interval
    
    def _draw_vertical_ruler(self, painter: QPainter, image_rect: QRect, scaled_interval: float):
        ruler_rect = QRect(image_rect.left() - self.ruler_height, image_rect.top(), 
                          self.ruler_height, image_rect.height())
        
        painter.fillRect(ruler_rect, QColor(0, 0, 0, 180))
        
        y = image_rect.top()
        pixel_pos = 0
        while y <= image_rect.bottom():
            tick_width = 5 if pixel_pos % 100 == 0 else 3
            painter.drawLine(ruler_rect.right() - tick_width, int(y), 
                           ruler_rect.right(), int(y))
            
            if pixel_pos % 100 == 0:
                painter.save()
                painter.translate(ruler_rect.right() - 15, int(y - 2))
                painter.rotate(-90)
                painter.drawText(0, 0, str(pixel_pos))
                painter.restore()
            
            y += scaled_interval
            pixel_pos += self.tick_interval


class TextOverlay(Overlay):
    def __init__(self, text: str, position: QPoint, font_size: int = 16):
        super().__init__("Text")
        self.text = text
        self.position = position
        self.font_size = font_size
        self.background_color = QColor(0, 0, 0, 128)
        self.show_background = True
    
    def draw(self, painter: QPainter, image_rect: QRect, zoom_factor: float):
        if not self.visible or not self.text:
            return
        
        font = QFont("Arial", int(self.font_size * zoom_factor))
        painter.setFont(font)
        
        metrics = QFontMetrics(font)
        text_rect = metrics.boundingRect(self.text)
        
        # Use anchor positioning if set, otherwise use direct position
        if hasattr(self, 'anchor_position') and self.anchor_position != AnchorPosition.CURSOR_OFFSET:
            final_pos = self._get_anchored_position(text_rect, image_rect)
        else:
            scaled_pos = QPoint(
                int(self.position.x() * zoom_factor + image_rect.left()),
                int(self.position.y() * zoom_factor + image_rect.top())
            )
            final_pos = scaled_pos
        
        text_rect.moveTopLeft(final_pos)
        
        if self.show_background:
            painter.fillRect(text_rect.adjusted(-4, -2, 4, 2), self.background_color)
        
        pen = QPen(self.color)
        painter.setPen(pen)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft, self.text)
    
    def set_text(self, text: str):  #type:ignore
        self.text = text
    
    def set_position(self, position: QPoint):
        self.position = position


class CrosshairOverlay(Overlay):
    def __init__(self, position: QPoint):
        super().__init__("Crosshair")
        self.position = position
        self.color = QColor(255, 0, 0, 200)
        self.line_width = 1
    
    def draw(self, painter: QPainter, image_rect: QRect, zoom_factor: float):
        if not self.visible:
            return
        
        pen = QPen(self.color, self.line_width)
        painter.setPen(pen)
        
        scaled_pos = QPoint(
            int(self.position.x() * zoom_factor + image_rect.left()),
            int(self.position.y() * zoom_factor + image_rect.top())
        )
        

        painter.drawLine(image_rect.left(), scaled_pos.y(), 
                        image_rect.right(), scaled_pos.y())
        painter.drawLine(scaled_pos.x(), image_rect.top(), 
                        scaled_pos.x(), image_rect.bottom())
    
    def set_position(self, position: QPoint):
        self.position = position


class ShapeOverlay(Overlay):
    def __init__(self, shape_type: str, start_point: QPoint, end_point: QPoint):
        super().__init__(f"{shape_type.title()} Shape")
        self.shape_type = shape_type
        self.start_point = start_point
        self.end_point = end_point
        self.line_width = 2
        self.fill_color = QColor(255, 255, 255, 50)
        self.filled = False
    
    def draw(self, painter: QPainter, image_rect: QRect, zoom_factor: float):
        if not self.visible:
            return
        
        pen = QPen(self.color, self.line_width)
        painter.setPen(pen)
        
        scaled_start = QPoint(
            int(self.start_point.x() * zoom_factor + image_rect.left()),
            int(self.start_point.y() * zoom_factor + image_rect.top())
        )
        scaled_end = QPoint(
            int(self.end_point.x() * zoom_factor + image_rect.left()),
            int(self.end_point.y() * zoom_factor + image_rect.top())
        )
        
        if self.shape_type == "rectangle":
            rect = QRect(scaled_start, scaled_end).normalized()
            if self.filled:
                painter.fillRect(rect, self.fill_color)
            painter.drawRect(rect)
        
        elif self.shape_type == "circle":
            rect = QRect(scaled_start, scaled_end).normalized()
            if self.filled:
                painter.setBrush(QBrush(self.fill_color))
            else:
                painter.setBrush(QBrush())
            painter.drawEllipse(rect)
        
        elif self.shape_type == "line":
            painter.drawLine(scaled_start, scaled_end)
    
    def set_points(self, start_point: QPoint, end_point: QPoint):
        self.start_point = start_point
        self.end_point = end_point


class PixelInfoOverlay(Overlay):
    def __init__(self, position: QPoint, pixel_color: QColor):
        super().__init__("Pixel Info")
        self.position = position
        self.pixel_color = pixel_color
        self.show_color_sample = True
    
    def draw(self, painter: QPainter, image_rect: QRect, zoom_factor: float):
        if not self.visible:
            return
        
        font = QFont("Arial", 10)
        painter.setFont(font)
        
        scaled_pos = QPoint(
            int(self.position.x() * zoom_factor + image_rect.left()),
            int(self.position.y() * zoom_factor + image_rect.top())
        )
        
        info_text = f"({self.position.x()}, {self.position.y()})\n"
        info_text += f"RGB({self.pixel_color.red()}, {self.pixel_color.green()}, {self.pixel_color.blue()})"
        
        metrics = QFontMetrics(font)
        text_rect = metrics.boundingRect(QRect(), Qt.TextFlag.TextWordWrap, info_text)
        
        info_pos = QPoint(scaled_pos.x() + 15, scaled_pos.y() - text_rect.height() - 25)
        text_rect.moveTopLeft(info_pos)
        
        painter.fillRect(text_rect.adjusted(-4, -2, 4, 2), QColor(0, 0, 0, 200))
        
        pen = QPen(QColor(255, 255, 255))
        painter.setPen(pen)
        painter.drawText(text_rect, Qt.TextFlag.TextWordWrap, info_text)
        
        if self.show_color_sample:
            sample_rect = QRect(text_rect.right() + 5, text_rect.top(), 20, 20)
            painter.fillRect(sample_rect, self.pixel_color)
            painter.drawRect(sample_rect)
    
    def update_info(self, position: QPoint, pixel_color: QColor):
        self.position = position
        self.pixel_color = pixel_color


class OverlayManager:
    def __init__(self):
        self.overlays: List[Overlay] = []
        self.active_overlay_types = set()
    
    def add_overlay(self, overlay: Overlay):
        self.overlays.append(overlay)
        self.active_overlay_types.add(type(overlay).__name__)
    
    def remove_overlay(self, overlay: Overlay):
        if overlay in self.overlays:
            self.overlays.remove(overlay)
            if not any(isinstance(o, type(overlay)) for o in self.overlays):
                self.active_overlay_types.discard(type(overlay).__name__)
    
    def clear_overlays(self):
        self.overlays.clear()
        self.active_overlay_types.clear()
    
    def get_overlays_by_type(self, overlay_type: type) -> List[Overlay]:
        return [o for o in self.overlays if isinstance(o, overlay_type)]
    
    def toggle_overlay_type(self, overlay_type: type):
        overlays_of_type = self.get_overlays_by_type(overlay_type)
        if overlays_of_type:
            for overlay in overlays_of_type:
                overlay.set_visible(not overlay.visible)
    
    def draw_all(self, painter: QPainter, image_rect: QRect, zoom_factor: float):
        for overlay in self.overlays:
            if overlay.visible:
                painter.save()
                overlay.draw(painter, image_rect, zoom_factor)
                painter.restore()
