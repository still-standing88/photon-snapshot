from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
                             QListWidgetItem, QLabel, QFrame, QPushButton,
                             QLineEdit, QSplitter, QGroupBox, QToolBar, QMenu)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QAction
from core.explorer import FileExplorer
from core.utils import create_thumbnail, is_image_file, get_file_size_str
from core.image import PhotonImage
from gui_controls.common_controls import TabableLabel
import os
from pathlib import Path


class FileListWidget(QListWidget):
    file_selected = Signal(str)
    directory_entered = Signal(str)
    open_image = Signal(str)

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
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        menu = QMenu(self)
        if data["is_image"]:
            open_action = QAction(_("Open Image"), self)
            open_action.triggered.connect(lambda: self.open_image.emit(data["full_path"]))
            menu.addAction(open_action)
        elif data["is_directory"]:
            open_action = QAction(_("Open Folder"), self)
            open_action.triggered.connect(lambda: self.directory_entered.emit(data["full_path"]))
            menu.addAction(open_action)
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


class PathBar(QWidget):
    path_changed = Signal(str)

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        self.path_edit = QLineEdit()
        self.path_edit.setAccessibleName(_("Current folder path"))
        self.path_edit.setPlaceholderText(_("Enter a folder path and press Enter"))
        self.path_edit.returnPressed.connect(self._on_path_entered)

        layout.addWidget(self.path_edit)
        self.setLayout(layout)

    def set_path(self, path: str):
        self.path_edit.setText(path)

    def _on_path_entered(self):
        path = self.path_edit.text().strip()
        if path:
            self.path_changed.emit(path)


class NavigationBar(QWidget):
    back_clicked = Signal()
    forward_clicked = Signal()
    up_clicked = Signal()

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        style = self.style()

        self.back_btn = QPushButton()
        self.back_btn.setIcon(style.standardIcon(style.StandardPixmap.SP_ArrowLeft))
        self.back_btn.setToolTip(_("Go Back"))
        self.back_btn.setAccessibleName(_("Go back"))
        self.back_btn.setFixedSize(30, 30)
        self.back_btn.clicked.connect(self.back_clicked.emit)

        self.forward_btn = QPushButton()
        self.forward_btn.setIcon(style.standardIcon(style.StandardPixmap.SP_ArrowRight))
        self.forward_btn.setToolTip(_("Go Forward"))
        self.forward_btn.setAccessibleName(_("Go forward"))
        self.forward_btn.setFixedSize(30, 30)
        self.forward_btn.clicked.connect(self.forward_clicked.emit)

        self.up_btn = QPushButton()
        self.up_btn.setIcon(style.standardIcon(style.StandardPixmap.SP_ArrowUp))
        self.up_btn.setToolTip(_("Go Up"))
        self.up_btn.setAccessibleName(_("Go to parent folder"))
        self.up_btn.setFixedSize(30, 30)
        self.up_btn.clicked.connect(self.up_clicked.emit)

        layout.addWidget(self.back_btn)
        layout.addWidget(self.forward_btn)
        layout.addWidget(self.up_btn)
        layout.addStretch()

        self.setLayout(layout)

    def set_navigation_state(self, can_back: bool, can_forward: bool):
        self.back_btn.setEnabled(can_back)
        self.forward_btn.setEnabled(can_forward)


class LibraryWidget(QGroupBox):
    """Pinned-folder list: quick access to folders the user browses often.
    Deliberately just a flat list of paths persisted in SQLite (see
    ``core.explorer.FileExplorer.get_library_folders``) - no media
    catalog/scanning database sits behind it."""

    folder_activated = Signal(str)

    def __init__(self, explorer: FileExplorer):
        super().__init__(_("Library"))
        self.setAccessibleName(_("Library"))
        self._explorer = explorer

        layout = QVBoxLayout(self)

        self.list = QListWidget()
        self.list.setAccessibleName(_("Library folders"))
        self.list.setAccessibleDescription(_("Pinned folders for quick access. Double-click or press Enter to open."))
        self.list.itemActivated.connect(self._on_activated)
        layout.addWidget(self.list)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton(_("Add Current Folder"))
        self.add_btn.setAccessibleName(_("Add current folder to library"))
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.remove_btn = QPushButton(_("Remove"))
        self.remove_btn.setAccessibleName(_("Remove selected folder from library"))
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.remove_btn)
        layout.addLayout(btn_row)

        self._explorer.library_updated.connect(self.refresh)
        self.refresh(self._explorer.get_library_folders())

    def refresh(self, folders=None):
        folders = folders if folders is not None else self._explorer.get_library_folders()
        self.list.clear()
        style = self.style()
        for folder in folders:
            item = QListWidgetItem(style.standardIcon(style.StandardPixmap.SP_DirIcon), os.path.basename(folder) or folder)
            item.setToolTip(folder)
            item.setData(Qt.ItemDataRole.UserRole, folder)
            self.list.addItem(item)

    def _on_activated(self, item):
        self.folder_activated.emit(item.data(Qt.ItemDataRole.UserRole))

    def _on_add_clicked(self):
        self._explorer.add_library_folder(self._explorer.current_path)

    def _on_remove_clicked(self):
        item = self.list.currentItem()
        if item:
            self._explorer.remove_library_folder(item.data(Qt.ItemDataRole.UserRole))


class ExplorerWidget(QWidget):
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

        self.library_widget = LibraryWidget(self.explorer)
        layout.addWidget(self.library_widget)

        path_group = QGroupBox(_("Path"))
        path_layout = QVBoxLayout(path_group)
        self.nav_bar = NavigationBar()
        self.path_bar = PathBar()
        path_layout.addWidget(self.nav_bar)
        path_layout.addWidget(self.path_bar)
        layout.addWidget(path_group)

        search_group = QGroupBox(_("Search"))
        search_layout = QHBoxLayout(search_group)
        self.search_edit = QLineEdit()
        self.search_edit.setAccessibleName(_("Search current folder"))
        self.search_edit.setPlaceholderText(_("Search current folder..."))
        self.search_edit.returnPressed.connect(self._on_search_submitted)
        search_layout.addWidget(self.search_edit)
        self.search_clear_btn = QPushButton(_("Clear"))
        self.search_clear_btn.setAccessibleName(_("Clear search"))
        self.search_clear_btn.clicked.connect(self._on_search_cleared)
        search_layout.addWidget(self.search_clear_btn)
        layout.addWidget(search_group)

        files_group = QGroupBox(_("Files"))
        files_layout = QVBoxLayout(files_group)

        self.toolbar = QToolBar(_("Explorer Toolbar"))
        self.toolbar.setAccessibleName(_("Explorer toolbar"))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.refresh_action = QAction(_("Refresh"), self)
        self.refresh_action.setShortcut("F5")
        self.refresh_action.triggered.connect(self.refresh_view)
        self.toolbar.addAction(self.refresh_action)
        files_layout.addWidget(self.toolbar)

        content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.file_list = FileListWidget()
        self.preview_pane = PreviewPane()
        content_splitter.addWidget(self.file_list)
        content_splitter.addWidget(self.preview_pane)
        content_splitter.setSizes([300, 200])
        files_layout.addWidget(content_splitter)

        layout.addWidget(files_group, 1)

        self.setLayout(layout)

    def connect_signals(self):
        self.explorer.path_changed.connect(self._on_path_changed)
        self.nav_bar.back_clicked.connect(self.explorer.go_back)
        self.nav_bar.forward_clicked.connect(self.explorer.go_forward)
        self.nav_bar.up_clicked.connect(self.explorer.go_up)
        self.path_bar.path_changed.connect(self.explorer.navigate_to)
        self.file_list.directory_entered.connect(self.explorer.navigate_to)
        self.file_list.file_selected.connect(self._on_file_selected)
        self.file_list.open_image.connect(self.open_image.emit)
        self.library_widget.folder_activated.connect(self.explorer.navigate_to)

    def _on_path_changed(self, path: str):
        self.path_bar.set_path(path)
        self.nav_bar.set_navigation_state(self.explorer.can_go_back(), self.explorer.can_go_forward())
        self._search_active = False
        self.search_edit.clear()
        self.refresh_view()

    def _on_file_selected(self, filepath: str):
        self.preview_pane.set_preview(filepath)
        self.file_selected.emit(filepath)

    def _on_search_submitted(self):
        query = self.search_edit.text().strip()
        if not query:
            self._on_search_cleared()
            return
        self._search_active = True
        self._populate(self.explorer.search(query))

    def _on_search_cleared(self):
        self.search_edit.clear()
        self._search_active = False
        self.refresh_view()

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
        if event.key() == Qt.Key.Key_Backspace and not self.path_bar.path_edit.hasFocus():
            self.explorer.go_back()
        else:
            super().keyPressEvent(event)
