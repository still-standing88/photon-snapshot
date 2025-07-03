import os, sys
import app_guard

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QSplitter, QMenuBar, QToolBar, QStatusBar, QLabel,
                             QMessageBox, QFileDialog, QApplication)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon, QPixmap
from .viewer import ImageViewer
from .explorer import ExplorerWidget
from .editor_panel import EditorPanel
from core.editor import Editor
from core.image import PhotonImage
from core.utils import get_all_image_filter, get_save_formats



class MainWindow(QMainWindow):


    def __init__(self):
        super().__init__()
        self.editor = Editor()
        self.current_file_path = None
        self.recent_files_actions = []
        
        self.setWindowTitle("Photon Snapshot")
        self.setGeometry(100, 100, 1400, 900)
        self.setWindowIcon(QIcon(":icons/photon-snapshot.png"))
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """)
        
        self.setup_ui()
        self.setup_menu_bar()
        self.setup_toolbar()
        self.setup_status_bar()
        self.setup_shortcuts()
        self.connect_signals()
    
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        main_splitter = QSplitter(Qt.Horizontal)
        
        self.explorer = ExplorerWidget()
        
        center_splitter = QSplitter(Qt.Horizontal)
        
        self.viewer = ImageViewer()
        self.editor_panel = EditorPanel(self.editor)
        
        center_splitter.addWidget(self.viewer)
        center_splitter.addWidget(self.editor_panel)
        center_splitter.setSizes([800, 250])
        
        main_splitter.addWidget(self.explorer)
        main_splitter.addWidget(center_splitter)
        main_splitter.setSizes([300, 1100])
        
        main_layout.addWidget(main_splitter)
        central_widget.setLayout(main_layout)
    
    def setup_menu_bar(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #2b2b2b;
                color: #ffffff;
                border-bottom: 1px solid #404040;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 5px 10px;
            }
            QMenuBar::item:selected {
                background-color: #404040;
            }
            QMenu {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #404040;
            }
            QMenu::item {
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
        """)
        
        file_menu = menubar.addMenu("File")
        
        self.open_action = QAction("Open", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self.open_file)
        file_menu.addAction(self.open_action)
        
        file_menu.addSeparator()
        
        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.save_file)
        self.save_action.setEnabled(False)
        file_menu.addAction(self.save_action)
        
        self.save_as_action = QAction("Save As...", self)
        self.save_as_action.setShortcut(QKeySequence.SaveAs)
        self.save_as_action.triggered.connect(self.save_file_as)
        self.save_as_action.setEnabled(False)
        file_menu.addAction(self.save_as_action)
        
        file_menu.addSeparator()
        

        self.recent_files_menu = file_menu.addMenu("Recent Files")
        self.update_recent_files_menu()
        

        clear_recent_action = QAction("Clear Recent Files", self)
        clear_recent_action.triggered.connect(self.clear_recent_files)
        self.recent_files_menu.addSeparator()
        self.recent_files_menu.addAction(clear_recent_action)
        
        file_menu.addSeparator()
        
        hide_action = QAction("Minimize to tray", self)
        hide_action.setShortcut(QKeySequence("Ctrl+H"))
        hide_action.triggered.connect(self.hide)
        file_menu.addAction(hide_action)

        self.exit_action = QAction("Exit", self)
        self.exit_action.setShortcut(QKeySequence.Quit)
        self.exit_action.triggered.connect(self.close)
        file_menu.addAction(self.exit_action)
        
        edit_menu = menubar.addMenu("Edit")
        
        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setEnabled(False)
        edit_menu.addAction(self.undo_action)
        
        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.triggered.connect(self.redo)
        self.redo_action.setEnabled(False)
        edit_menu.addAction(self.redo_action)
        
        edit_menu.addSeparator()
        
        self.reset_action = QAction("Reset to Original", self)
        self.reset_action.triggered.connect(self.reset_image)
        self.reset_action.setEnabled(False)
        edit_menu.addAction(self.reset_action)
        
        view_menu = menubar.addMenu("View")
        
        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        self.zoom_in_action.triggered.connect(self.viewer.zoom_in)
        view_menu.addAction(self.zoom_in_action)
        
        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        self.zoom_out_action.triggered.connect(self.viewer.zoom_out)
        view_menu.addAction(self.zoom_out_action)
        
        self.zoom_fit_action = QAction("Fit to Window", self)
        self.zoom_fit_action.setShortcut(QKeySequence("Ctrl+0"))
        self.zoom_fit_action.triggered.connect(self.viewer.zoom_to_fit)
        view_menu.addAction(self.zoom_fit_action)
        
        self.zoom_actual_action = QAction("Actual Size", self)
        self.zoom_actual_action.setShortcut(QKeySequence("Ctrl+1"))
        self.zoom_actual_action.triggered.connect(self.viewer.zoom_to_actual)
        view_menu.addAction(self.zoom_actual_action)
        
        view_menu.addSeparator()
        
        self.toggle_explorer_action = QAction("Toggle Explorer", self)
        self.toggle_explorer_action.setShortcut(QKeySequence("F9"))
        self.toggle_explorer_action.triggered.connect(self.toggle_explorer_panel)
        view_menu.addAction(self.toggle_explorer_action)
        
        view_menu.addSeparator()
        
        self.toggle_grid_action = QAction("Toggle Grid", self)
        self.toggle_grid_action.setShortcut(QKeySequence("G"))
        self.toggle_grid_action.triggered.connect(self.viewer.toggle_grid_overlay)
        view_menu.addAction(self.toggle_grid_action)
        
        self.toggle_ruler_action = QAction("Toggle Ruler", self)
        self.toggle_ruler_action.setShortcut(QKeySequence("R"))
        self.toggle_ruler_action.triggered.connect(self.viewer.toggle_ruler_overlay)
        view_menu.addAction(self.toggle_ruler_action)
        
        self.toggle_pixel_info_action = QAction("Toggle Pixel Info", self)
        self.toggle_pixel_info_action.setShortcut(QKeySequence("I"))
        self.toggle_pixel_info_action.triggered.connect(self.viewer.toggle_pixel_info_mode)
        view_menu.addAction(self.toggle_pixel_info_action)
    
    def setup_toolbar(self):
        toolbar = self.addToolBar("Main")
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2b2b2b;
                border-bottom: 1px solid #404040;
                spacing: 3px;
            }
            QToolButton {
                background-color: #404040;
                border: 1px solid #555555;
                color: #ffffff;
                padding: 5px;
                border-radius: 3px;
            }
            QToolButton:hover {
                background-color: #505050;
            }
            QToolButton:pressed {
                background-color: #303030;
            }
            QToolButton:disabled {
                background-color: #2b2b2b;
                color: #666666;
            }
        """)
        
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)
        toolbar.addSeparator()
        toolbar.addAction(self.zoom_in_action)
        toolbar.addAction(self.zoom_out_action)
        toolbar.addAction(self.zoom_fit_action)
        toolbar.addAction(self.zoom_actual_action)
    
    def setup_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #2b2b2b;
                color: #ffffff;
                border-top: 1px solid #404040;
            }
        """)
        
        self.status_label = QLabel("Ready")
        self.zoom_label = QLabel("Zoom: 100%")
        self.image_info_label = QLabel("")
        
        self.status_bar.addWidget(self.status_label)
        self.status_bar.addPermanentWidget(self.image_info_label)
        self.status_bar.addPermanentWidget(self.zoom_label)
    
    def setup_shortcuts(self):
        pass
    
    def connect_signals(self):
        self.explorer.file_selected.connect(self.load_image_file)
        self.explorer.open_image.connect(self.load_image_file)
        self.viewer.zoom_changed.connect(self._update_zoom_display)
        self.editor.set_state_change_callback(self._on_editor_state_changed)
        self.editor_panel.crop_panel.crop_mode_toggled.connect(self.viewer.enable_crop_mode)
        self.editor_panel.crop_panel.crop_applied.connect(self._apply_crop)
        
        self.explorer.explorer.recent_files_updated.connect(lambda: self.update_recent_files_menu())
        
        if hasattr(self.editor_panel, 'overlay_panel'):
            self.editor_panel.overlay_panel.grid_toggled.connect(self.viewer.toggle_grid_overlay)
            self.editor_panel.overlay_panel.ruler_toggled.connect(self.viewer.toggle_ruler_overlay)
            self.editor_panel.overlay_panel.pixel_info_toggled.connect(self.viewer.toggle_pixel_info_mode)
            self.editor_panel.overlay_panel.text_overlay_requested.connect(self.viewer.add_text_overlay)
            self.editor_panel.overlay_panel.shape_mode_changed.connect(self._on_shape_mode_changed)
            self.editor_panel.overlay_panel.overlays_cleared.connect(self.viewer.clear_overlays)
    
    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", get_all_image_filter())
        self._load_file(file_path)

    def load_file(self, file_path):
        if file_path:
            self.load_image_file(file_path)
    
    def load_image_file(self, file_path: str):
        try:
            if self.editor.load_image_from_file(file_path):
                self.current_file_path = file_path
                self.viewer.set_image(self.editor.current_image)
                self.editor_panel.reset_controls()
                self._update_window_title()
                self._update_image_info()
                self.status_label.setText(f"Loaded: {os.path.basename(file_path)}")
                
                self.explorer.explorer.add_recent_file(file_path)
            else:
                QMessageBox.warning(self, "Error", "Failed to load image")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading image: {str(e)}")
    

    def cli_load_file(self, ipc_msg_data:dict[str, str]):
        self.load_file(ipc_msg_data["msg_data"])

    def save_file(self):
        if self.current_file_path and self.editor.current_image:
            try:
                self.editor.save_image(self.current_file_path)
                self.status_label.setText("Image saved")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error saving image: {str(e)}")
    
    def save_file_as(self):
        if not self.editor.current_image:
            return
        
        formats = get_save_formats()
        filter_str = ";;".join([f"{fmt} files (*.{fmt.lower()})" for fmt in formats])
        
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Save Image As", "", filter_str)
        
        if file_path:
            try:
                format_name = selected_filter.split()[0]
                self.editor.save_image(file_path, format_name)
                self.current_file_path = file_path
                self._update_window_title()
                self.status_label.setText(f"Image saved as {os.path.basename(file_path)}")
                

                self.explorer.explorer.add_recent_file(file_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error saving image: {str(e)}")
    
    def undo(self):
        if self.editor.undo():
            self.viewer.set_image(self.editor.current_image)
            self.status_label.setText("Undone")
    
    def redo(self):
        if self.editor.redo():
            self.viewer.set_image(self.editor.current_image)
            self.status_label.setText("Redone")
    
    def reset_image(self):
        if self.editor.current_image:
            self.editor.reset_to_original()
            self.viewer.set_image(self.editor.current_image)
            self.editor_panel.reset_controls()
            self.status_label.setText("Reset to original")
    
    def _apply_crop(self):
        crop_rect = self.viewer.get_crop_rect()
        if crop_rect and self.editor.current_image:
            box = (crop_rect.x(), crop_rect.y(), 
                  crop_rect.x() + crop_rect.width(), 
                  crop_rect.y() + crop_rect.height())
            self.editor.crop(box)
            self.viewer.set_image(self.editor.current_image)
            self.viewer.enable_crop_mode(False)
            self.editor_panel.crop_panel.crop_mode_checkbox.setChecked(False)
    
    def _on_shape_mode_changed(self, shape_type: str):
        if shape_type:
            self.viewer.set_shape_drawing_mode(shape_type)
        else:
            self.viewer.set_shape_drawing_mode(None)
    
    def toggle_explorer_panel(self):
        if self.explorer.isVisible():
            self.explorer.hide()
        else:
            self.explorer.show()
    
    def _update_zoom_display(self, zoom_factor: float):
        self.zoom_label.setText(f"Zoom: {zoom_factor * 100:.0f}%")
    
    def _update_window_title(self):
        if self.current_file_path:
            filename = os.path.basename(self.current_file_path)
            self.setWindowTitle(f"Photon Snapshot - {filename}")
        else:
            self.setWindowTitle("Photon Snapshot")
    
    def _update_image_info(self):
        if self.editor.current_image:
            width, height = self.editor.current_image.size
            self.image_info_label.setText(f"{width} × {height}")
        else:
            self.image_info_label.setText("")
    
    def _on_editor_state_changed(self):
        has_image = self.editor.current_image is not None
        can_undo = self.editor.can_undo()
        can_redo = self.editor.can_redo()
        
        self.save_action.setEnabled(has_image)
        self.save_as_action.setEnabled(has_image)
        self.reset_action.setEnabled(has_image)
        self.undo_action.setEnabled(can_undo)
        self.redo_action.setEnabled(can_redo)
        
        if self.editor.current_image:
            self.viewer.set_image(self.editor.current_image)
            self._update_image_info()
    
    def update_recent_files_menu(self):
        actions = self.recent_files_menu.actions()
        
        separator_action = None
        clear_action = None
        recent_file_actions = []
        
        for action in actions:
            if action.isSeparator():
                separator_action = action
            elif action.text() == "Clear Recent Files":
                clear_action = action
            else:
                recent_file_actions.append(action)
        
        for action in recent_file_actions:
            self.recent_files_menu.removeAction(action)

        recent_files = self.explorer.explorer.get_recent_files()
        
        if not recent_files:
            no_files_action = QAction("No recent files", self)
            no_files_action.setEnabled(False)
            
            if separator_action:
                self.recent_files_menu.insertAction(separator_action, no_files_action)
            else:
                self.recent_files_menu.addAction(no_files_action)
        else:
            for i, file_path in enumerate(recent_files):
                file_name = os.path.basename(file_path)
                if len(file_name) > 40:
                    file_name = file_name[:37] + "..."
                
                action_text = f"{i + 1}. {file_name}"
                action = QAction(action_text, self)
                action.setToolTip(file_path)
                action.triggered.connect(lambda path=file_path: self.open_recent_file(file_path))
                
                if separator_action:
                    self.recent_files_menu.insertAction(separator_action, action)
                else:
                    self.recent_files_menu.addAction(action)
    
    def open_recent_file(self, file_path: str):

        if os.path.exists(file_path):
            self.load_image_file(file_path)
        else:
            QMessageBox.warning(self, "File Not Found", 
                              f"The file '{file_path}' no longer exists and will be removed from recent files.")


            self.update_recent_files_menu()
    
    def clear_recent_files(self):
        self.explorer.explorer.clear_recent_files()
        self.update_recent_files_menu()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.viewer.zoom_to_fit()
        elif event.key() == Qt.Key_Escape:
            if self.viewer.crop_mode:
                self.viewer.enable_crop_mode(False)
                self.editor_panel.crop_panel.crop_mode_checkbox.setChecked(False)
            elif hasattr(self.viewer, 'shape_drawing_mode') and self.viewer.shape_drawing_mode:
                self.viewer.set_shape_drawing_mode(None)

                if hasattr(self.editor_panel, 'overlay_panel'):
                    for btn in [self.editor_panel.overlay_panel.rectangle_btn,
                               self.editor_panel.overlay_panel.circle_btn,
                               self.editor_panel.overlay_panel.line_btn]:
                        btn.setChecked(False)
        elif event.key() == Qt.Key_G and event.modifiers() == Qt.NoModifier:
            self.viewer.toggle_grid_overlay()
        elif event.key() == Qt.Key_R and event.modifiers() == Qt.NoModifier:
            self.viewer.toggle_ruler_overlay()
        elif event.key() == Qt.Key_I and event.modifiers() == Qt.NoModifier:
            self.viewer.toggle_pixel_info_mode()
        elif event.key() == Qt.Key_C and event.modifiers() == Qt.AltModifier:
            if hasattr(self.viewer, 'clear_overlays'):
                self.viewer.clear_overlays()
        else:
            super().keyPressEvent(event)
