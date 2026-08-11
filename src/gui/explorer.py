import os

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QFrame, QToolButton,
                             QLineEdit, QSplitter, QMenu, QTreeWidget, QTreeWidgetItem)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QAction, QGuiApplication
from core.explorer import FileExplorer
from core.utils import create_thumbnail, is_image_file, get_file_size_str
from core.image import PhotonImage
from gui_controls.common_controls import TabableLabel


class FileListWidget(QListWidget):
    """The file/folder list. All actions beyond plain navigation (open,
    add to library, copy path, refresh) live in its right-click context
    menu rather than dedicated toolbar buttons, mirroring playForm's
    explorer_view - keeps the always-visible chrome down to just the
    parent/search buttons above it."""

    file_selected = Signal(str)
    directory_entered = Signal(str)
    open_image = Signal(str)
    add_to_library_requested = Signal(str)
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setAccessibleName(_("File list"))
        self.setAccessibleDescription(_("Files and folders in the current directory. Enter opens a folder or image, double-click opens images."))
        self.setIconSize(QSize(16, 16))
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _get_file_icon(self, is_directory: bool, is_image: bool, file_name: str = "") -> QIcon:
        style = self.style()
        if is_directory:
            return style.standardIcon(style.StandardPixmap.SP_DirIcon)
        elif is_image:
            return style.standardIcon(style.StandardPixmap.SP_DesktopIcon)
        else:
            return style.standardIcon(style.StandardPixmap.SP_FileIcon)

    def _on_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data and data["is_image"]:
            self.file_selected.emit(data["full_path"])

    def _on_item_double_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            if data["is_directory"]:
                self.directory_entered.emit(data["full_path"])
            elif data["is_image"]:
                self.open_image.emit(data["full_path"])

    def _show_context_menu(self, position):
        item = self.itemAt(position)
        menu = QMenu(self)

        if item is not None:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data["is_image"]:
                open_action = QAction(_("Open Image"), self)
                open_action.triggered.connect(lambda: self.open_image.emit(data["full_path"]))
                menu.addAction(open_action)

                copy_action = QAction(_("Copy Path"), self)
                copy_action.triggered.connect(lambda: QGuiApplication.clipboard().setText(data["full_path"]))
                menu.addAction(copy_action)
            elif data and data["is_directory"]:
                open_action = QAction(_("Open Folder"), self)
                open_action.triggered.connect(lambda: self.directory_entered.emit(data["full_path"]))
                menu.addAction(open_action)

                add_lib_action = QAction(_("Add to Library"), self)
                add_lib_action.triggered.connect(lambda: self.add_to_library_requested.emit(data["full_path"]))
                menu.addAction(add_lib_action)

                copy_action = QAction(_("Copy Path"), self)
                copy_action.triggered.connect(lambda: QGuiApplication.clipboard().setText(data["full_path"]))
                menu.addAction(copy_action)
            menu.addSeparator()

        refresh_action = QAction(_("Refresh"), self)
        refresh_action.triggered.connect(self.refresh_requested.emit)
        menu.addAction(refresh_action)

        menu.exec(self.mapToGlobal(position))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current_item = self.currentItem()
            if current_item:
                self._on_item_double_clicked(current_item)
                return
        super().keyPressEvent(event)


class PreviewPane(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(200)
        self.setAccessibleName(_("Selected file preview"))

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(180, 180)
        self.preview_label.setAccessibleName(_("Preview thumbnail"))

        self.name_label = TabableLabel("", accessible_name=_("File name"))
        self.name_label.setWordWrap(True)

        self.size_label = TabableLabel("", accessible_name=_("File size"))
        self.dimensions_label = TabableLabel("", accessible_name=_("Image dimensions"))

        layout.addWidget(self.preview_label)
        layout.addWidget(self.name_label)
        layout.addWidget(self.size_label)
        layout.addWidget(self.dimensions_label)
        layout.addStretch()

        self.setLayout(layout)
        self.current_file = None

    def set_preview(self, filepath: str):
        self.current_file = filepath
        try:
            if is_image_file(filepath):
                image = PhotonImage.from_file(filepath)
                thumbnail = create_thumbnail(image.current, (160, 160))
                self.preview_label.setPixmap(thumbnail)

                file_size = os.path.getsize(filepath)
                width, height = image.size

                self.name_label.setText(os.path.basename(filepath))
                self.size_label.setText(get_file_size_str(file_size))
                self.dimensions_label.setText(f"{width} × {height}")
            else:
                self.clear_preview()
        except Exception:
            self.clear_preview()

    def clear_preview(self):
        self.preview_label.clear()
        self.preview_label.setText(_("No preview"))
        self.name_label.setText("")
        self.size_label.setText("")
        self.dimensions_label.setText("")


class LibraryTree(QTreeWidget):
    """Pinned-folder tree, mirroring playForm's LibraryView: a single
    "Library" root with one child per pinned folder. Deliberately just a
    flat list of paths persisted in SQLite (see
    ``core.explorer.FileExplorer.get_library_folders``) - no media
    catalog/scanning database sits behind it. All actions (add/remove/
    clear) live in the right-click context menu, not buttons."""

    folder_activated = Signal(str)

    def __init__(self, explorer: FileExplorer):
        super().__init__()
        self._explorer = explorer
        self.setAccessibleName(_("Library"))
        self.setAccessibleDescription(_("Pinned folders for quick access. Double-click or press Enter to open. Right-click for more actions."))
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.itemActivated.connect(self._on_activated)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._root = QTreeWidgetItem(self, [_("Library")])
        self._root.setFlags(self._root.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        style = self.style()
        self._root.setIcon(0, style.standardIcon(style.StandardPixmap.SP_DriveHDIcon))
        self.addTopLevelItem(self._root)
        self._root.setExpanded(True)

        self._explorer.library_updated.connect(self.refresh)
        self.refresh(self._explorer.get_library_folders())

    def refresh(self, folders=None):
        folders = folders if folders is not None else self._explorer.get_library_folders()
        self._root.takeChildren()
        style = self.style()
        for folder in folders:
            item = QTreeWidgetItem(self._root, [os.path.basename(folder) or folder])
            item.setIcon(0, style.standardIcon(style.StandardPixmap.SP_DirIcon))
            item.setToolTip(0, folder)
            item.setData(0, Qt.ItemDataRole.UserRole, folder)

    def _on_activated(self, item, column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.folder_activated.emit(path)

    def _show_context_menu(self, position):
        item = self.itemAt(position)
        menu = QMenu(self)

        add_action = QAction(_("Add Current Folder to Library"), self)
        add_action.triggered.connect(lambda: self._explorer.add_library_folder(self._explorer.current_path))
        menu.addAction(add_action)

        if item is not None and item is not self._root:
            remove_action = QAction(_("Remove from Library"), self)
            remove_action.triggered.connect(lambda: self._explorer.remove_library_folder(item.data(0, Qt.ItemDataRole.UserRole)))
            menu.addAction(remove_action)

        menu.addSeparator()
        clear_action = QAction(_("Clear Library"), self)
        clear_action.triggered.connect(self._clear_library)
        menu.addAction(clear_action)

        menu.exec(self.mapToGlobal(position))

    def _clear_library(self):
        for folder in list(self._explorer.get_library_folders()):
            self._explorer.remove_library_folder(folder)


class SearchLineEdit(QLineEdit):
    """A QLineEdit whose Escape key closes the search bar (via `closed`)
    instead of being swallowed - lets the search button toggle work as a
    single Escape-to-dismiss affordance without a separate Clear button."""

    closed = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.closed.emit()
            return
        super().keyPressEvent(event)


class ExplorerWidget(QWidget):
    """Library tree + file list + a Parent button + a Search toggle -
    mirroring playForm's explorer interface. Every other action (open,
    add/remove library folder, copy path, refresh) is reached through
    right-click context menus rather than dedicated buttons, keeping the
    always-visible chrome minimal."""

    file_selected = Signal(str)
    open_image = Signal(str)

    def __init__(self):
        super().__init__()
        self.setAccessibleName(_("Explorer"))
        self.explorer = FileExplorer()
        self._search_active = False
        self.setup_ui()
        self.connect_signals()
        self.refresh_view()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        style = self.style()

        top_bar = QHBoxLayout()

        self.parent_btn = QToolButton()
        self.parent_btn.setIcon(style.standardIcon(style.StandardPixmap.SP_FileDialogToParent))
        self.parent_btn.setText(_("Parent"))
        self.parent_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.parent_btn.setToolTip(_("Go to parent folder"))
        self.parent_btn.setAccessibleName(_("Go to parent folder"))
        self.parent_btn.clicked.connect(self.explorer.go_up)
        top_bar.addWidget(self.parent_btn)

        self.search_toggle_btn = QToolButton()
        self.search_toggle_btn.setIcon(style.standardIcon(style.StandardPixmap.SP_FileDialogContentsView))
        self.search_toggle_btn.setText(_("Search"))
        self.search_toggle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.search_toggle_btn.setCheckable(True)
        self.search_toggle_btn.setToolTip(_("Search current folder"))
        self.search_toggle_btn.setAccessibleName(_("Toggle search"))
        self.search_toggle_btn.toggled.connect(self._on_search_toggled)
        top_bar.addWidget(self.search_toggle_btn)

        top_bar.addStretch()

        self.path_label = TabableLabel("", accessible_name=_("Current folder path"))
        self.path_label.setStyleSheet("color: #999999;")
        top_bar.addWidget(self.path_label)

        layout.addLayout(top_bar)

        self.search_bar = SearchLineEdit()
        self.search_bar.setAccessibleName(_("Search current folder"))
        self.search_bar.setPlaceholderText(_("Search current folder..."))
        self.search_bar.returnPressed.connect(self._on_search_submitted)
        self.search_bar.closed.connect(lambda: self.search_toggle_btn.setChecked(False))
        self.search_bar.setVisible(False)
        layout.addWidget(self.search_bar)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.library_tree = LibraryTree(self.explorer)
        self.file_list = FileListWidget()
        self.preview_pane = PreviewPane()
        main_splitter.addWidget(self.library_tree)
        main_splitter.addWidget(self.file_list)
        main_splitter.addWidget(self.preview_pane)
        main_splitter.setSizes([120, 320, 200])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)

        layout.addWidget(main_splitter, 1)

        # F5 still refreshes even without a visible toolbar button - added
        # directly to the widget (not a QShortcut) so it only fires while
        # something inside the Explorer has focus.
        self.refresh_action = QAction(_("Refresh"), self)
        self.refresh_action.setShortcut("F5")
        self.refresh_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.refresh_action.triggered.connect(self.refresh_view)
        self.addAction(self.refresh_action)

        self.setLayout(layout)

    def connect_signals(self):
        self.explorer.path_changed.connect(self._on_path_changed)
        self.file_list.directory_entered.connect(self.explorer.navigate_to)
        self.file_list.file_selected.connect(self._on_file_selected)
        self.file_list.open_image.connect(self.open_image.emit)
        self.file_list.add_to_library_requested.connect(self.explorer.add_library_folder)
        self.file_list.refresh_requested.connect(self.refresh_view)
        self.library_tree.folder_activated.connect(self.explorer.navigate_to)

    def _on_search_toggled(self, checked: bool):
        self.search_bar.setVisible(checked)
        if checked:
            self.search_bar.setFocus()
            self.search_bar.selectAll()
        else:
            self.search_bar.clear()
            self._search_active = False
            self.refresh_view()

    def _on_path_changed(self, path: str):
        self.path_label.setText(path)
        self.path_label.setToolTip(path)
        if self.search_toggle_btn.isChecked():
            self.search_toggle_btn.setChecked(False)  # triggers refresh_view() via _on_search_toggled
        else:
            self.refresh_view()

    def _on_file_selected(self, filepath: str):
        self.preview_pane.set_preview(filepath)
        self.file_selected.emit(filepath)

    def _on_search_submitted(self):
        query = self.search_bar.text().strip()
        if not query:
            self.search_toggle_btn.setChecked(False)
            return
        self._search_active = True
        self._populate(self.explorer.search(query))

    def refresh_view(self):
        if self._search_active:
            return
        self._populate(self.explorer.get_all_files())

    def _populate(self, files):
        self.file_list.clear()
        for name, is_dir, is_image, full_path in files:
            item = QListWidgetItem()
            item.setText(name)
            icon = self.file_list._get_file_icon(is_dir, is_image, name)
            item.setIcon(icon)
            item.setData(Qt.ItemDataRole.UserRole, {
                "name": name,
                "is_directory": is_dir,
                "is_image": is_image,
                "full_path": full_path,
            })
            if is_dir:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.file_list.addItem(item)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Backspace and not self.search_bar.hasFocus():
            self.explorer.go_up()
        else:
            super().keyPressEvent(event)
