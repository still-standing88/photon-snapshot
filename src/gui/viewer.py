from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QScrollArea, QPushButton, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QTimer, QRect, QPoint, QSize
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QWheelEvent, QMouseEvent, QImage
from core.utils import pil_to_qpixmap, scale_pixmap_smooth
from core.image import PhotonImage
from core.overlays import (OverlayManager, GridOverlay, RulerOverlay, TextOverlay,
                            CrosshairOverlay, ShapeOverlay, PixelInfoOverlay)
import math

# Zoom clamps: without them zoom_in/zoom_out grow/shrink the factor
# without bound, and a huge factor makes Qt allocate an enormous pixmap
# (multi-GB) and freeze. MAX_SCALED_DIMENSION additionally caps any single
# scaled dimension regardless of the factor.
MIN_ZOOM_FACTOR = 0.05
MAX_ZOOM_FACTOR = 20.0
MAX_SCALED_DIMENSION = 16384


class ImageViewer(QScrollArea):
    image_clicked = Signal(int, int)
    zoom_changed = Signal(float)
    stroke_finished = Signal(list, tuple, int)  # image-space points, RGBA color, width
    overlay_state_changed = Signal()
    shape_finished = Signal(str, int, int, int, int)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignCenter)
        self.setAccessibleName(_("Image canvas"))
        # No hardcoded dark background here - the qdarkstyle/theme palette
        # styles the scroll area correctly in both light and dark themes.

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: transparent;")
        self.image_label.setMinimumSize(100, 100)

        self.setWidget(self.image_label)

        self.current_pixmap = None
        self.original_pixmap = None
        self._cached_qimage: QImage | None = None  # lazily converted, for pixel info
        self.zoom_factor = 1.0
        self.fit_to_window = True
        self.crop_mode = False
        self.crop_start = None
        self.crop_end = None
        self.crop_rect = None

        self.overlay_manager = OverlayManager()
        self._show_overlays = True
        self.pixel_info_mode = False
        self.shape_drawing_mode = None
        self.current_shape = None
        self.mouse_position = QPoint()

        # Canvas (freehand pen) drawing mode: paints directly onto the
        # image's pixels via core.editor.Editor.draw_stroke(), unlike the
        # non-destructive shape/text overlays above.
        self.drawing_mode = False
        self.pen_color = QColor(255, 0, 0)
        self.pen_width = 3
        self._stroke_points: list[QPoint] = []

        self.image_label.mousePressEvent = self._mouse_press_event
        self.image_label.mouseMoveEvent = self._mouse_move_event
        self.image_label.mouseReleaseEvent = self._mouse_release_event

        # Single reuse timer for fit-to-window refresh on resize - a fresh
        # singleShot per resize event piled up dozens of redundant redraws.
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(50)
        self._resize_timer.timeout.connect(self._on_resize_timeout)
        self._overlay_redraw_timer = QTimer(self)
        self._overlay_redraw_timer.setSingleShot(True)
        self._overlay_redraw_timer.timeout.connect(self._update_display)
        self.overlay_manager.changed.connect(self._on_overlay_changed)

    @property
    def show_overlays(self):
        return self._show_overlays

    @show_overlays.setter
    def show_overlays(self, visible):
        self._show_overlays = bool(visible)
        self._on_overlay_changed()

    def _on_overlay_changed(self):
        self.overlay_state_changed.emit()
        self._overlay_redraw_timer.start(0)

    def grid_overlay_visible(self):
        return self.show_overlays and any(overlay.visible for overlay in
                                         self.overlay_manager.get_overlays_by_type(GridOverlay))

    def ruler_overlay_visible(self):
        return self.show_overlays and any(overlay.visible for overlay in
                                         self.overlay_manager.get_overlays_by_type(RulerOverlay))

    def set_image(self, photon_image: PhotonImage):
        if photon_image:
            self.original_pixmap = pil_to_qpixmap(photon_image.current)
            self._cached_qimage = None
            self._update_display()

    def set_pixmap(self, pixmap: QPixmap):
        self.original_pixmap = pixmap
        self._cached_qimage = None
        self._update_display()

    def _get_qimage(self) -> QImage | None:
        """Cached QImage view of the original pixmap. Converting the whole
        pixmap via toImage() on every mouse-move (pixel info mode) was very
        expensive for large images."""
        if self._cached_qimage is None and self.original_pixmap and not self.original_pixmap.isNull():
            self._cached_qimage = self.original_pixmap.toImage()
        return self._cached_qimage

    def zoom_in(self):
        self.fit_to_window = False
        self.zoom_factor = min(MAX_ZOOM_FACTOR, self.zoom_factor * 1.25)
        self._update_display()
        self.zoom_changed.emit(self.zoom_factor)

    def zoom_out(self):
        self.fit_to_window = False
        self.zoom_factor = max(MIN_ZOOM_FACTOR, self.zoom_factor / 1.25)
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
        self.zoom_factor = max(MIN_ZOOM_FACTOR, min(MAX_ZOOM_FACTOR, factor))
        self._update_display()
        self.zoom_changed.emit(self.zoom_factor)

    def enable_crop_mode(self, enabled: bool):
        self.crop_mode = enabled
        if not enabled:
            self.crop_rect = None
            self.crop_start = None
            self.crop_end = None
            self._update_display()

    def set_shape_drawing_mode(self, shape_type: str):
        self.shape_drawing_mode = shape_type
        self.crop_mode = False
        if shape_type:
            self.drawing_mode = False

    def set_drawing_mode(self, enabled: bool):
        self.drawing_mode = enabled
        if enabled:
            self.crop_mode = False
            self.shape_drawing_mode = None
        self._stroke_points = []
        self._update_display()

    def set_pen_color(self, color: QColor):
        self.pen_color = color

    def set_pen_width(self, width: int):
        self.pen_width = max(1, width)

    def toggle_grid_overlay(self):
        self.set_grid_overlay_visible(not self.grid_overlay_visible())

    def set_grid_overlay_visible(self, visible):
        grid_overlays = self.overlay_manager.get_overlays_by_type(GridOverlay)
        if grid_overlays:
            for overlay in grid_overlays:
                overlay.set_visible(visible)
        elif visible:
            grid = GridOverlay()
            self.overlay_manager.add_overlay(grid)
        self._update_display()

    def toggle_ruler_overlay(self):
        self.set_ruler_overlay_visible(not self.ruler_overlay_visible())

    def set_ruler_overlay_visible(self, visible):
        ruler_overlays = self.overlay_manager.get_overlays_by_type(RulerOverlay)
        if ruler_overlays:
            for overlay in ruler_overlays:
                overlay.set_visible(visible)
        elif visible:
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
        self.set_pixel_info_mode(not self.pixel_info_mode)

    def set_pixel_info_mode(self, enabled):
        self.pixel_info_mode = bool(enabled)
        if not self.pixel_info_mode:
            pixel_overlays = self.overlay_manager.get_overlays_by_type(PixelInfoOverlay)
            for overlay in pixel_overlays:
                self.overlay_manager.remove_overlay(overlay)
        self._update_display()

    def clear_overlays(self):
        self.pixel_info_mode = False
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
        if event.button() == Qt.LeftButton:
            image_pos = self._screen_to_image_pos(event.pos())
            self.image_clicked.emit(image_pos.x(), image_pos.y())
        if self.crop_mode and event.button() == Qt.LeftButton:
            self.crop_start = event.pos()
            self.crop_end = event.pos()
        elif self.shape_drawing_mode and event.button() == Qt.LeftButton:
            image_pos = self._screen_to_image_pos(event.pos())
            self.current_shape = ShapeOverlay(self.shape_drawing_mode, image_pos, image_pos)
            self.overlay_manager.add_overlay(self.current_shape)
        elif self.drawing_mode and event.button() == Qt.LeftButton:
            self._stroke_points = [self._screen_to_image_pos(event.pos())]

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
        elif self.drawing_mode and self._stroke_points:
            self._stroke_points.append(self._screen_to_image_pos(event.pos()))
            self._update_display()
        elif self.pixel_info_mode and self.original_pixmap:
            self._update_pixel_info(event.pos())

    def _mouse_release_event(self, event: QMouseEvent):
        if self.crop_mode and self.crop_start and self.crop_end:
            x1, y1 = self.crop_start.x(), self.crop_start.y()
            x2, y2 = self.crop_end.x(), self.crop_end.y()

            if abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
                # Convert the widget-space rubber band to IMAGE pixel
                # coordinates (clamped to the image). The old code stored
                # the raw widget rect, so _apply_crop() cropped the wrong
                # region whenever the image was zoomed or centered.
                top_left = self._screen_to_image_pos(QPoint(min(x1, x2), min(y1, y2)))
                bottom_right = self._screen_to_image_pos(QPoint(max(x1, x2), max(y1, y2)))
                # Build from a size, not two corners: QRect(p1, p2) counts
                # both endpoints as inclusive pixels, while the PIL crop
                # box used by _apply_crop() is exclusive on right/bottom -
                # the mismatch cropped one extra row/column.
                self.crop_rect = QRect(
                    top_left,
                    QSize(bottom_right.x() - top_left.x(),
                          bottom_right.y() - top_left.y()),
                )
                self._update_display()
        elif self.shape_drawing_mode and self.current_shape:
            # Keep the shape tool active after releasing one shape so the
            # user can draw several in a row; the combo box stays in sync.
            # Deselect via the panel (or Escape) to exit the mode.
            shape = self.current_shape
            self.current_shape = None
            self.overlay_manager.remove_overlay(shape)
            self.shape_finished.emit(shape.shape_type, shape.start_point.x(), shape.start_point.y(), shape.end_point.x(), shape.end_point.y())
        elif self.drawing_mode and self._stroke_points:
            if len(self._stroke_points) > 1:
                points = [(p.x(), p.y()) for p in self._stroke_points]
                color = (self.pen_color.red(), self.pen_color.green(), self.pen_color.blue(), self.pen_color.alpha())
                self.stroke_finished.emit(points, color, self.pen_width)
            self._stroke_points = []

    def _screen_to_image_pos(self, screen_pos: QPoint) -> QPoint:
        """Map a widget-space position to image pixel coordinates.

        Uses the ACTUAL display scale (current pixmap size vs original),
        not self.zoom_factor - in fit-to-window mode those differ, which
        used to place strokes/shapes/pixel-info at wrong positions. Points
        outside the image are clamped to the nearest edge instead of
        collapsing to (0, 0)."""
        if not self.current_pixmap or not self.original_pixmap:
            return QPoint(0, 0)

        image_rect = self._get_image_rect()
        img_w = self.original_pixmap.width()
        img_h = self.original_pixmap.height()
        scale_x = self.current_pixmap.width() / img_w
        scale_y = self.current_pixmap.height() / img_h

        rel_x = (screen_pos.x() - image_rect.left()) / scale_x
        rel_y = (screen_pos.y() - image_rect.top()) / scale_y

        clamped_x = max(0, min(img_w - 1, int(rel_x)))
        clamped_y = max(0, min(img_h - 1, int(rel_y)))
        return QPoint(clamped_x, clamped_y)

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
        qimage = self._get_qimage()

        if qimage is not None and not qimage.isNull():
            if (0 <= image_pos.x() < qimage.width() and
                0 <= image_pos.y() < qimage.height()):

                pixel_color = qimage.pixelColor(image_pos.x(), image_pos.y())

                pixel_overlays = self.overlay_manager.get_overlays_by_type(PixelInfoOverlay)
                for overlay in pixel_overlays:
                    self.overlay_manager.remove_overlay(overlay)

                pixel_info = PixelInfoOverlay(image_pos, pixel_color)
                self.overlay_manager.add_overlay(pixel_info)
                self._update_display()

    def _update_display(self):
        self.overlay_state_changed.emit()
        if not self.original_pixmap:
            return

        if self.fit_to_window:
            viewport_size = self.viewport().size()
            self.current_pixmap = scale_pixmap_smooth(
                self.original_pixmap, viewport_size, True)
        else:
            # Cap the effective scale so a huge zoom factor can never ask
            # Qt to allocate an enormous pixmap.
            max_dim = max(self.original_pixmap.width(), self.original_pixmap.height())
            effective_zoom = min(self.zoom_factor, MAX_SCALED_DIMENSION / max_dim) if max_dim else self.zoom_factor
            new_size = QSize(
                max(1, int(self.original_pixmap.width() * effective_zoom)),
                max(1, int(self.original_pixmap.height() * effective_zoom)),
            )
            self.current_pixmap = scale_pixmap_smooth(
                self.original_pixmap, new_size, False)

        display_pixmap = QPixmap(self.current_pixmap)
        painter = QPainter(display_pixmap)

        if self.crop_mode and self.crop_start and self.crop_end:
            self._draw_crop_overlay(painter)

        actual_zoom = self.current_pixmap.width() / self.original_pixmap.width()

        # Keep zoom_factor (and the status-bar label) truthful in fit mode;
        # it used to stay at whatever the last manual zoom was.
        if self.fit_to_window and abs(actual_zoom - self.zoom_factor) > 0.001:
            self.zoom_factor = actual_zoom
            self.zoom_changed.emit(actual_zoom)

        if self.show_overlays:
            image_rect = QRect(0, 0, display_pixmap.width(), display_pixmap.height())
            self.overlay_manager.draw_all(painter, image_rect, actual_zoom)

        if self.drawing_mode and len(self._stroke_points) > 1:
            pen = QPen(self.pen_color, max(1, self.pen_width * actual_zoom), Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            scaled_points = [QPoint(int(p.x() * actual_zoom), int(p.y() * actual_zoom)) for p in self._stroke_points]
            for i in range(len(scaled_points) - 1):
                painter.drawLine(scaled_points[i], scaled_points[i + 1])

        painter.end()

        self.image_label.setPixmap(display_pixmap)
        self.image_label.resize(display_pixmap.size())

    def _update_crop_display(self):
        self._update_display()

    def _crop_display_rect(self) -> QRect | None:
        """The current rubber band in DISPLAY (pixmap-local) coordinates,
        so it can be drawn onto the display pixmap."""
        if not (self.crop_mode and self.crop_start and self.crop_end):
            return None
        image_rect = self._get_image_rect()
        start = self.crop_start - image_rect.topLeft()
        end = self.crop_end - image_rect.topLeft()
        return QRect(start, end).normalized()

    def _draw_crop_overlay(self, painter: QPainter):
        rect = self._crop_display_rect()
        if not rect:
            return

        overlay_color = QColor(0, 0, 0, 128)
        painter.fillRect(painter.device().rect(), overlay_color)

        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.fillRect(rect, Qt.transparent)

        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        pen = QPen(QColor(255, 255, 255), 2, Qt.DashLine)
        painter.setPen(pen)
        painter.drawRect(rect)

    def _on_resize_timeout(self):
        if self.fit_to_window:
            self._update_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_to_window:
            self._resize_timer.start()
