from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QScrollArea, QPushButton, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QTimer, QRect, QPoint
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QWheelEvent, QMouseEvent
from core.utils import pil_to_qpixmap, scale_pixmap_smooth
from core.image import PhotonImage
from core.overlays import (OverlayManager, GridOverlay, RulerOverlay, TextOverlay, 
                            CrosshairOverlay, ShapeOverlay, PixelInfoOverlay)
import math


class ImageViewer(QScrollArea):
    image_clicked = Signal(int, int)
    zoom_changed = Signal(float)
    
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QScrollArea {
                background-color: #2b2b2b;
                border: none;
            }
        """)
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: transparent;")
        self.image_label.setMinimumSize(100, 100)
        
        self.setWidget(self.image_label)
        
        self.current_pixmap = None
        self.original_pixmap = None
        self.zoom_factor = 1.0
        self.fit_to_window = True
        self.crop_mode = False
        self.crop_start = None
        self.crop_end = None
        self.crop_rect = None
        
        self.overlay_manager = OverlayManager()
        self.show_overlays = True
        self.pixel_info_mode = False
        self.shape_drawing_mode = None
        self.current_shape = None
        self.mouse_position = QPoint()
        
        self.image_label.mousePressEvent = self._mouse_press_event
        self.image_label.mouseMoveEvent = self._mouse_move_event
        self.image_label.mouseReleaseEvent = self._mouse_release_event
    
    def set_image(self, photon_image: PhotonImage):
        if photon_image:
            self.original_pixmap = pil_to_qpixmap(photon_image.current)
            self._update_display()
    
    def set_pixmap(self, pixmap: QPixmap):
        self.original_pixmap = pixmap
        self._update_display()
    
    def zoom_in(self):
        self.fit_to_window = False
        self.zoom_factor *= 1.25
        self._update_display()
        self.zoom_changed.emit(self.zoom_factor)
    
    def zoom_out(self):
        self.fit_to_window = False
        self.zoom_factor /= 1.25
        self._update_display()
        self.zoom_changed.emit(self.zoom_factor)
    
    def zoom_to_fit(self):
        self.fit_to_window = True
        self._update_display()
    
    def zoom_to_actual(self):
        self.fit_to_window = False
        self.zoom_factor = 1.0
        self._update_display()
        self.zoom_changed.emit(self.zoom_factor)
    
    def set_zoom(self, factor: float):
        self.fit_to_window = False
        self.zoom_factor = factor
        self._update_display()
        self.zoom_changed.emit(self.zoom_factor)
    
    def enable_crop_mode(self, enabled: bool):
        self.crop_mode = enabled
        if not enabled:
            self.crop_rect = None
            self._update_display()
    
    def set_shape_drawing_mode(self, shape_type: str):
        self.shape_drawing_mode = shape_type
        self.crop_mode = False
    
    def toggle_grid_overlay(self):
        grid_overlays = self.overlay_manager.get_overlays_by_type(GridOverlay)
        if grid_overlays:
            for overlay in grid_overlays:
                overlay.set_visible(not overlay.visible)
        else:
            grid = GridOverlay()
            self.overlay_manager.add_overlay(grid)
        self._update_display()
    
    def toggle_ruler_overlay(self):
        ruler_overlays = self.overlay_manager.get_overlays_by_type(RulerOverlay)
        if ruler_overlays:
            for overlay in ruler_overlays:
                overlay.set_visible(not overlay.visible)
        else:
            ruler = RulerOverlay()
            self.overlay_manager.add_overlay(ruler)
        self._update_display()
    
    def add_text_overlay(self, text: str, position_str: str = "Click to Place", font_size: int = 16, color: QColor | None = None, show_background: bool = True):
        from core.overlays import AnchorPosition
        
        if color is None:
            color = QColor(255, 255, 255)
            
        # Map position string to actual position/anchor
        position_map = {
            "Top Left": (AnchorPosition.TOP_LEFT, QPoint(0, 0)),
            "Top Center": (AnchorPosition.TOP_CENTER, QPoint(0, 0)),
            "Top Right": (AnchorPosition.TOP_RIGHT, QPoint(0, 0)),
            "Left Center": (AnchorPosition.LEFT_CENTER, QPoint(0, 0)),
            "Center": (AnchorPosition.CENTER, QPoint(0, 0)),
            "Right Center": (AnchorPosition.RIGHT_CENTER, QPoint(0, 0)),
            "Bottom Left": (AnchorPosition.BOTTOM_LEFT, QPoint(0, 0)),
            "Bottom Center": (AnchorPosition.BOTTOM_CENTER, QPoint(0, 0)),
            "Bottom Right": (AnchorPosition.BOTTOM_RIGHT, QPoint(0, 0)),
            "Click to Place": (AnchorPosition.CURSOR_OFFSET, QPoint(50, 50))
        }
        
        anchor, position = position_map.get(position_str, (AnchorPosition.CURSOR_OFFSET, QPoint(50, 50)))
        
        text_overlay = TextOverlay(text, position, font_size)
        text_overlay.set_color(color)
        text_overlay.show_background = show_background
        text_overlay.set_anchor_position(anchor)
        
        self.overlay_manager.add_overlay(text_overlay)
        self._update_display()
    
    def toggle_pixel_info_mode(self):
        self.pixel_info_mode = not self.pixel_info_mode
        if not self.pixel_info_mode:
            pixel_overlays = self.overlay_manager.get_overlays_by_type(PixelInfoOverlay)
            for overlay in pixel_overlays:
                self.overlay_manager.remove_overlay(overlay)
        self._update_display()
    
    def clear_overlays(self):
        self.overlay_manager.clear_overlays()
        self._update_display()
    
    def get_crop_rect(self):
        return self.crop_rect
    
    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            super().wheelEvent(event)
    
    def _mouse_press_event(self, event: QMouseEvent):
        if self.crop_mode and event.button() == Qt.LeftButton:
            self.crop_start = event.pos()
            self.crop_end = event.pos()
        elif self.shape_drawing_mode and event.button() == Qt.LeftButton:
            image_pos = self._screen_to_image_pos(event.pos())
            self.current_shape = ShapeOverlay(self.shape_drawing_mode, image_pos, image_pos)
            self.overlay_manager.add_overlay(self.current_shape)
        
        self.mouse_position = event.pos()
    
    def _mouse_move_event(self, event: QMouseEvent):
        self.mouse_position = event.pos()
        
        if self.crop_mode and self.crop_start:
            self.crop_end = event.pos()
            self._update_crop_display()
        elif self.shape_drawing_mode and self.current_shape:
            end_pos = self._screen_to_image_pos(event.pos())
            self.current_shape.set_points(self.current_shape.start_point, end_pos)
            self._update_display()
        elif self.pixel_info_mode and self.original_pixmap:
            self._update_pixel_info(event.pos())
    
    def _mouse_release_event(self, event: QMouseEvent):
        if self.crop_mode and self.crop_start and self.crop_end:
            x1, y1 = self.crop_start.x(), self.crop_start.y()
            x2, y2 = self.crop_end.x(), self.crop_end.y()
            
            if abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
                self.crop_rect = QRect(min(x1, x2), min(y1, y2), 
                                       abs(x2 - x1), abs(y2 - y1))
                self._update_display()
        elif self.shape_drawing_mode and self.current_shape:
            self.current_shape = None
            self.shape_drawing_mode = None
    
    def _screen_to_image_pos(self, screen_pos: QPoint) -> QPoint:
        if not self.current_pixmap:
            return QPoint(0, 0)
        
        image_rect = self._get_image_rect()
        if image_rect.contains(screen_pos):
            rel_x = (screen_pos.x() - image_rect.left()) / self.zoom_factor
            rel_y = (screen_pos.y() - image_rect.top()) / self.zoom_factor
            return QPoint(int(rel_x), int(rel_y))
        return QPoint(0, 0)
    
    def _get_image_rect(self) -> QRect:
        if not self.current_pixmap:
            return QRect()
        
        label_rect = self.image_label.geometry()
        pixmap_size = self.current_pixmap.size()
        
        x = label_rect.x() + (label_rect.width() - pixmap_size.width()) // 2
        y = label_rect.y() + (label_rect.height() - pixmap_size.height()) // 2
        
        return QRect(x, y, pixmap_size.width(), pixmap_size.height())
    
    def _update_pixel_info(self, screen_pos: QPoint):
        image_pos = self._screen_to_image_pos(screen_pos)
        
        if self.original_pixmap and not self.original_pixmap.isNull():
            if (0 <= image_pos.x() < self.original_pixmap.width() and 
                0 <= image_pos.y() < self.original_pixmap.height()):
                
                pixel_color = self.original_pixmap.toImage().pixelColor(image_pos.x(), image_pos.y())
                
                pixel_overlays = self.overlay_manager.get_overlays_by_type(PixelInfoOverlay)
                for overlay in pixel_overlays:
                    self.overlay_manager.remove_overlay(overlay)
                
                pixel_info = PixelInfoOverlay(image_pos, pixel_color)
                self.overlay_manager.add_overlay(pixel_info)
                self._update_display()
    
    def _update_display(self):
        if not self.original_pixmap:
            return
        
        if self.fit_to_window:
            viewport_size = self.viewport().size()
            self.current_pixmap = scale_pixmap_smooth(
                self.original_pixmap, viewport_size, True)
        else:
            new_size = self.original_pixmap.size() * self.zoom_factor
            self.current_pixmap = scale_pixmap_smooth(
                self.original_pixmap, new_size, False)
        
        display_pixmap = QPixmap(self.current_pixmap)
        painter = QPainter(display_pixmap)
        
        if self.crop_mode and self.crop_rect:
            self._draw_crop_overlay(painter)
        
        if self.show_overlays:
            image_rect = QRect(0, 0, display_pixmap.width(), display_pixmap.height())
            actual_zoom = self.current_pixmap.width() / self.original_pixmap.width()
            self.overlay_manager.draw_all(painter, image_rect, actual_zoom)
        
        painter.end()
        
        self.image_label.setPixmap(display_pixmap)
        self.image_label.resize(display_pixmap.size())
    
    def _update_crop_display(self):
        self._update_display()
    
    def _draw_crop_overlay(self, painter: QPainter):
        if not self.crop_rect:
            return
        
        overlay_color = QColor(0, 0, 0, 128)
        painter.fillRect(painter.device().rect(), overlay_color)
        
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.fillRect(self.crop_rect, Qt.transparent)
        
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        pen = QPen(QColor(255, 255, 255), 2, Qt.DashLine)
        painter.setPen(pen)
        painter.drawRect(self.crop_rect)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_to_window:
            QTimer.singleShot(50, self._update_display)