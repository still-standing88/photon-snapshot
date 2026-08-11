import os

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QMessageBox, QFileDialog, QApplication, QSizePolicy)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon

from .viewer import ImageViewer
from .explorer import ExplorerWidget
from .editor_panel import EditorPanel
from .managers.dock_manager import DockManager
from .managers.focus_navigation_manager import FocusNavigationManager
from .dialogs.hotkeys_dialog import HotkeysDialog
from .dialogs.preferences_dialog import PreferencesDialog
from .dialogs.about_dialog import AboutDialog
from core.editor import Editor
from core.utils import get_all_image_filter, get_save_formats
from gui_controls.common_controls import TabableLabel
from app_config import key_config
from app_config.prefs import prefs


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.editor = Editor()
        self.current_file_path = None
        self.recent_files_actions = []
        self.focusable_widgets = []
        self.current_focus_index = -1

        self.setWindowTitle("Photon Snapshot")
        self.setGeometry(100, 100, 1400, 900)
        self.setWindowIcon(QIcon(":icons/photon-snapshot.png"))
        self.setAccessibleName(_("Photon Snapshot main window"))
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #ffffff; }
        """)

        self.dock_manager = DockManager(self)
        self.focus_manager = FocusNavigationManager(self)

        self.setup_ui()
        self.setup_dock_widgets()
        self.setup_menu_bar()
        self.setup_toolbar()
        self.setup_status_bar()
        self.setup_shortcuts()
        self.connect_signals()

        self.dock_manager.restore_window_state()

    # -------------------------------------------------------------- UI ----
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # A single QSplitter (not fixed-width panes) so the viewer and the
        # editing-tools panel resize together with the window - and each
        # other, since either side can also be dragged - satisfying the
        # responsive-layout requirement. The Explorer lives in its own
        # QDockWidget (see setup_dock_widgets), independent of this splitter.
        self.center_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.center_splitter.setObjectName("centerSplitter")

        self.viewer = ImageViewer()
        self.viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.editor_panel = EditorPanel(self.editor)

        self.center_splitter.addWidget(self.viewer)
        self.center_splitter.addWidget(self.editor_panel)
        self.center_splitter.setStretchFactor(0, 1)
        self.center_splitter.setStretchFactor(1, 0)
        self.center_splitter.setSizes([1000, 300])

        main_layout.addWidget(self.center_splitter)
        central_widget.setLayout(main_layout)

    def setup_dock_widgets(self):
        self.explorer_widget = ExplorerWidget()
        self.dock_manager.setup_dock_widgets()

    # ---------------------------------------------------------- menubar ----
    def setup_menu_bar(self):
        menubar = self.menuBar()
        menubar.setAccessibleName(_("Main menu"))

        # ------------------------------------------------------- File ----
        file_menu = menubar.addMenu(_("&File"))

        self.open_action = QAction(_("&Open..."), self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.setAccessibleName(_("Open an image file"))
        self.open_action.triggered.connect(self.open_file)
        key_config.bind_action("Main Window", "Open file", self.open_action)
        file_menu.addAction(self.open_action)

        self.open_folder_action = QAction(_("Open &Folder..."), self)
        self.open_folder_action.setAccessibleName(_("Open a folder in the explorer"))
        self.open_folder_action.triggered.connect(self.open_folder)
        key_config.bind_action("Main Window", "Open folder", self.open_folder_action)
        file_menu.addAction(self.open_folder_action)

        file_menu.addSeparator()

        self.save_action = QAction(_("&Save"), self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self.save_file)
        self.save_action.setEnabled(False)
        key_config.bind_action("Main Window", "Save", self.save_action)
        file_menu.addAction(self.save_action)

        self.save_as_action = QAction(_("Save &As..."), self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(self.save_file_as)
        self.save_as_action.setEnabled(False)
        key_config.bind_action("Main Window", "Save As", self.save_as_action)
        file_menu.addAction(self.save_as_action)

        file_menu.addSeparator()

        self.recent_files_menu = file_menu.addMenu(_("Recent Files"))
        self.update_recent_files_menu()

        clear_recent_action = QAction(_("Clear Recent Files"), self)
        clear_recent_action.triggered.connect(self.clear_recent_files)
        self.recent_files_menu.addSeparator()
        self.recent_files_menu.addAction(clear_recent_action)

        file_menu.addSeparator()

        hide_action = QAction(_("Minimize to Tray"), self)
        hide_action.triggered.connect(self._minimize_to_tray)
        key_config.bind_action("Main Window", "Minimize to Tray", hide_action)
        file_menu.addAction(hide_action)

        self.exit_action = QAction(_("E&xit"), self)
        self.exit_action.triggered.connect(self.close_application)
        key_config.bind_action("Main Window", "Exit", self.exit_action)
        file_menu.addAction(self.exit_action)

        # ------------------------------------------------------- Edit ----
        edit_menu = menubar.addMenu(_("&Edit"))

        self.undo_action = QAction(_("&Undo"), self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self.undo)
        self.undo_action.setEnabled(False)
        key_config.bind_action("Main Window", "Undo", self.undo_action)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction(_("&Redo"), self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self.redo)
        self.redo_action.setEnabled(False)
        key_config.bind_action("Main Window", "Redo", self.redo_action)
        edit_menu.addAction(self.redo_action)

        edit_menu.addSeparator()

        self.reset_action = QAction(_("&Reset to Original"), self)
        self.reset_action.triggered.connect(self.reset_image)
        self.reset_action.setEnabled(False)
        key_config.bind_action("Main Window", "Reset to Original", self.reset_action)
        edit_menu.addAction(self.reset_action)

        # ------------------------------------------------------- View ----
        view_menu = menubar.addMenu(_("&View"))

        self.zoom_in_action = QAction(_("Zoom &In"), self)
        self.zoom_in_action.triggered.connect(self.viewer.zoom_in)
        key_config.bind_action("Main Window", "Zoom In", self.zoom_in_action)
        view_menu.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction(_("Zoom &Out"), self)
        self.zoom_out_action.triggered.connect(self.viewer.zoom_out)
        key_config.bind_action("Main Window", "Zoom Out", self.zoom_out_action)
        view_menu.addAction(self.zoom_out_action)

        self.zoom_fit_action = QAction(_("&Fit to Window"), self)
        self.zoom_fit_action.triggered.connect(self.viewer.zoom_to_fit)
        key_config.bind_action("Main Window", "Fit to Window", self.zoom_fit_action)
        view_menu.addAction(self.zoom_fit_action)

        self.zoom_actual_action = QAction(_("&Actual Size"), self)
        self.zoom_actual_action.triggered.connect(self.viewer.zoom_to_actual)
        key_config.bind_action("Main Window", "Actual Size", self.zoom_actual_action)
        view_menu.addAction(self.zoom_actual_action)

        view_menu.addSeparator()

        self.show_explorer_action = QAction(_("&Explorer"), self)
        self.show_explorer_action.setCheckable(True)
        self.show_explorer_action.setAccessibleName(_("Show or hide the Explorer panel"))
        self.show_explorer_action.toggled.connect(self.dock_manager.toggle_explorer)
        key_config.bind_action("Main Window", "Toggle Explorer", self.show_explorer_action)
        view_menu.addAction(self.show_explorer_action)

        self.show_toolbar_action = QAction(_("&Toolbar"), self)
        self.show_toolbar_action.setCheckable(True)
        self.show_toolbar_action.setChecked(True)
        self.show_toolbar_action.toggled.connect(self._toggle_toolbar)
        view_menu.addAction(self.show_toolbar_action)

        self.show_statusbar_action = QAction(_("Status &Bar"), self)
        self.show_statusbar_action.setCheckable(True)
        self.show_statusbar_action.setChecked(True)
        self.show_statusbar_action.toggled.connect(self._toggle_statusbar)
        view_menu.addAction(self.show_statusbar_action)

        view_menu.addSeparator()

        self.toggle_grid_action = QAction(_("Toggle &Grid"), self)
        self.toggle_grid_action.triggered.connect(self.viewer.toggle_grid_overlay)
        key_config.bind_action("Viewer", "Toggle Grid Overlay", self.toggle_grid_action)
        view_menu.addAction(self.toggle_grid_action)

        self.toggle_ruler_action = QAction(_("Toggle &Ruler"), self)
        self.toggle_ruler_action.triggered.connect(self.viewer.toggle_ruler_overlay)
        key_config.bind_action("Viewer", "Toggle Ruler Overlay", self.toggle_ruler_action)
        view_menu.addAction(self.toggle_ruler_action)

        self.toggle_pixel_info_action = QAction(_("Toggle &Pixel Info"), self)
        self.toggle_pixel_info_action.triggered.connect(self.viewer.toggle_pixel_info_mode)
        key_config.bind_action("Viewer", "Toggle Pixel Info", self.toggle_pixel_info_action)
        view_menu.addAction(self.toggle_pixel_info_action)

        # ---------------------------------------------------- Options ----
        options_menu = menubar.addMenu(_("&Options"))

        preferences_action = QAction(_("&Preferences..."), self)
        preferences_action.triggered.connect(self.open_preferences)
        key_config.bind_action("Main Window", "Preferences", preferences_action)
        options_menu.addAction(preferences_action)

        hotkeys_action = QAction(_("&Hotkeys..."), self)
        hotkeys_action.triggered.connect(self.open_hotkeys_dialog)
        key_config.bind_action("Main Window", "Hotkeys Dialog", hotkeys_action)
        options_menu.addAction(hotkeys_action)

        options_menu.addSeparator()

        check_updates_action = QAction(_("Check for &Updates..."), self)
        check_updates_action.triggered.connect(self.check_for_updates)
        key_config.bind_action("Main Window", "Check for Updates", check_updates_action)
        options_menu.addAction(check_updates_action)

        about_action = QAction(_("&About Photon Snapshot"), self)
        about_action.triggered.connect(self.open_about_dialog)
        options_menu.addAction(about_action)

    # ---------------------------------------------------------- toolbar ----
    def setup_toolbar(self):
        self.toolbar = self.addToolBar(_("Main"))
        self.toolbar.setObjectName("mainToolbar")
        self.toolbar.setAccessibleName(_("Main toolbar"))
        self.toolbar.setStyleSheet("""
            QToolBar { background-color: #2b2b2b; border-bottom: 1px solid #404040; spacing: 3px; }
            QToolButton { background-color: #404040; border: 1px solid #555555; color: #ffffff; padding: 5px; border-radius: 3px; }
            QToolButton:hover { background-color: #505050; }
            QToolButton:pressed { background-color: #303030; }
            QToolButton:disabled { background-color: #2b2b2b; color: #666666; }
        """)

        self.toolbar.addAction(self.open_action)
        self.toolbar.addAction(self.save_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.zoom_in_action)
        self.toolbar.addAction(self.zoom_out_action)
        self.toolbar.addAction(self.zoom_fit_action)
        self.toolbar.addAction(self.zoom_actual_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.show_explorer_action)

    # -------------------------------------------------------- statusbar ----
    def setup_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.setObjectName("mainStatusBar")
        self.status_bar.setAccessibleName(_("Status bar"))
        self.status_bar.setStyleSheet("""
            QStatusBar { background-color: #2b2b2b; color: #ffffff; border-top: 1px solid #404040; }
        """)

        # TabableLabel, not QLabel: every info-bearing label in the status
        # bar must be reachable by keyboard/screen reader (accessibility
        # requirement of the snapshot rewrite).
        self.status_label = TabableLabel(_("Ready"), accessible_name=_("Status message"))
        self.zoom_label = TabableLabel(_("Zoom: 100%"), accessible_name=_("Current zoom level"))
        self.image_info_label = TabableLabel("", accessible_name=_("Image dimensions"))

        self.status_bar.addWidget(self.status_label)
        self.status_bar.addPermanentWidget(self.image_info_label)
        self.status_bar.addPermanentWidget(self.zoom_label)

    def setup_shortcuts(self):
        key_config.make_shortcut("Main Window", "Next Pane", self, self.focus_manager.focus_next_widget)
        key_config.make_shortcut("Main Window", "Previous Pane", self, self.focus_manager.focus_previous_widget)
        key_config.make_shortcut("Main Window", "Focus Explorer", self, lambda: self._focus_pane(self.explorer_widget))
        key_config.make_shortcut("Main Window", "Focus Viewer", self, lambda: self._focus_pane(self.viewer))

    def _focus_pane(self, widget):
        if widget is self.explorer_widget and not self.explorer_dock.isVisible():
            self.show_explorer_action.setChecked(True)
        widget.setFocus()

    # -------------------------------------------------------- signals ----
    def connect_signals(self):
        self.explorer_widget.file_selected.connect(self.load_image_file)
        self.explorer_widget.open_image.connect(self.load_image_file)
        self.viewer.zoom_changed.connect(self._update_zoom_display)
        self.viewer.stroke_finished.connect(self._on_stroke_finished)
        self.editor.set_state_change_callback(self._on_editor_state_changed)
        self.editor_panel.crop_panel.crop_mode_toggled.connect(self.viewer.enable_crop_mode)
        self.editor_panel.crop_panel.crop_applied.connect(self._apply_crop)

        self.editor_panel.draw_panel.drawing_mode_toggled.connect(self.viewer.set_drawing_mode)
        self.editor_panel.draw_panel.pen_color_changed.connect(self.viewer.set_pen_color)
        self.editor_panel.draw_panel.pen_width_changed.connect(self.viewer.set_pen_width)

        self.explorer_widget.explorer.recent_files_updated.connect(lambda *_: self.update_recent_files_menu())

        overlay_panel = self.editor_panel.overlay_panel
        overlay_panel.grid_toggled.connect(self.viewer.toggle_grid_overlay)
        overlay_panel.ruler_toggled.connect(self.viewer.toggle_ruler_overlay)
        overlay_panel.pixel_info_toggled.connect(self.viewer.toggle_pixel_info_mode)
        overlay_panel.text_overlay_requested.connect(self.viewer.add_text_overlay)
        overlay_panel.shape_mode_changed.connect(self._on_shape_mode_changed)
        overlay_panel.overlays_cleared.connect(self.viewer.clear_overlays)

    def on_explorer_visibility_changed(self, visible: bool):
        if self.show_explorer_action.isChecked() != visible:
            self.show_explorer_action.blockSignals(True)
            self.show_explorer_action.setChecked(visible)
            self.show_explorer_action.blockSignals(False)

    def _toggle_toolbar(self, checked: bool):
        self.toolbar.setVisible(checked)
        self.dock_manager.update_focusable_widgets()

    def _toggle_statusbar(self, checked: bool):
        self.status_bar.setVisible(checked)
        self.dock_manager.update_focusable_widgets()

    # ---------------------------------------------------------- files ----
    def open_file(self):
        file_path, _sel = QFileDialog.getOpenFileName(self, _("Open Image"), "", get_all_image_filter())
        if file_path:
            self.load_image_file(file_path)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, _("Open Folder"), "")
        if folder:
            self.show_explorer_action.setChecked(True)
            self.explorer_widget.explorer.navigate_to(folder)

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
                self.status_label.setText(_("Loaded: {name}").format(name=os.path.basename(file_path)))
                self.explorer_widget.explorer.add_recent_file(file_path)
            else:
                QMessageBox.warning(self, _("Error"), _("Failed to load image"))
        except Exception as e:
            QMessageBox.critical(self, _("Error"), _("Error loading image: {error}").format(error=str(e)))

    def cli_load_file(self, ipc_msg_data: dict):
        self.load_file(ipc_msg_data["msg_data"])

    def save_file(self):
        if self.current_file_path and self.editor.current_image:
            try:
                self.editor.save_image(self.current_file_path)
                self.status_label.setText(_("Image saved"))
            except Exception as e:
                QMessageBox.critical(self, _("Error"), _("Error saving image: {error}").format(error=str(e)))

    def save_file_as(self):
        if not self.editor.current_image:
            return

        formats = get_save_formats()
        filter_str = ";;".join([f"{fmt} files (*.{fmt.lower()})" for fmt in formats])
        file_path, selected_filter = QFileDialog.getSaveFileName(self, _("Save Image As"), "", filter_str)
        if not file_path:
            return

        if prefs.get("confirm_on_overwrite", True) and os.path.exists(file_path):
            reply = QMessageBox.question(
                self, _("Overwrite File?"),
                _("{name} already exists. Overwrite it?").format(name=os.path.basename(file_path)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            format_name = selected_filter.split()[0]
            self.editor.save_image(file_path, format_name)
            self.current_file_path = file_path
            self._update_window_title()
            self.status_label.setText(_("Image saved as {name}").format(name=os.path.basename(file_path)))
            self.explorer_widget.explorer.add_recent_file(file_path)
        except Exception as e:
            QMessageBox.critical(self, _("Error"), _("Error saving image: {error}").format(error=str(e)))

    def undo(self):
        if self.editor.undo():
            self.viewer.set_image(self.editor.current_image)
            self.status_label.setText(_("Undone"))

    def redo(self):
        if self.editor.redo():
            self.viewer.set_image(self.editor.current_image)
            self.status_label.setText(_("Redone"))

    def reset_image(self):
        if self.editor.current_image:
            self.editor.reset_to_original()
            self.viewer.set_image(self.editor.current_image)
            self.editor_panel.reset_controls()
            self.status_label.setText(_("Reset to original"))

    def _apply_crop(self):
        crop_rect = self.viewer.get_crop_rect()
        if crop_rect and self.editor.current_image:
            box = (crop_rect.x(), crop_rect.y(), crop_rect.x() + crop_rect.width(), crop_rect.y() + crop_rect.height())
            self.editor.crop(box)
            self.viewer.set_image(self.editor.current_image)
            self.viewer.enable_crop_mode(False)
            self.editor_panel.crop_panel.crop_mode_checkbox.setChecked(False)

    def _on_shape_mode_changed(self, shape_type: str):
        self.viewer.set_shape_drawing_mode(shape_type or None)

    def _on_stroke_finished(self, points: list, color: tuple, width: int):
        if self.editor.current_image:
            self.editor.draw_stroke(points, color, width)
            self.viewer.set_image(self.editor.current_image)
            self.status_label.setText(_("Stroke drawn"))

    def _update_zoom_display(self, zoom_factor: float):
        self.zoom_label.setText(_("Zoom: {percent:.0f}%").format(percent=zoom_factor * 100))

    def _update_window_title(self):
        if self.current_file_path:
            self.setWindowTitle(f"Photon Snapshot - {os.path.basename(self.current_file_path)}")
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
        self.save_action.setEnabled(has_image)
        self.save_as_action.setEnabled(has_image)
        self.reset_action.setEnabled(has_image)
        self.undo_action.setEnabled(self.editor.can_undo())
        self.redo_action.setEnabled(self.editor.can_redo())

        if self.editor.current_image:
            self.viewer.set_image(self.editor.current_image)
            self._update_image_info()

    # ---------------------------------------------------- recent files ----
    def update_recent_files_menu(self):
        actions = self.recent_files_menu.actions()
        separator_action = None
        recent_file_actions = []
        for action in actions:
            if action.isSeparator():
                separator_action = action
            elif action.data() == "clear":
                pass
            else:
                recent_file_actions.append(action)
        for action in recent_file_actions:
            self.recent_files_menu.removeAction(action)

        recent_files = self.explorer_widget.explorer.get_recent_files()

        if not recent_files:
            no_files_action = QAction(_("No recent files"), self)
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
                action = QAction(f"{i + 1}. {file_name}", self)
                action.setToolTip(file_path)
                action.triggered.connect(lambda checked=False, path=file_path: self.open_recent_file(path))
                if separator_action:
                    self.recent_files_menu.insertAction(separator_action, action)
                else:
                    self.recent_files_menu.addAction(action)

    def open_recent_file(self, file_path: str):
        if os.path.exists(file_path):
            self.load_image_file(file_path)
        else:
            QMessageBox.warning(
                self, _("File Not Found"),
                _("The file '{path}' no longer exists and will be removed from recent files.").format(path=file_path),
            )
            self.explorer_widget.explorer.remove_recent_file(file_path)
            self.update_recent_files_menu()

    def clear_recent_files(self):
        self.explorer_widget.explorer.clear_recent_files()
        self.update_recent_files_menu()

    # --------------------------------------------------------- dialogs ----
    def open_hotkeys_dialog(self):
        HotkeysDialog(self).exec()

    def open_preferences(self):
        PreferencesDialog(self).exec()

    def open_about_dialog(self):
        AboutDialog(self).exec()

    def check_for_updates(self):
        from update_checker import UpdateChecker
        UpdateChecker.instance(parent=self).check_now(silent=False)

    # -------------------------------------------------------- tray/close ----
    def _minimize_to_tray(self):
        self.dock_manager.hide_floating_docks()
        self.hide()

    def close_application(self):
        self.dock_manager.save_window_state()
        QApplication.quit()

    def closeEvent(self, event):
        if prefs.get("minimize_to_tray_on_close", False):
            event.ignore()
            self._minimize_to_tray()
            return
        self.dock_manager.save_window_state()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.viewer.crop_mode:
                self.viewer.enable_crop_mode(False)
                self.editor_panel.crop_panel.crop_mode_checkbox.setChecked(False)
            elif self.viewer.shape_drawing_mode:
                self.viewer.set_shape_drawing_mode(None)
                for btn in self.editor_panel.overlay_panel._shape_buttons.values():
                    btn.setChecked(False)
            elif self.viewer.drawing_mode:
                self.editor_panel.draw_panel.draw_mode_checkbox.setChecked(False)
        else:
            super().keyPressEvent(event)
