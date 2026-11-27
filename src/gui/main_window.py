import os

from PIL import Image as PILImage

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QSplitter, QMessageBox, QFileDialog, QSizePolicy)
from PySide6.QtCore import Qt, QTimer, QSignalBlocker
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QIcon

from .viewer import ImageViewer
from .explorer import ExplorerWidget
from .editor_panel import EditorPanel
from .managers.dock_manager import DockManager
from .managers.focus_navigation_manager import FocusNavigationManager
from .dialogs.hotkeys_dialog import HotkeysDialog
from .dialogs.preferences_dialog import PreferencesDialog
from .dialogs.about_dialog import AboutDialog
from core.editor import Editor
from core.image import PhotonImage
from core.utils import get_all_image_filter, get_save_formats
from gui_controls.common_controls import TabableLabel
from app_config import key_config
from app_config.prefs import prefs
from .animation_workspace import AnimationWorkspace


class MainWindow(QMainWindow, AnimationWorkspace):

    def __init__(self):
        super().__init__()
        self.editor = Editor()
        self.initialize_workspace()
        self.current_file_path = None
        self.recent_files_actions = []
        self.focusable_widgets = []
        self.current_focus_index = -1
        self._force_exit = False

        self.setWindowTitle("Photon Snapshot")
        self.setGeometry(100, 100, 1400, 900)
        self.setWindowIcon(QIcon(":icons/photon-snapshot.png"))
        self.setAccessibleName("Photon Snapshot")
        # No hardcoded QMainWindow stylesheet here - colors come from the
        # app-wide qdarkstyle stylesheet applied by utilities.theme_manager
        # so the dark/light/system theme setting actually takes effect.

        self.dock_manager = DockManager(self)
        self.focus_manager = FocusNavigationManager(self)

        self.setup_ui()
        self.setup_dock_widgets()
        self.setup_menu_bar()
        self.setup_toolbar()
        self.setup_status_bar()
        self.add_workspace_actions()
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

        self.center_splitter.addWidget(self.build_canvas_workspace())
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
        self.file_menu = file_menu

        self.new_action = QAction(_("&New..."), self)
        self.new_action.setText(_("New Image..."))
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_action.setStatusTip(_("Create a new blank image"))
        self.new_action.triggered.connect(self.new_file)
        key_config.bind_action("Main Window", "New", self.new_action)
        self.new_menu = file_menu.addMenu(_("&New"))
        self.new_menu.addAction(self.new_action)

        self.open_action = QAction(_("&Open..."), self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.setStatusTip(_("Open an image file"))
        self.open_action.triggered.connect(self.open_file)
        key_config.bind_action("Main Window", "Open file", self.open_action)
        file_menu.addAction(self.open_action)

        self.open_folder_action = QAction(_("Open &Folder..."), self)
        self.open_folder_action.setStatusTip(_("Open a folder in the explorer"))
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
        clear_recent_action.setData("clear")
        clear_recent_action.triggered.connect(self.clear_recent_files)
        key_config.bind_action("Main Window", "Clear Recent Files", clear_recent_action)
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
        self.edit_menu = edit_menu

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
        edit_menu.addMenu(self.editor_panel.effect_menu)
        self.coordinate_crop_action = edit_menu.addAction(
            _("Crop by Coordinates..."), self.editor_panel.crop_by_coordinates
        )
        self.coordinate_crop_action.setEnabled(False)

        # ------------------------------------------------------- View ----
        view_menu = menubar.addMenu(_("&View"))
        self.view_menu = view_menu

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
        self.show_explorer_action.setStatusTip(_("Show or hide the Explorer panel"))
        self.show_explorer_action.toggled.connect(self.dock_manager.toggle_explorer)
        key_config.bind_action("Main Window", "Toggle Explorer", self.show_explorer_action)
        view_menu.addAction(self.show_explorer_action)

        self.show_toolbar_action = QAction(_("&Toolbar"), self)
        self.show_toolbar_action.setCheckable(True)
        self.show_toolbar_action.setChecked(True)
        self.show_toolbar_action.toggled.connect(self._toggle_toolbar)
        key_config.bind_action("Main Window", "Toggle Toolbar", self.show_toolbar_action)
        view_menu.addAction(self.show_toolbar_action)

        self.show_statusbar_action = QAction(_("Status &Bar"), self)
        self.show_statusbar_action.setCheckable(True)
        self.show_statusbar_action.setChecked(True)
        self.show_statusbar_action.toggled.connect(self._toggle_statusbar)
        key_config.bind_action("Main Window", "Toggle Status Bar", self.show_statusbar_action)
        view_menu.addAction(self.show_statusbar_action)

        view_menu.addSeparator()

        self.toggle_grid_action = QAction(_("&Grid"), self)
        self.toggle_grid_action.setCheckable(True)
        self.toggle_grid_action.toggled.connect(self.viewer.set_grid_overlay_visible)
        self.toggle_grid_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.viewer.addAction(self.toggle_grid_action)
        key_config.bind_action("Viewer", "Toggle Grid Overlay", self.toggle_grid_action)
        view_menu.addAction(self.toggle_grid_action)

        self.toggle_ruler_action = QAction(_("&Ruler"), self)
        self.toggle_ruler_action.setCheckable(True)
        self.toggle_ruler_action.toggled.connect(self.viewer.set_ruler_overlay_visible)
        self.toggle_ruler_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.viewer.addAction(self.toggle_ruler_action)
        key_config.bind_action("Viewer", "Toggle Ruler Overlay", self.toggle_ruler_action)
        view_menu.addAction(self.toggle_ruler_action)

        self.toggle_pixel_info_action = QAction(_("&Pixel Info"), self)
        self.toggle_pixel_info_action.setCheckable(True)
        self.toggle_pixel_info_action.toggled.connect(self.viewer.set_pixel_info_mode)
        self.toggle_pixel_info_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.viewer.addAction(self.toggle_pixel_info_action)
        key_config.bind_action("Viewer", "Toggle Pixel Info", self.toggle_pixel_info_action)
        view_menu.addAction(self.toggle_pixel_info_action)
        # One optional radio group per independent overlay gives native
        # radio indicators while still allowing multiple overlays at once.
        self._overlay_action_groups = []
        for action in (self.toggle_grid_action, self.toggle_ruler_action, self.toggle_pixel_info_action):
            group = QActionGroup(self)
            group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
            group.addAction(action)
            self._overlay_action_groups.append(group)

        # ---------------------------------------------------- Options ----
        options_menu = menubar.addMenu(_("&Options"))
        self.options_menu = options_menu

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
        key_config.bind_action("Main Window", "About", about_action)
        options_menu.addAction(about_action)

    # ---------------------------------------------------------- toolbar ----
    def setup_toolbar(self):
        self.toolbar = self.addToolBar(_("Main"))
        self.toolbar.setObjectName("mainToolbar")
        self.toolbar.setAccessibleName(_("Main toolbar"))

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
        for action, callback in (
            ("Toggle Crop Mode", self.editor_panel.crop_panel.crop_mode_checkbox.toggle),
            ("Toggle Drawing Mode", self.editor_panel.draw_panel.draw_mode_checkbox.toggle),
            ("Clear Overlays", self._clear_overlays),
            ("Cancel/Escape Mode", self._cancel_viewer_modes),
        ):
            key_config.make_shortcut("Viewer", action, self.viewer, callback,
                                     Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def _focus_pane(self, widget):
        if widget is self.explorer_widget and not self.explorer_dock.isVisible():
            self.show_explorer_action.setChecked(True)
        self.focus_manager._focus_navigation_target(widget)

    # -------------------------------------------------------- signals ----
    def connect_signals(self):
        self.explorer_widget.open_image.connect(self.load_image_file)
        self.viewer.zoom_changed.connect(self._update_zoom_display)
        self.viewer.stroke_finished.connect(self._on_stroke_finished)
        self.editor.set_state_change_callback(self._on_editor_state_changed)
        self.editor_panel.edit_dialog_opening.connect(self._begin_edit)
        self.editor_panel.crop_panel.crop_mode_toggled.connect(self._set_crop_mode)
        self.editor_panel.crop_panel.crop_applied.connect(self._apply_crop)

        self.editor_panel.draw_panel.drawing_mode_toggled.connect(self._set_drawing_mode)
        self.editor_panel.draw_panel.pen_color_changed.connect(self.viewer.set_pen_color)
        self.editor_panel.draw_panel.pen_width_changed.connect(self.viewer.set_pen_width)

        self.explorer_widget.explorer.recent_files_updated.connect(lambda *_: self.update_recent_files_menu())

        overlay_panel = self.editor_panel.overlay_panel
        overlay_panel.grid_toggled.connect(self.viewer.set_grid_overlay_visible)
        overlay_panel.ruler_toggled.connect(self.viewer.set_ruler_overlay_visible)
        overlay_panel.pixel_info_toggled.connect(self.viewer.set_pixel_info_mode)
        overlay_panel.text_overlay_requested.connect(self.add_document_text)
        overlay_panel.shape_mode_changed.connect(self._on_shape_mode_changed)
        overlay_panel.overlays_cleared.connect(self._clear_overlays)
        self.viewer.overlay_state_changed.connect(self._sync_overlay_controls)
        self._sync_overlay_controls()

    def _sync_overlay_controls(self):
        panel = self.editor_panel.overlay_panel
        for action, button, checked in (
            (self.toggle_grid_action, panel.grid_btn, self.viewer.grid_overlay_visible()),
            (self.toggle_ruler_action, panel.ruler_btn, self.viewer.ruler_overlay_visible()),
            (self.toggle_pixel_info_action, panel.pixel_info_btn,
             self.viewer.pixel_info_mode and self.viewer.show_overlays),
        ):
            with QSignalBlocker(action), QSignalBlocker(button):
                action.setChecked(checked)
                button.setChecked(checked)

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
    def new_file(self):
        """File -> New: create a blank canvas and load it into the editor.
        Pairs with Canvas Drawing mode - a fresh surface to paint on that
        can then be saved like any other image."""
        from gui.dialogs.new_image_dialog import NewImageDialog
        dialog = NewImageDialog(self)
        if not dialog.exec():
            return
        if not self._confirm_close():
            return

        width, height, color = dialog.values()
        if color.alpha() < 255:
            pil_img = PILImage.new(
                "RGBA", (width, height),
                (color.red(), color.green(), color.blue(), color.alpha()))
        else:
            pil_img = PILImage.new(
                "RGB", (width, height),
                (color.red(), color.green(), color.blue()))

        self.editor.load_image(PhotonImage(pil_img))
        self.editor.state.dirty = True
        self.current_file_path = None
        self.viewer.set_image(self.editor.current_image)
        self.editor_panel.reset_controls()
        self._update_window_title()
        self._update_image_info()
        self.status_label.setText(
            _("New {width} × {height} image").format(width=width, height=height))

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
        self.load_document_file(file_path)


    def cli_load_file(self, ipc_msg_data: dict):
        self.load_file(ipc_msg_data["msg_data"])

    def save_file(self):
        self.save_document()


    def save_file_as(self):
        self.save_document(save_as=True)


    def undo(self):
        if self.editor.undo():
            # _on_editor_state_changed already refreshes the viewer.
            self.status_label.setText(_("Undone"))

    def redo(self):
        if self.editor.redo():
            self.status_label.setText(_("Redone"))

    def reset_image(self):
        if self.editor.current_image:
            self.editor.reset_to_original()
            self.refresh_document_view()
            self.editor_panel.reset_controls()
            self.status_label.setText(_("Reset to original"))

    def _apply_crop(self):
        crop_rect = self.viewer.get_crop_rect()
        if crop_rect and self.editor.current_image:
            box = (crop_rect.x(), crop_rect.y(), crop_rect.x() + crop_rect.width(), crop_rect.y() + crop_rect.height())
            self.editor.crop(box)
            self.refresh_document_view()
            self.viewer.enable_crop_mode(False)
            self.editor_panel.crop_panel.crop_mode_checkbox.setChecked(False)

    def _on_shape_mode_changed(self, shape_type: str):
        if shape_type:
            self.editor_panel.crop_panel.crop_mode_checkbox.setChecked(False)
            self.editor_panel.draw_panel.draw_mode_checkbox.setChecked(False)
        self.viewer.set_shape_drawing_mode(shape_type or None)

    def _set_crop_mode(self, enabled: bool):
        if enabled:
            self.editor_panel.draw_panel.draw_mode_checkbox.setChecked(False)
            self.editor_panel.overlay_panel.reset_shape_tool()
        self.viewer.enable_crop_mode(enabled)

    def _set_drawing_mode(self, enabled: bool):
        if enabled:
            self.editor_panel.crop_panel.crop_mode_checkbox.setChecked(False)
            self.editor_panel.overlay_panel.reset_shape_tool()
        self.viewer.set_drawing_mode(enabled)

    def _clear_overlays(self):
        self.viewer.clear_overlays()
        if self.editor.document and self.editor.document.has_artwork:
            self.editor.clear_artwork()

    def _cancel_viewer_modes(self):
        self.editor_panel.crop_panel.crop_mode_checkbox.setChecked(False)
        self.editor_panel.draw_panel.draw_mode_checkbox.setChecked(False)
        self.editor_panel.overlay_panel.reset_shape_tool()

    def _on_stroke_finished(self, points: list, color: tuple, width: int):
        if self.editor.current_image:
            self.editor.draw_stroke(points, color, width)
            self.refresh_document_view()
            self.status_label.setText(_("Stroke drawn"))

    def _update_zoom_display(self, zoom_factor: float):
        self.zoom_label.setText(_("Zoom: {percent:.0f}%").format(percent=zoom_factor * 100))

    def _update_window_title(self):
        if self.current_file_path:
            base = f"Photon Snapshot - {os.path.basename(self.current_file_path)}"
        else:
            base = "Photon Snapshot"
        # The [*] placeholder + setWindowModified is Qt's cross-platform
        # modified-file indicator (shows an asterisk on Windows/Linux).
        self.setWindowTitle(base + "[*]")
        self.setWindowModified(self.editor.is_dirty)

    def _update_image_info(self):
        if self.editor.current_image:
            width, height = self.editor.current_image.size
            self.image_info_label.setText(f"{width} × {height}")
        else:
            self.image_info_label.setText("")

    def _on_editor_state_changed(self):
        has_image = self.editor.current_image is not None
        self.editor_panel.set_document_available(has_image)
        self.coordinate_crop_action.setEnabled(has_image)
        self.save_action.setEnabled(has_image)
        self.save_as_action.setEnabled(has_image)
        self.reset_action.setEnabled(has_image)
        self.undo_action.setEnabled(self.editor.can_undo())
        self.redo_action.setEnabled(self.editor.can_redo())

        if self.editor.current_image:
            self.refresh_document_view()
            self._update_image_info()

        self._update_window_title()

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
            action.deleteLater()

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
        self.playback.stop()
        from PySide6.QtWidgets import QSystemTrayIcon
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.showMinimized()
            return
        self.dock_manager.hide_floating_docks()
        self.hide()

    def close_application(self):
        """Tray-menu Quit. Route through close() so the unsaved-changes
        prompt in closeEvent runs; QApplication.quit() bypassed it."""
        self._force_exit = True
        try:
            self.close()
        finally:
            self._force_exit = False

    def _confirm_close(self) -> bool:
        """Prompt about unsaved edits. Returns True when it's OK to close."""
        if not (self.editor.current_image and self.editor.is_dirty):
            return True

        buttons = (QMessageBox.StandardButton.Save
                   | QMessageBox.StandardButton.Discard
                   | QMessageBox.StandardButton.Cancel)
        reply = QMessageBox.question(
            self,
            _("Unsaved Changes"),
            _("The image has been modified. Do you want to save your changes?"),
            buttons,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        if reply == QMessageBox.StandardButton.Save:
            if self.current_file_path:
                self.save_file()
            else:
                self.save_file_as()
            # Still dirty means the save was cancelled or failed.
            return not self.editor.is_dirty
        return True  # Discard

    def closeEvent(self, event):
        if not self._force_exit and prefs.get("minimize_to_tray_on_close", False):
            event.ignore()
            self._minimize_to_tray()
            return
        if not self._exit_authorized and not self._confirm_close():
            event.ignore()
            return
        self.playback.stop()
        if self.jobs.active:
            reply = QMessageBox.question(self, _('Active Jobs'), _('Wait for active jobs before exiting? Choose No to cancel them and exit after cleanup.'),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            event.ignore()
            if reply == QMessageBox.StandardButton.Cancel:
                return
            self._pending_exit = True
            if reply == QMessageBox.StandardButton.No:
                self.jobs.cancel_all()
            return
        self.dock_manager.save_window_state()
        super().closeEvent(event)
        if event.isAccepted() and self._force_exit:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()
