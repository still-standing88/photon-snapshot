from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QListWidgetItem, QLabel, QFrame, QPushButton, 
                             QLineEdit, QSplitter, QScrollArea, QSizePolicy, QMenu)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QPixmap, QIcon, QFont, QAction
from PySide6.QtWidgets import QApplication
from core.explorer import FileExplorer
from core.utils import create_thumbnail, is_image_file, get_file_size_str
from core.image import PhotonImage
import os
from pathlib import Path


class FileListWidget(QListWidget):
    file_selected = Signal(str)
    directory_entered = Signal(str)
    open_image = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: none;
                color: #ffffff;
                selection-background-color: #0078d4;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 8px;
                border: none;
                min-height: 20px;
                border-radius: 3px;
                margin: 1px;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #404040;
            }
            QListWidget::item:selected:hover {
                background-color: #106ebe;
            }
        """)
        
        self.setIconSize(QSize(16, 16))
        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
    
    def _get_file_icon(self, is_directory: bool, is_image: bool, file_name: str = "") -> QIcon:
        style = self.style()
        
        if is_directory:
            return style.standardIcon(style.StandardPixmap.SP_DirIcon)
        elif is_image:
            return style.standardIcon(style.StandardPixmap.SP_DesktopIcon)
        else:
            file_ext = os.path.splitext(file_name)[1].lower()
            if file_ext in ['.txt', '.md', '.log', '.py', '.js', '.html', '.css']:
                return style.standardIcon(style.StandardPixmap.SP_FileDialogDetailedView)
            elif file_ext in ['.exe', '.msi', '.app']:
                return style.standardIcon(style.StandardPixmap.SP_ComputerIcon)
            elif file_ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
                return style.standardIcon(style.StandardPixmap.SP_DriveHDIcon)
            else:
                return style.standardIcon(style.StandardPixmap.SP_FileIcon)
    
    def _on_item_clicked(self, item):
        data = item.data(Qt.UserRole)
        if data and data['is_image']:
            self.file_selected.emit(data['full_path'])
    
    def _on_item_double_clicked(self, item):
        data = item.data(Qt.UserRole)
        if data:
            if data['is_directory']:
                self.directory_entered.emit(data['full_path'])
            elif data['is_image']:
                self.open_image.emit(data['full_path'])
    
    def _show_context_menu(self, position):
        item = self.itemAt(position)
        if item:
            data = item.data(Qt.UserRole)
            if data and data['is_image']:
                menu = QMenu(self)
                menu.setStyleSheet("""
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
                
                open_action = QAction("Open Image", self)
                open_action.triggered.connect(lambda: self.open_image.emit(data['full_path']))
                menu.addAction(open_action)
                
                menu.exec_(self.mapToGlobal(position))


class PreviewPane(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(200)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-left: 1px solid #404040;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedSize(180, 180)
        self.preview_label.setStyleSheet("""
            QLabel {
                border: 1px solid #404040;
                background-color: #2b2b2b;
            }
        """)
        
        self.name_label = QLabel()
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        
        self.size_label = QLabel()
        self.size_label.setStyleSheet("color: #cccccc;")
        
        self.dimensions_label = QLabel()
        self.dimensions_label.setStyleSheet("color: #cccccc;")
        
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
        self.preview_label.setText("No preview")
        self.name_label.clear()
        self.size_label.clear()
        self.dimensions_label.clear()


class PathBar(QWidget):
    path_changed = Signal(str)
    
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.path_edit = QLineEdit()
        self.path_edit.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b;
                border: 1px solid #404040;
                color: #ffffff;
                padding: 5px;
                border-radius: 3px;
            }
        """)
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
        self.back_btn.setToolTip("Go Back")
        self.back_btn.setFixedSize(30, 30)
        self.back_btn.clicked.connect(self.back_clicked.emit)
        
        self.forward_btn = QPushButton()
        self.forward_btn.setIcon(style.standardIcon(style.StandardPixmap.SP_ArrowRight))
        self.forward_btn.setToolTip("Go Forward")
        self.forward_btn.setFixedSize(30, 30)
        self.forward_btn.clicked.connect(self.forward_clicked.emit)
        
        self.up_btn = QPushButton()
        self.up_btn.setIcon(style.standardIcon(style.StandardPixmap.SP_ArrowUp))
        self.up_btn.setToolTip("Go Up")
        self.up_btn.setFixedSize(30, 30)
        self.up_btn.clicked.connect(self.up_clicked.emit)
        
        for btn in [self.back_btn, self.forward_btn, self.up_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    border: 1px solid #555555;
                    color: #ffffff;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                QPushButton:pressed {
                    background-color: #303030;
                }
                QPushButton:disabled {
                    background-color: #2b2b2b;
                    color: #666666;
                }
            """)
        
        layout.addWidget(self.back_btn)
        layout.addWidget(self.forward_btn)
        layout.addWidget(self.up_btn)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def set_navigation_state(self, can_back: bool, can_forward: bool):
        self.back_btn.setEnabled(can_back)
        self.forward_btn.setEnabled(can_forward)


class ExplorerWidget(QWidget):
    file_selected = Signal(str)
    open_image = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.explorer = FileExplorer()
        self.setup_ui()
        self.connect_signals()
        self.refresh_view()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.nav_bar = NavigationBar()
        self.path_bar = PathBar()
        
        content_splitter = QSplitter(Qt.Horizontal)
        
        self.file_list = FileListWidget()
        self.preview_pane = PreviewPane()
        
        content_splitter.addWidget(self.file_list)
        content_splitter.addWidget(self.preview_pane)
        content_splitter.setSizes([300, 200])
        
        layout.addWidget(self.nav_bar)
        layout.addWidget(self.path_bar)
        layout.addWidget(content_splitter)
        
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
    
    def _on_path_changed(self, path: str):
        self.path_bar.set_path(path)
        self.nav_bar.set_navigation_state(
            self.explorer.can_go_back(), 
            self.explorer.can_go_forward()
        )
        self.refresh_view()
    
    def _on_file_selected(self, filepath: str):
        self.preview_pane.set_preview(filepath)
        self.file_selected.emit(filepath)
    
    def refresh_view(self):
        self.file_list.clear()
        files = self.explorer.get_all_files()
        
        for name, is_dir, is_image, full_path in files:
            item = QListWidgetItem()
            
            item.setText(name)
            
            icon = self.file_list._get_file_icon(is_dir, is_image, name)
            item.setIcon(icon)
            
            item.setData(Qt.UserRole, {
                'name': name,
                'is_directory': is_dir,
                'is_image': is_image,
                'full_path': full_path
            })
            
            if is_dir:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(Qt.GlobalColor.yellow)
            elif is_image:
                item.setForeground(Qt.GlobalColor.green)
            else:
                item.setForeground(Qt.GlobalColor.lightGray)
            
            self.file_list.addItem(item)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Backspace:
            self.explorer.go_back()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            current_item = self.file_list.currentItem()
            if current_item:
                data = current_item.data(Qt.UserRole)
                if data and data['is_directory']:
                    self.explorer.navigate_to(data['full_path'])
        else:
            super().keyPressEvent(event)