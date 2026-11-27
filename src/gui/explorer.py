"""playForm's Library / Path & Search / Files layout, adapted for images."""
import os
from datetime import datetime

from PIL import Image as PILImage, ImageOps
from PySide6.QtCore import Qt, Signal, QSize, QRect
from PySide6.QtGui import QAction, QActionGroup, QFont, QFontMetrics, QIcon, QPalette, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QSplitter,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem, QToolBar, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)
from app_config import key_config
from app_config.prefs import prefs
from core.explorer import FileExplorer
from core.utils import pil_to_qpixmap, get_file_size_str
from .explorer_search import SearchWorker

DETAILS_ROLE = Qt.ItemDataRole.UserRole + 1


class FileDetailsDelegate(QStyledItemDelegate):
    """Detail-view painter: file name wrapped over up to two lines with the
    entry's details (type/date/size) on a line below. Replaces the old
    per-item QLabel overlay, whose fixed 200px minimum width clipped long
    names and whose creation-time sizeHint never adapted to window resizes.
    Height is uniform for all rows so scrolling stays smooth; width comes
    from the view's viewport so text re-wraps on resize."""

    MAX_NAME_LINES = 2

    def __init__(self, view):
        super().__init__(view)
        self._view = view
        self._width = 300

    def set_viewport_width(self, width: int):
        self._width = max(120, int(width))

    @staticmethod
    def _wrap_lines(text, metrics: QFontMetrics, width: int, max_lines: int) -> list:
        if not text:
            return []
        words = text.split()
        lines = []
        current = ""
        overflow = False
        for word in words:
            candidate = f"{current} {word}" if current else word
            if not current or metrics.horizontalAdvance(candidate) <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
                if len(lines) == max_lines:
                    overflow = True
                    break
        if not overflow and current:
            lines.append(current)
        if lines and (overflow or metrics.horizontalAdvance(lines[-1]) > width):
            lines[-1] = metrics.elidedText(lines[-1], Qt.TextElideMode.ElideRight, width)
        return lines[:max_lines]

    def _row_height(self, name_metrics: QFontMetrics, detail_metrics: QFontMetrics) -> int:
        return self.MAX_NAME_LINES * name_metrics.height() + detail_metrics.height() + 8

    def sizeHint(self, option, index):
        if self._view.viewMode() != QListWidget.ViewMode.ListMode:
            return super().sizeHint(option, index)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        name_metrics = QFontMetrics(opt.font)
        detail_font = opt.font
        detail_font.setPointSizeF(max(7.0, detail_font.pointSizeF() - 1))
        detail_metrics = QFontMetrics(detail_font)
        return QSize(self._width, self._row_height(name_metrics, detail_metrics))

    def paint(self, painter, option, index):
        if self._view.viewMode() != QListWidget.ViewMode.ListMode:
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        name = opt.text
        details = index.data(DETAILS_ROLE) or ""

        opt.text = ""
        opt.icon = QIcon()
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        rect = opt.rect.adjusted(6, 2, -6, -2)
        name_metrics = QFontMetrics(opt.font)
        detail_font = QFont(opt.font)
        detail_font.setPointSizeF(max(7.0, detail_font.pointSizeF() - 1))
        detail_metrics = QFontMetrics(detail_font)

        y = rect.top()
        alignment = (Qt.AlignmentFlag.AlignRight if opt.direction == Qt.LayoutDirection.RightToLeft
                     else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        text_color = opt.palette.color(QPalette.ColorRole.HighlightedText if selected
                                       else QPalette.ColorRole.Text)
        for line in self._wrap_lines(name, name_metrics, rect.width(), self.MAX_NAME_LINES):
            painter.setFont(opt.font)
            painter.setPen(text_color)
            painter.drawText(QRect(rect.left(), y, rect.width(), name_metrics.height()),
                             alignment, line)
            y += name_metrics.height()

        if details:
            painter.setFont(detail_font)
            painter.setPen(text_color if selected else opt.palette.color(QPalette.ColorRole.PlaceholderText))
            elided = detail_metrics.elidedText(details, Qt.TextElideMode.ElideRight, rect.width())
            painter.drawText(QRect(rect.left(), y, rect.width(), detail_metrics.height()),
                             alignment, elided)


class FileListWidget(QListWidget):
    file_selected = Signal(str)
    directory_entered = Signal(str)
    open_image = Signal(str)
    add_to_library_requested = Signal(str)
    add_to_favorites_requested = Signal(str)
    refresh_requested = Signal()
    options_menu_requested = Signal(object)

    def __init__(self):
        super().__init__()
        self.setAccessibleName(_("Files"))
        self._details_delegate = FileDetailsDelegate(self)
        self.setItemDelegate(self._details_delegate)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.currentItemChanged.connect(self._on_current_item_changed)
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_view_mode(self, list_mode):
        self.setViewMode(QListWidget.ViewMode.ListMode if list_mode else QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setWrapping(not list_mode)
        self.setGridSize(QSize() if list_mode else QSize(96, 96))
        self.setIconSize(QSize(16, 16) if list_mode else QSize(48, 48))
        self._details_delegate.set_viewport_width(self.viewport().width())
        self.doItemsLayout()

    def _get_file_icon(self, is_directory, is_image, file_name=""):
        return self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon if is_directory
                                         else QStyle.StandardPixmap.SP_FileIcon)

    def _on_current_item_changed(self, item, previous):
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        self.file_selected.emit(data["full_path"] if data and data["is_image"] else "")

    def _on_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data and data["is_directory"]:
            self.directory_entered.emit(data["full_path"])

    def _on_item_double_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            if data["is_directory"]:
                self.directory_entered.emit(data["full_path"])
            elif data["is_image"]:
                self.open_image.emit(data["full_path"])

    def open_selected(self):
        item = self.currentItem()
        if item is not None:
            self._on_item_double_clicked(item)

    def _show_context_menu(self, position):
        item = self.itemAt(position)
        if item is not None:
            self.setCurrentItem(item)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        menu = QMenu(self)
        if data:
            if data["is_directory"]:
                menu.addAction(_("Open Folder"), lambda: self.directory_entered.emit(data["full_path"]))
                menu.addAction(_("Add to Library"), lambda: self.add_to_library_requested.emit(data["full_path"]))
            elif data["is_image"]:
                menu.addAction(_("Open Image"), lambda: self.open_image.emit(data["full_path"]))
                menu.addAction(_("Add to Favorites"), lambda: self.add_to_favorites_requested.emit(data["full_path"]))
            menu.addAction(_("Copy Path"), lambda: QGuiApplication.clipboard().setText(data["full_path"]))
            menu.addSeparator()
        self.options_menu_requested.emit(menu)
        menu.addSeparator()
        menu.addAction(_("Refresh"), self.refresh_requested.emit)
        menu.exec(self.viewport().mapToGlobal(position))
        menu.deleteLater()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._details_delegate.set_viewport_width(self.viewport().width())
        self.doItemsLayout()


class ImagePreview(QLabel):
    def __init__(self):
        super().__init__()
        self._thumbnail = QPixmap()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName(_("Preview thumbnail"))
        self.setMinimumWidth(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.hide()

    def set_preview(self, path):
        self._thumbnail = QPixmap()
        if path:
            try:
                with PILImage.open(path) as image:
                    image.draft("RGB", (512, 512))
                    thumbnail = ImageOps.exif_transpose(image)
                    thumbnail.thumbnail((512, 512), PILImage.Resampling.LANCZOS)
                    self._thumbnail = pil_to_qpixmap(thumbnail)
            except (OSError, ValueError, PILImage.DecompressionBombError):
                pass
        self.setToolTip(path)
        self.setVisible(not self._thumbnail.isNull())
        self._update_pixmap()

    def _update_pixmap(self):
        if not self._thumbnail.isNull():
            self.setPixmap(self._thumbnail.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation))
        else:
            self.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pixmap()


class LibraryPathDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Add new path to library"))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(440, 160)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        label = QLabel(_("Path:"))
        self.path_field = QPlainTextEdit()
        self.path_field.setTabChangesFocus(True)
        self.path_field.setAccessibleName(_("Folder path"))
        label.setBuddy(self.path_field)
        path_layout = QVBoxLayout()
        path_layout.addWidget(label)
        path_layout.addWidget(self.path_field)
        row.addLayout(path_layout, 1)
        browse = QPushButton(_("Browse..."))
        browse.clicked.connect(self.browse)
        row.addWidget(browse)
        layout.addLayout(row)
        buttons = QDialogButtonBox()
        buttons.addButton(_("Confirm"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse(self):
        path = QFileDialog.getExistingDirectory(self, _("Select Folder"), self.path_field.toPlainText())
        if path:
            self.path_field.setPlainText(path)

    def path(self):
        return os.path.abspath(os.path.expandvars(os.path.expanduser(self.path_field.toPlainText().strip())))

    def accept(self):
        if not self.path_field.toPlainText().strip() or not os.path.isdir(self.path()):
            QMessageBox.warning(self, _("Invalid Folder"), _("Please select a valid, existing folder."))
            return
        super().accept()


class LibraryTree(QTreeWidget):
    folder_activated = Signal(str)

    def __init__(self, explorer):
        super().__init__()
        self._explorer = explorer
        self.setAccessibleName(_("Library"))
        self.setColumnCount(1)
        self.setHeaderLabels([_("Folder")])
        self.setMinimumWidth(100)
        self.itemClicked.connect(self._on_activated)
        self.itemActivated.connect(self._on_activated)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._root = QTreeWidgetItem(self, [_("Library")])
        self._root.setExpanded(True)
        self._explorer.library_updated.connect(self.refresh)
        self.refresh()

    def refresh(self, folders=None):
        folders = folders if folders is not None else self._explorer.get_library_folders()
        previous = self.currentItem()
        path = previous.data(0, Qt.ItemDataRole.UserRole) if previous else None
        self._root.takeChildren()
        for folder in folders:
            item = QTreeWidgetItem(self._root, [os.path.basename(os.path.normpath(folder)) or folder])
            item.setToolTip(0, folder)
            item.setData(0, Qt.ItemDataRole.UserRole, folder)
            if folder == path:
                self.setCurrentItem(item)

    def _on_activated(self, item, column=0):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            self.folder_activated.emit(path)

    def add_new(self):
        dialog = LibraryPathDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._explorer.add_library_folder(dialog.path())
        dialog.deleteLater()

    def remove_selected(self):
        item = self.currentItem()
        path = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if path:
            self._explorer.remove_library_folder(path)

    def _show_context_menu(self, position):
        item = self.itemAt(position)
        if item is not None:
            self.setCurrentItem(item)
        path = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        menu = QMenu(self)
        menu.addAction(_("Add new"), self.add_new)
        if path:
            menu.addAction(_("Remove"), self.remove_selected)
        clear = menu.addAction(_("Clear Library"), self._clear_library)
        clear.setEnabled(self._root.childCount() > 0)
        menu.exec(self.viewport().mapToGlobal(position))
        menu.deleteLater()

    def _clear_library(self):
        for folder in list(self._explorer.get_library_folders()):
            self._explorer.remove_library_folder(folder)


class SearchLineEdit(QLineEdit):
    closed = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.closed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ExplorerWidget(QWidget):
    file_selected = Signal(str)
    open_image = Signal(str)
    BATCH_SIZE = 500

    def __init__(self):
        super().__init__()
        self.setAccessibleName(_("Explorer"))
        self.explorer = FileExplorer()
        self._search_active = False
        self._search_query = ""
        self._search_root = ""
        self._pending_entries = []
        self._search_worker = SearchWorker(self)
        self._search_worker.results_ready.connect(self._on_search_results)
        self._search_worker.error.connect(self._on_search_error)
        self.destroyed.connect(self._search_worker.shutdown)
        self.setup_ui()
        self.connect_signals()
        self.setup_shortcuts()
        self.setFocusProxy(self.file_list)
        self.path_edit.setText(self.explorer.current_path)
        self.refresh_view()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.toolbar = QToolBar(_("Explorer Toolbar"))
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        layout.addWidget(self.toolbar)
        self.view_mode_group = QActionGroup(self)
        self.view_mode_group.setExclusive(True)
        self.view_list_action = QAction(_("List View"), self)
        self.view_icon_action = QAction(_("Icon View"), self)
        for action in (self.view_list_action, self.view_icon_action):
            action.setCheckable(True)
            self.view_mode_group.addAction(action)
            self.toolbar.addAction(action)
        self.view_list_action.triggered.connect(lambda: self.set_view_mode(True))
        self.view_icon_action.triggered.connect(lambda: self.set_view_mode(False))
        key_config.bind_action("Explorer", "List View", self.view_list_action)
        key_config.bind_action("Explorer", "Icon View", self.view_icon_action)
        self.toolbar.addSeparator()
        self.refresh_action = QAction(_("Refresh"), self)
        self.refresh_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.refresh_action.triggered.connect(self.refresh_view)
        key_config.bind_action("Explorer", "Refresh", self.refresh_action)
        self.toolbar.addAction(self.refresh_action)
        self.addAction(self.refresh_action)
        self.toolbar.addSeparator()
        self.add_current_folder_action = QAction(_("Add Current Folder to Library"), self)
        self.add_current_folder_action.triggered.connect(lambda: self.explorer.add_library_folder(self.explorer.current_path))
        key_config.bind_action("Explorer", "Add Current Folder to Library", self.add_current_folder_action)
        self.toolbar.addAction(self.add_current_folder_action)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.main_splitter, 1)
        self.library_group = QGroupBox(_("Library"))
        library_layout = QVBoxLayout(self.library_group)
        self.library_tree = LibraryTree(self.explorer)
        self.library_view = self.library_tree
        library_layout.addWidget(self.library_tree)
        self.main_splitter.addWidget(self.library_group)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.location_group = QGroupBox(_("Path && Search"))
        location_layout = QVBoxLayout(self.location_group)
        path_row = QHBoxLayout()
        self.parent_btn = QPushButton(_("Parent Directory"))
        self.parent_btn.clicked.connect(self.go_up)
        self.path_edit = QLineEdit()
        self.path_edit.setAccessibleName(_("Current path"))
        self.path_edit.returnPressed.connect(self.set_path)
        path_row.addWidget(self.parent_btn)
        path_row.addWidget(self.path_edit, 1)
        location_layout.addLayout(path_row)
        self.search_edit = QComboBox()
        self.search_edit.setEditable(True)
        self.search_edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.search_bar = SearchLineEdit()
        self.search_bar.setPlaceholderText(_("Search current folder..."))
        self.search_edit.setLineEdit(self.search_bar)
        self.search_edit.setAccessibleName(_("Search current folder"))
        if prefs.get("store_search_history", True):
            self.search_edit.addItems(self._search_history())
        self.search_edit.setCurrentText("")
        self.search_bar.returnPressed.connect(self._on_search_submitted)
        self.search_bar.closed.connect(self.clear_search)
        location_layout.addWidget(self.search_edit)
        right_layout.addWidget(self.location_group)
        self.files_group = QGroupBox(_("Files"))
        files_layout = QVBoxLayout(self.files_group)
        self.files_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.file_list = FileListWidget()
        self.explorer_view = self.file_list
        self.image_preview_label = ImagePreview()
        self.files_splitter.addWidget(self.file_list)
        self.files_splitter.addWidget(self.image_preview_label)
        self.files_splitter.setStretchFactor(0, 3)
        self.files_splitter.setStretchFactor(1, 2)
        self.files_splitter.setCollapsible(1, True)
        files_layout.addWidget(self.files_splitter)
        right_layout.addWidget(self.files_group, 1)
        self.main_splitter.addWidget(right_panel)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([140, 500])
        self.set_view_mode(prefs.get("explorer_view_mode", "list") != "icon", persist=False)
        QWidget.setTabOrder(self.library_tree, self.parent_btn)
        QWidget.setTabOrder(self.parent_btn, self.path_edit)
        QWidget.setTabOrder(self.path_edit, self.search_edit)
        QWidget.setTabOrder(self.search_edit, self.file_list)

    def setup_shortcuts(self):
        context = Qt.ShortcutContext.WidgetWithChildrenShortcut
        for action, parent, callback in (
            ("Search files", self, self.focus_search),
            ("Focus Path", self, self.focus_path),
            ("Go Up", self, self.go_up),
            ("Open Selected", self.file_list, self.file_list.open_selected),
            ("Add to Favorites", self.file_list, self.add_selected_to_favorites),
            ("Add Folder to Library", self, self.add_folder_to_library),
        ):
            key_config.make_shortcut("Explorer", action, parent, callback, context)
        for action in (self.view_list_action, self.view_icon_action, self.add_current_folder_action):
            action.setShortcutContext(context)
            self.addAction(action)

    def focus_search(self):
        self.search_edit.setFocus()
        self.search_bar.selectAll()

    def focus_path(self):
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    def set_path(self):
        text = self.path_edit.text().strip().strip('"')
        path = "drives" if text.casefold() == "drives" else os.path.expandvars(os.path.expanduser(text))
        if path != "drives" and not os.path.isabs(path):
            path = os.path.join(self.explorer.current_path, path)
        if not text or not self.explorer.navigate_to(path):
            QMessageBox.warning(self, _("Invalid Folder"), _("Please select a valid, existing folder."))
            self.path_edit.setText(self.explorer.current_path)
            self.path_edit.setFocus()
        else:
            self.clear_search()
            self.file_list.setFocus()

    def go_up(self):
        previous = self.explorer.current_path
        if self.explorer.go_up():
            for index in range(self.file_list.count()):
                item = self.file_list.item(index)
                if os.path.normcase(item.data(Qt.ItemDataRole.UserRole)["full_path"]) == os.path.normcase(previous):
                    self.file_list.setCurrentItem(item)
                    break

    def add_selected_to_favorites(self):
        for item in self.file_list.selectedItems():
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data["is_image"]:
                self.explorer.add_favorite(data["full_path"])

    def add_folder_to_library(self):
        item = self.file_list.currentItem()
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        path = data["full_path"] if data and data["is_directory"] else self.explorer.current_path
        self.explorer.add_library_folder(path)

    def connect_signals(self):
        self.explorer.path_changed.connect(self._on_path_changed)
        self.file_list.directory_entered.connect(self.explorer.navigate_to)
        self.file_list.file_selected.connect(self._on_file_selected)
        self.file_list.open_image.connect(self.open_image.emit)
        self.file_list.add_to_library_requested.connect(self.explorer.add_library_folder)
        self.file_list.add_to_favorites_requested.connect(self.explorer.add_favorite)
        self.file_list.refresh_requested.connect(self.refresh_view)
        self.file_list.options_menu_requested.connect(self._add_options_menus)
        self.library_tree.folder_activated.connect(self.explorer.navigate_to)
        self.file_list.verticalScrollBar().valueChanged.connect(self._load_near_bottom)
        self.file_list.currentItemChanged.connect(self._load_near_selection)

    def _on_path_changed(self, path):
        self.path_edit.setText(path)
        self.clear_search(focus=False)

    def _on_file_selected(self, path):
        was_hidden = self.image_preview_label.isHidden()
        self.image_preview_label.set_preview(path)
        if path and was_hidden and not self.image_preview_label.isHidden():
            total = max(1, self.files_splitter.width())
            preview_width = min(200, max(80, total // 3))
            self.files_splitter.setSizes([max(120, total - preview_width), preview_width])
        self.file_selected.emit(path)

    def clear_search(self, focus=True):
        self._search_worker.cancel()
        self._search_active = False
        self._search_query = ""
        self._search_root = ""
        self.search_edit.setCurrentText("")
        self.refresh_view()
        if focus:
            self.file_list.setFocus()

    @staticmethod
    def _search_history():
        history = prefs.get("search_history", [])
        return [item for item in history if isinstance(item, str)][:20] if isinstance(history, list) else []

    def _on_search_submitted(self):
        query = self.search_edit.currentText().strip()
        if not query:
            self.clear_search()
            return
        self._search_active = True
        self._search_query = query
        self._search_root = self.explorer.current_path
        if prefs.get("store_search_history", True):
            history = [query] + [item for item in self._search_history() if item != query]
            prefs["search_history"] = history[:20]
            self.search_edit.blockSignals(True)
            self.search_edit.clear()
            self.search_edit.addItems(history[:20])
            self.search_edit.setCurrentText(query)
            self.search_edit.blockSignals(False)
        self._search_worker.start_search(self._search_root, query)

    def _on_search_results(self, root, query, entries):
        if self._search_active and root == self._search_root and query == self._search_query:
            self._populate(self.explorer.filter_entries(entries))

    def _on_search_error(self, root, error):
        if self._search_active and root == self._search_root:
            QMessageBox.warning(self, _("Error"), _("Search failed: {error}").format(error=error))

    def refresh_view(self):
        if self._search_active:
            self._search_worker.start_search(self._search_root, self._search_query)
        else:
            self._populate(self.explorer.get_all_files())

    def _populate(self, entries):
        previous = self.file_list.currentItem()
        selected_path = previous.data(Qt.ItemDataRole.UserRole)["full_path"] if previous else None
        self.file_list.clear()
        self.image_preview_label.set_preview("")
        self._pending_entries = list(entries)
        self._load_more_entries()
        if selected_path:
            for index in range(self.file_list.count()):
                item = self.file_list.item(index)
                if item.data(Qt.ItemDataRole.UserRole)["full_path"] == selected_path:
                    self.file_list.setCurrentItem(item)
                    break

    def _load_more_entries(self):
        entries = self._pending_entries[:self.BATCH_SIZE]
        del self._pending_entries[:self.BATCH_SIZE]
        for name, is_dir, is_image, path in entries:
            item = QListWidgetItem(name)
            item.setIcon(self.file_list._get_file_icon(is_dir, is_image, name))
            item.setData(Qt.ItemDataRole.UserRole, {
                "name": name, "is_directory": is_dir, "is_image": is_image, "full_path": path,
            })
            parts = [_("Folder") if is_dir else os.path.splitext(path)[1].lstrip('.') or _("File")]
            try:
                info = os.stat(path)
                parts.append(datetime.fromtimestamp(info.st_mtime).strftime('%Y-%m-%d'))
                if not is_dir:
                    parts.append(get_file_size_str(info.st_size))
            except (OSError, ValueError, OverflowError):
                pass
            item.setData(DETAILS_ROLE, " · ".join(parts))
            item.setToolTip(f"{path}\n{' · '.join(parts)}")
            self.file_list.addItem(item)

    def _load_near_bottom(self, value):
        if self._pending_entries and value >= self.file_list.verticalScrollBar().maximum() - 60:
            self._load_more_entries()

    def _load_near_selection(self, current, previous):
        if current is not None and self._pending_entries and self.file_list.row(current) >= self.file_list.count() - 10:
            self._load_more_entries()

    def set_view_mode(self, list_mode, persist=True):
        self.file_list.set_view_mode(list_mode)
        self.view_list_action.setChecked(list_mode)
        self.view_icon_action.setChecked(not list_mode)
        if persist:
            prefs["explorer_view_mode"] = "list" if list_mode else "icon"

    def _set_sort(self, mode):
        self.explorer.sort_mode = mode
        prefs["explorer_sort_mode"] = mode
        self.refresh_view()

    def _set_filter(self, mode, extension=""):
        self.explorer.filter_mode = mode
        self.explorer.filter_extension = extension
        prefs["explorer_filter_mode"] = mode
        prefs["explorer_filter_format"] = extension
        self.refresh_view()

    def _custom_filter(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(_("Filter by Format"))
        layout = QVBoxLayout(dialog)
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(['jpg', 'jpeg', 'png', 'bmp', 'gif', 'tiff', 'tif', 'webp'])
        combo.setCurrentText(self.explorer.filter_extension)
        combo.setAccessibleName(_("Format (extension):"))
        layout.addWidget(QLabel(_("Format (extension):")))
        layout.addWidget(combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            extension = combo.currentText().strip().lstrip('.').casefold()
            if extension:
                self._set_filter("custom", extension)
        dialog.deleteLater()

    def _add_options_menus(self, menu):
        view = menu.addMenu(_("View"))
        view.addAction(self.view_list_action)
        view.addAction(self.view_icon_action)
        sort = menu.addMenu(_("Sort by"))
        for label, mode in ((_("Name (A–Z)"), "name_asc"), (_("Name (Z–A)"), "name_desc"),
                            (_("Newest first"), "date_newest"), (_("Oldest first"), "date_oldest")):
            action = sort.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.explorer.sort_mode == mode)
            action.triggered.connect(lambda checked=False, selected=mode: self._set_sort(selected))
        filters = menu.addMenu(_("Filter"))
        group = QActionGroup(filters)
        group.setExclusive(True)
        for label, mode in ((_("All Files"), "all"), (_("Images"), "images")):
            action = filters.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.explorer.filter_mode == mode)
            action.triggered.connect(lambda checked=False, selected=mode: self._set_filter(selected))
            group.addAction(action)
        custom = filters.addAction(_("Custom Format..."))
        custom.setCheckable(True)
        custom.setChecked(self.explorer.filter_mode == "custom")
        custom.triggered.connect(self._custom_filter)
        group.addAction(custom)
