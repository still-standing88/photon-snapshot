# Project Snapshot: src

Generated on: The current date is: Thu 07/03/2025 
Enter the new date: (mm-dd-yy)

## Table of Contents

- [Directory: core](#directory-core)
- [Directory: gui](#directory-gui)

## Files


<a name="directory-root"></a>
### Directory: `Root`


#### File: `app.py`

```python
import sys
import os
import app_guard

from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QColor

from gui.main_window import MainWindow
from taskbar_icon import TaskbarIcon


def setup_application_style(app: QApplication):
    app.setStyle('Fusion')
    
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(66, 66, 66))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(0, 0, 0))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(64, 64, 64))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))    
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))

    app.setPalette(dark_palette)


def main():
    if getattr(sys, 'frozen', False):
        BASE_DIR = Path(sys.executable).parent
        os.environ['QT_PLUGIN_PATH'] = str(BASE_DIR / "PySide6" / "qt-plugins")
    else:
        BASE_DIR = Path(__file__).parent

    cli_args = sys.argv
    instance = app_guard.AppGuard()
    app = QApplication(sys.argv)

    instance.init("photon_snapshot", lambda: None, False)
    if not instance.is_primary_instance() and cli_args:
        instance.send_msg_request("cli-args", cli_args[1])
        instance.release()
        exit(0)

    app.setApplicationName("Photon Snapshot")
    app.setApplicationVersion("1.0.0")
    setup_application_style(app)

    window = MainWindow()
    taskbar_icon = TaskbarIcon(window)
    cli_args_msg:app_guard.IPCMsg = instance.create_ipc_msg("cli-args",
        window.cli_load_file
    )
    instance.register_msg(cli_args_msg)

    if len(cli_args) > 1:
        window.load_file(cli_args[1])
        instance.focus_window("Photon Snapshot")

    window.show()
    taskbar_icon.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

#### File: `project_snapshot.md`

```markdown

```

#### File: `taskbar_icon.py`

```python
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QObject
import resources_rc


class TaskbarIcon(QObject):


    def __init__(self, window):
        super().__init__(window)
        self.window = window
        
        self.tray_icon = QSystemTrayIcon(self)
        
        icon = QIcon(":icons/photon-snapshot.png")
        self.tray_icon.setIcon(icon)
        
        self.create_menu()
        self.tray_icon.setToolTip("Photon Snapshot")
        self.tray_icon.activated.connect(self.on_tray_activated)
    
    def create_menu(self):
        menu = QMenu()
        
        self.show_action = QAction("Show", self)
        self.show_action.triggered.connect(self.on_show_window)
        menu.addAction(self.show_action)
        
        menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.window.close)
        menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(menu)
    
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()
    
    def on_show_window(self):
        if self.window.isVisible():
            self.show_action.setText("Show")
            self.hide_window()
        else:
            self.show_action.setText("Hide")
            self.show_window()

    def show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()
    
    def hide_window(self):
        self.window.hide()
    
    def show(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()
            return True
        return False
```

<a name="directory-core"></a>
### Directory: `core`


#### File: `core\__init__.py`

```python
from .image import PhotonImage
from .actions import *
from .editor import Editor, EditorState
from .explorer import FileExplorer
from .overlays import *
from .utils import *
```

#### File: `core\actions.py`

```python
from abc import ABC, abstractmethod
from typing import Any, Optional
from .image import PhotonImage


class Action(ABC):
    def __init__(self, name: str):
        self.name = name
        self.image_before: Optional[PhotonImage] = None
        self.image_after: Optional[PhotonImage] = None
    
    @abstractmethod
    def execute(self, image: PhotonImage) -> PhotonImage:
        pass
    
    @abstractmethod
    def undo(self, image: PhotonImage) -> PhotonImage:
        pass


class BrightnessAction(Action):
    def __init__(self, factor: float):
        super().__init__(f"Brightness {factor}")
        self.factor = factor
    
    def execute(self, image: PhotonImage) -> PhotonImage:
        self.image_before = image.copy()
        image.apply_brightness(self.factor)
        self.image_after = image.copy()
        return image
    
    def undo(self, image: PhotonImage) -> PhotonImage:
        if self.image_before:
            image.current = self.image_before.current.copy()
            image.applied_filters = self.image_before.applied_filters.copy()
        return image


class ContrastAction(Action):
    def __init__(self, factor: float):
        super().__init__(f"Contrast {factor}")
        self.factor = factor
    
    def execute(self, image: PhotonImage) -> PhotonImage:
        self.image_before = image.copy()
        image.apply_contrast(self.factor)
        self.image_after = image.copy()
        return image
    
    def undo(self, image: PhotonImage) -> PhotonImage:
        if self.image_before:
            image.current = self.image_before.current.copy()
            image.applied_filters = self.image_before.applied_filters.copy()
        return image


class GrayscaleAction(Action):
    def __init__(self):
        super().__init__("Grayscale")
    
    def execute(self, image: PhotonImage) -> PhotonImage:
        self.image_before = image.copy()
        image.apply_grayscale()
        self.image_after = image.copy()
        return image
    
    def undo(self, image: PhotonImage) -> PhotonImage:
        if self.image_before:
            image.current = self.image_before.current.copy()
            image.applied_filters = self.image_before.applied_filters.copy()
        return image


class InvertAction(Action):
    def __init__(self):
        super().__init__("Invert Colors")
    
    def execute(self, image: PhotonImage) -> PhotonImage:
        self.image_before = image.copy()
        image.apply_invert()
        self.image_after = image.copy()
        return image
    
    def undo(self, image: PhotonImage) -> PhotonImage:
        if self.image_before:
            image.current = self.image_before.current.copy()
            image.applied_filters = self.image_before.applied_filters.copy()
        return image


class SepiaAction(Action):
    def __init__(self):
        super().__init__("Sepia")
    
    def execute(self, image: PhotonImage) -> PhotonImage:
        self.image_before = image.copy()
        image.apply_sepia()
        self.image_after = image.copy()
        return image
    
    def undo(self, image: PhotonImage) -> PhotonImage:
        if self.image_before:
            image.current = self.image_before.current.copy()
            image.applied_filters = self.image_before.applied_filters.copy()
        return image


class RotateAction(Action):
    def __init__(self, degrees: float):
        super().__init__(f"Rotate {degrees}°")
        self.degrees = degrees
    
    def execute(self, image: PhotonImage) -> PhotonImage:
        self.image_before = image.copy()
        image.rotate(self.degrees)
        self.image_after = image.copy()
        return image
    
    def undo(self, image: PhotonImage) -> PhotonImage:
        if self.image_before:
            image.current = self.image_before.current.copy()
            image.applied_filters = self.image_before.applied_filters.copy()
        return image


class FlipAction(Action):
    def __init__(self, direction: str):
        super().__init__(f"Flip {direction}")
        self.direction = direction
    
    def execute(self, image: PhotonImage) -> PhotonImage:
        self.image_before = image.copy()
        if self.direction == "horizontal":
            image.flip_horizontal()
        elif self.direction == "vertical":
            image.flip_vertical()
        self.image_after = image.copy()
        return image
    
    def undo(self, image: PhotonImage) -> PhotonImage:
        if self.image_before:
            image.current = self.image_before.current.copy()
            image.applied_filters = self.image_before.applied_filters.copy()
        return image


class CropAction(Action):
    def __init__(self, box: tuple):
        super().__init__("Crop")
        self.box = box
    
    def execute(self, image: PhotonImage) -> PhotonImage:
        self.image_before = image.copy()
        image.crop(self.box)
        self.image_after = image.copy()
        return image
    
    def undo(self, image: PhotonImage) -> PhotonImage:
        if self.image_before:
            image.current = self.image_before.current.copy()
            image.applied_filters = self.image_before.applied_filters.copy()
        return image


class ResizeAction(Action):
    def __init__(self, size: tuple, keep_aspect: bool = True):
        super().__init__(f"Resize {size}")
        self.size = size
        self.keep_aspect = keep_aspect
    
    def execute(self, image: PhotonImage) -> PhotonImage:
        self.image_before = image.copy()
        image.resize(self.size, self.keep_aspect)
        self.image_after = image.copy()
        return image
    
    def undo(self, image: PhotonImage) -> PhotonImage:
        if self.image_before:
            image.current = self.image_before.current.copy()
            image.applied_filters = self.image_before.applied_filters.copy()
        return image
```

#### File: `core\editor.py`

```python
from typing import List, Optional, Callable
from .image import PhotonImage
from .actions import Action


class EditorState:
    def __init__(self):
        self.current_image: Optional[PhotonImage] = None
        self.history: List[Action] = []
        self.current_index = -1
        self.max_history_size = 50
        self.on_state_changed: Optional[Callable] = None
    
    def load_image(self, image: PhotonImage):
        self.current_image = image
        self.history.clear()
        self.current_index = -1
        self._notify_state_changed()
    
    def execute_action(self, action: Action):
        if not self.current_image:
            return
        
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]
        
        action.execute(self.current_image)
        self.history.append(action)
        self.current_index += 1
        
        if len(self.history) > self.max_history_size:
            self.history.pop(0)
            self.current_index -= 1
        
        self._notify_state_changed()
    
    def undo(self) -> bool:
        if not self.can_undo():
            return False
        
        action = self.history[self.current_index]
        action.undo(self.current_image)
        self.current_index -= 1
        self._notify_state_changed()
        return True
    
    def redo(self) -> bool:
        if not self.can_redo():
            return False
        
        self.current_index += 1
        action = self.history[self.current_index]
        action.execute(self.current_image)
        self._notify_state_changed()
        return True
    
    def can_undo(self) -> bool:
        return self.current_index >= 0
    
    def can_redo(self) -> bool:
        return self.current_index < len(self.history) - 1
    
    def get_current_action_name(self) -> str:
        if self.current_index >= 0 and self.current_index < len(self.history):
            return self.history[self.current_index].name
        return "No action"
    
    def get_history_names(self) -> List[str]:
        return [action.name for action in self.history]
    
    def reset_to_original(self):
        if self.current_image:
            self.current_image.reset_to_original()
            self.history.clear()
            self.current_index = -1
            self._notify_state_changed()
    
    def _notify_state_changed(self):
        if self.on_state_changed:
            self.on_state_changed()


class Editor:
    def __init__(self):
        self.state = EditorState()
    
    def set_state_change_callback(self, callback: Callable):
        self.state.on_state_changed = callback
    
    def load_image_from_file(self, filepath: str):
        try:
            image = PhotonImage.from_file(filepath)
            self.state.load_image(image)
            return True
        except Exception as e:
            print(f"Error loading image: {e}")
            return False
    
    def load_image(self, image: PhotonImage):
        self.state.load_image(image)
    
    def apply_brightness(self, factor: float):
        from .actions import BrightnessAction
        action = BrightnessAction(factor)
        self.state.execute_action(action)
    
    def apply_contrast(self, factor: float):
        from .actions import ContrastAction
        action = ContrastAction(factor)
        self.state.execute_action(action)
    
    def apply_grayscale(self):
        from .actions import GrayscaleAction
        action = GrayscaleAction()
        self.state.execute_action(action)
    
    def apply_invert(self):
        from .actions import InvertAction
        action = InvertAction()
        self.state.execute_action(action)
    
    def apply_sepia(self):
        from .actions import SepiaAction
        action = SepiaAction()
        self.state.execute_action(action)
    
    def rotate(self, degrees: float):
        from .actions import RotateAction
        action = RotateAction(degrees)
        self.state.execute_action(action)
    
    def flip_horizontal(self):
        from .actions import FlipAction
        action = FlipAction("horizontal")
        self.state.execute_action(action)
    
    def flip_vertical(self):
        from .actions import FlipAction
        action = FlipAction("vertical")
        self.state.execute_action(action)
    
    def crop(self, box: tuple):
        from .actions import CropAction
        action = CropAction(box)
        self.state.execute_action(action)
    
    def resize(self, size: tuple, keep_aspect: bool = True):
        from .actions import ResizeAction
        action = ResizeAction(size, keep_aspect)
        self.state.execute_action(action)
    
    def undo(self) -> bool:
        return self.state.undo()
    
    def redo(self) -> bool:
        return self.state.redo()
    
    def can_undo(self) -> bool:
        return self.state.can_undo()
    
    def can_redo(self) -> bool:
        return self.state.can_redo()
    
    def reset_to_original(self):
        self.state.reset_to_original()
    
    def save_image(self, filepath: str, format: str = None, quality: int = 95):
        if self.state.current_image:
            self.state.current_image.save(filepath, format, quality)
    
    @property
    def current_image(self) -> Optional[PhotonImage]:
        return self.state.current_image
```

#### File: `core\explorer.py`

```python
import os
import json
from typing import List, Optional, Callable
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from .utils import is_image_file


class FileExplorer(QObject):
    path_changed = Signal(str)
    selection_changed = Signal(str)
    recent_files_updated = Signal(list)
    
    def __init__(self):
        super().__init__()
        self.current_path = str(Path.home())
        self.history: List[str] = []
        self.history_index = -1
        self.max_history = 100
        self.recent_files: List[str] = []
        self.max_recent_files = 10
        
        self._load_config()
    
    def navigate_to(self, path: str):
        if os.path.exists(path) and os.path.isdir(path):
            if self.history_index < len(self.history) - 1:
                self.history = self.history[:self.history_index + 1]
            
            self.history.append(self.current_path)
            if len(self.history) > self.max_history:
                self.history.pop(0)
            else:
                self.history_index += 1
            
            self.current_path = path
            self._save_config()
            self.path_changed.emit(self.current_path)
    
    def go_back(self) -> bool:
        if self.can_go_back():
            self.current_path = self.history[self.history_index]
            self.history_index -= 1
            self.path_changed.emit(self.current_path)
            return True
        return False
    
    def go_forward(self) -> bool:
        if self.can_go_forward():
            self.history_index += 1
            self.current_path = self.history[self.history_index]
            self.path_changed.emit(self.current_path)
            return True
        return False
    
    def can_go_back(self) -> bool:
        return self.history_index >= 0
    
    def can_go_forward(self) -> bool:
        return self.history_index < len(self.history) - 1
    
    def go_up(self) -> bool:
        parent = str(Path(self.current_path).parent)
        if parent != self.current_path:
            self.navigate_to(parent)
            return True
        return False
    
    def get_drives(self) -> List[str]:
        if os.name == 'nt':
            drives = []
            for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append(drive)
            return drives
        else:
            return ['/']
    
    def get_directories(self, path: str = None) -> List[str]:
        path = path or self.current_path
        try:
            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    items.append(item)
            return sorted(items, key=str.lower)
        except (PermissionError, OSError):
            return []
    
    def get_image_files(self, path: str = None) -> List[str]:
        path = path or self.current_path
        try:
            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isfile(item_path) and is_image_file(item):
                    items.append(item)
            return sorted(items, key=str.lower)
        except (PermissionError, OSError):
            return []
    
    def get_all_files(self, path: str = None) -> List[tuple]:
        path = path or self.current_path
        try:
            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                is_dir = os.path.isdir(item_path)
                is_image = is_image_file(item) if not is_dir else False
                items.append((item, is_dir, is_image, item_path))
            
            items.sort(key=lambda x: (not x[1], x[0].lower()))
            return items
        except (PermissionError, OSError):
            return []
    
    def get_full_path(self, filename: str) -> str:
        return os.path.join(self.current_path, filename)
    
    def add_recent_file(self, file_path: str):
        if not os.path.exists(file_path) or not is_image_file(file_path):
            return
            
            self.recent_files.remove(file_path)
        
        self.recent_files.insert(0, file_path)
        
        if len(self.recent_files) > self.max_recent_files:
            self.recent_files = self.recent_files[:self.max_recent_files]
        
        self.recent_files = [f for f in self.recent_files if os.path.exists(f)]
        
        self._save_config()
        self.recent_files_updated.emit(self.recent_files.copy())
    
    def get_recent_files(self) -> List[str]:
        self.recent_files = [f for f in self.recent_files if os.path.exists(f)]
        return self.recent_files.copy()
    
    def clear_recent_files(self):
        self.recent_files.clear()
        self._save_config()
        self.recent_files_updated.emit([])
    
    def _save_config(self):
        try:
            config_dir = Path.home() / '.photon_snapshot'
            config_dir.mkdir(exist_ok=True)
            config_file = config_dir / 'config.json'
            
            config = {
                'last_path': self.current_path,
                'recent_files': self.recent_files
            }
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Failed to save config: {e}")
    
    def _load_config(self):
        try:
            config_file = Path.home() / '.photon_snapshot' / 'config.json'
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                if 'last_path' in config:
                    path = config['last_path']
                    if os.path.exists(path) and os.path.isdir(path):
                        self.current_path = path
                
                if 'recent_files' in config:
                    self.recent_files = [f for f in config['recent_files'] if os.path.exists(f)]
        except Exception as e:
            print(f"Failed to load config: {e}")
```

#### File: `core\image.py`

```python
from PIL import Image as PILImage, ImageEnhance, ImageOps, ImageFilter, ImageDraw, ImageFont
from typing import Optional, Tuple, List, Any
import io
import copy


class PhotonImage:
    def __init__(self, pil_image: PILImage.Image):
        self.original = pil_image.copy()
        self.current = pil_image.copy()
        self.format = pil_image.format or 'PNG'
        self.applied_filters = []
        self.metadata = {}
        
    @classmethod
    def from_file(cls, filepath: str) -> 'PhotonImage':
        pil_img = PILImage.open(filepath)
        return cls(pil_img)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'PhotonImage':
        pil_img = PILImage.open(io.BytesIO(data))
        return cls(pil_img)
    
    def copy(self) -> 'PhotonImage':
        new_img = PhotonImage(self.current)
        new_img.original = self.original.copy()
        new_img.format = self.format
        new_img.applied_filters = self.applied_filters.copy()
        new_img.metadata = self.metadata.copy()
        return new_img
    
    def reset_to_original(self):
        self.current = self.original.copy()
        self.applied_filters.clear()
    
    def apply_brightness(self, factor: float):
        enhancer = ImageEnhance.Brightness(self.current)
        self.current = enhancer.enhance(factor)
        self.applied_filters.append(('brightness', factor))
    
    def apply_contrast(self, factor: float):
        enhancer = ImageEnhance.Contrast(self.current)
        self.current = enhancer.enhance(factor)
        self.applied_filters.append(('contrast', factor))
    
    def apply_grayscale(self):
        self.current = ImageOps.grayscale(self.current).convert('RGB')
        self.applied_filters.append(('grayscale', None))
    
    def apply_invert(self):
        self.current = ImageOps.invert(self.current)
        self.applied_filters.append(('invert', None))
    
    def apply_sepia(self):
        pixels = self.current.load()
        width, height = self.current.size
        
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y][:3]
                tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                pixels[x, y] = (min(255, tr), min(255, tg), min(255, tb))
        
        self.applied_filters.append(('sepia', None))
    
    def rotate(self, degrees: float):
        self.current = self.current.rotate(degrees, expand=True)
        self.applied_filters.append(('rotate', degrees))
    
    def flip_horizontal(self):
        self.current = self.current.transpose(PILImage.FLIP_LEFT_RIGHT)
        self.applied_filters.append(('flip_horizontal', None))
    
    def flip_vertical(self):
        self.current = self.current.transpose(PILImage.FLIP_TOP_BOTTOM)
        self.applied_filters.append(('flip_vertical', None))
    
    def resize(self, size: Tuple[int, int], keep_aspect: bool = True):
        if keep_aspect:
            self.current.thumbnail(size, PILImage.Resampling.LANCZOS)
        else:
            self.current = self.current.resize(size, PILImage.Resampling.LANCZOS)
        self.applied_filters.append(('resize', size))
    
    def crop(self, box: Tuple[int, int, int, int]):
        self.current = self.current.crop(box)
        self.applied_filters.append(('crop', box))
    
    def to_bytes(self, format: str = None) -> bytes:
        format = format or self.format
        buffer = io.BytesIO()
        self.current.save(buffer, format=format)
        return buffer.getvalue()
    
    def save(self, filepath: str, format: str = None, quality: int = 95):
        format = format or self.format
        self.current.save(filepath, format=format, quality=quality)
    
    @property
    def size(self) -> Tuple[int, int]:
        return self.current.size
    
    @property
    def mode(self) -> str:
        return self.current.mode
```

#### File: `core\overlays.py`

```python
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
```

#### File: `core\utils.py`

```python
from PIL import Image as PILImage, ImageQt
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt
import io


def pil_to_qpixmap(pil_image: PILImage.Image) -> QPixmap:
    if pil_image.mode == "RGB":
        r, g, b = pil_image.split()
        pil_image = PILImage.merge("RGB", (b, g, r))
    elif pil_image.mode == "RGBA":
        r, g, b, a = pil_image.split()
        pil_image = PILImage.merge("RGBA", (b, g, r, a))
    elif pil_image.mode == "L":
        pil_image = pil_image.convert("RGB")
    
    qim = ImageQt.ImageQt(pil_image)
    qpixmap = QPixmap.fromImage(qim)
    return qpixmap


def qpixmap_to_pil(qpixmap: QPixmap) -> PILImage.Image:
    qimage = qpixmap.toImage()
    buffer = qimage.bits()
    width = qimage.width()
    height = qimage.height()
    
    if qimage.format() == QImage.Format_RGB32:
        pil_image = PILImage.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
    elif qimage.format() == QImage.Format_ARGB32:
        pil_image = PILImage.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1)
    else:
        qimage = qimage.convertToFormat(QImage.Format_RGB32)
        buffer = qimage.bits()
        pil_image = PILImage.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
    
    return pil_image


def get_image_formats():
    return {
        'JPEG': '*.jpg *.jpeg',
        'PNG': '*.png',
        'BMP': '*.bmp',
        'GIF': '*.gif',
        'TIFF': '*.tiff *.tif',
        'WEBP': '*.webp'
    }


def get_all_image_filter():
    formats = get_image_formats()
    all_formats = ' '.join(formats.values())
    return f"Image files ({all_formats})"


def get_save_formats():
    return ['JPEG', 'PNG', 'BMP', 'TIFF', 'WEBP']


def scale_pixmap_smooth(pixmap: QPixmap, size, keep_aspect_ratio=True) -> QPixmap:
    if keep_aspect_ratio:
        return pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    else:
        return pixmap.scaled(size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def create_thumbnail(pil_image: PILImage.Image, size=(128, 128)) -> QPixmap:
    thumbnail = pil_image.copy()
    thumbnail.thumbnail(size, PILImage.Resampling.LANCZOS)
    return pil_to_qpixmap(thumbnail)


def get_file_size_str(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def is_image_file(filename: str) -> bool:
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp'}
    return any(filename.lower().endswith(ext) for ext in image_extensions)
```

<a name="directory-gui"></a>
### Directory: `gui`


#### File: `gui\__init__.py`

```python
from .viewer import ImageViewer
from .explorer import ExplorerWidget
from .editor_panel import EditorPanel
from .main_window import MainWindow
```

#### File: `gui\editor_panel.py`

```python
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QSlider, QLabel, QPushButton, QSpinBox, QComboBox,
                             QFrame, QSizePolicy, QButtonGroup, QCheckBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from core.editor import Editor
from .overlay_panel import OverlayPanel


class SliderGroup(QWidget):
    value_changed = Signal(float)
    
    def __init__(self, title: str, min_val: float = 0.0, max_val: float = 2.0, 
                 default_val: float = 1.0, decimals: int = 2):
        super().__init__()
        self.min_val = min_val
        self.max_val = max_val
        self.decimals = decimals
        self.multiplier = 10 ** decimals
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        
        slider_layout = QHBoxLayout()
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(int(min_val * self.multiplier))
        self.slider.setMaximum(int(max_val * self.multiplier))
        self.slider.setValue(int(default_val * self.multiplier))
        self.slider.valueChanged.connect(self._on_slider_changed)
        
        self.value_label = QLabel(f"{default_val:.{decimals}f}")
        self.value_label.setMinimumWidth(50)
        self.value_label.setStyleSheet("color: #cccccc;")
        
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.value_label)
        
        layout.addWidget(self.title_label)
        layout.addLayout(slider_layout)
        
        self.setLayout(layout)
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #404040;
                height: 8px;
                background: #2b2b2b;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: 1px solid #005a9e;
                width: 18px;
                border-radius: 9px;
                margin: -5px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #106ebe;
            }
        """)
    
    def _on_slider_changed(self, value):
        real_value = value / self.multiplier
        self.value_label.setText(f"{real_value:.{self.decimals}f}")
        self.value_changed.emit(real_value)
    
    def set_value(self, value: float):
        self.slider.setValue(int(value * self.multiplier))


class EffectsPanel(QGroupBox):
    brightness_changed = Signal(float)
    contrast_changed = Signal(float)
    grayscale_applied = Signal()
    sepia_applied = Signal()
    invert_applied = Signal()
    
    def __init__(self):
        super().__init__("Effects & Adjustments")
        self.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout()
        
        self.brightness_slider = SliderGroup("Brightness", 0.0, 3.0, 1.0)
        self.contrast_slider = SliderGroup("Contrast", 0.0, 3.0, 1.0)
        
        self.brightness_slider.value_changed.connect(self.brightness_changed.emit)
        self.contrast_slider.value_changed.connect(self.contrast_changed.emit)
        
        effects_layout = QHBoxLayout()
        
        self.grayscale_btn = QPushButton("Grayscale")
        self.sepia_btn = QPushButton("Sepia")
        self.invert_btn = QPushButton("Invert")
        
        for btn in [self.grayscale_btn, self.sepia_btn, self.invert_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    border: 1px solid #555555;
                    color: #ffffff;
                    padding: 5px 10px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                QPushButton:pressed {
                    background-color: #303030;
                }
            """)
        
        self.grayscale_btn.clicked.connect(self.grayscale_applied.emit)
        self.sepia_btn.clicked.connect(self.sepia_applied.emit)
        self.invert_btn.clicked.connect(self.invert_applied.emit)
        
        effects_layout.addWidget(self.grayscale_btn)
        effects_layout.addWidget(self.sepia_btn)
        effects_layout.addWidget(self.invert_btn)
        
        layout.addWidget(self.brightness_slider)
        layout.addWidget(self.contrast_slider)
        layout.addLayout(effects_layout)
        
        self.setLayout(layout)
    
    def reset_sliders(self):
        self.brightness_slider.set_value(1.0)
        self.contrast_slider.set_value(1.0)


class TransformPanel(QGroupBox):
    rotate_90_cw = Signal()
    rotate_90_ccw = Signal()
    flip_horizontal = Signal()
    flip_vertical = Signal()
    
    def __init__(self):
        super().__init__("Transform")
        self.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout()
        
        rotate_layout = QHBoxLayout()
        
        self.rotate_cw_btn = QPushButton("↻ 90°")
        self.rotate_ccw_btn = QPushButton("↺ 90°")
        
        flip_layout = QHBoxLayout()
        
        self.flip_h_btn = QPushButton("↔ Flip H")
        self.flip_v_btn = QPushButton("↕ Flip V")
        
        for btn in [self.rotate_cw_btn, self.rotate_ccw_btn, 
                   self.flip_h_btn, self.flip_v_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    border: 1px solid #555555;
                    color: #ffffff;
                    padding: 5px 10px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                QPushButton:pressed {
                    background-color: #303030;
                }
            """)
        
        self.rotate_cw_btn.clicked.connect(self.rotate_90_cw.emit)
        self.rotate_ccw_btn.clicked.connect(self.rotate_90_ccw.emit)
        self.flip_h_btn.clicked.connect(self.flip_horizontal.emit)
        self.flip_v_btn.clicked.connect(self.flip_vertical.emit)
        
        rotate_layout.addWidget(self.rotate_cw_btn)
        rotate_layout.addWidget(self.rotate_ccw_btn)
        
        flip_layout.addWidget(self.flip_h_btn)
        flip_layout.addWidget(self.flip_v_btn)
        
        layout.addLayout(rotate_layout)
        layout.addLayout(flip_layout)
        
        self.setLayout(layout)


class CropPanel(QGroupBox):
    crop_mode_toggled = Signal(bool)
    crop_applied = Signal()
    
    def __init__(self):
        super().__init__("Crop")
        self.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout()
        
        self.crop_mode_checkbox = QCheckBox("Crop Mode")
        self.crop_mode_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #2b2b2b;
                border: 1px solid #404040;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border: 1px solid #005a9e;
            }
        """)
        
        self.apply_crop_btn = QPushButton("Apply Crop")
        self.apply_crop_btn.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                color: #ffffff;
                padding: 5px 10px;
                border-radius: 3px;
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
        self.apply_crop_btn.setEnabled(False)
        
        self.crop_mode_checkbox.toggled.connect(self._on_crop_mode_toggled)
        self.apply_crop_btn.clicked.connect(self.crop_applied.emit)
        
        layout.addWidget(self.crop_mode_checkbox)
        layout.addWidget(self.apply_crop_btn)
        
        self.setLayout(layout)
    
    def _on_crop_mode_toggled(self, checked):
        self.apply_crop_btn.setEnabled(checked)
        self.crop_mode_toggled.emit(checked)


class EditorPanel(QWidget):
    def __init__(self, editor: Editor):
        super().__init__()
        self.editor = editor
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        self.setFixedWidth(250)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.effects_panel = EffectsPanel()
        self.transform_panel = TransformPanel()
        self.crop_panel = CropPanel()
        self.overlay_panel = OverlayPanel()
        
        layout.addWidget(self.effects_panel)
        layout.addWidget(self.transform_panel)
        layout.addWidget(self.crop_panel)
        layout.addWidget(self.overlay_panel)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def connect_signals(self):
        self.effects_panel.brightness_changed.connect(self.editor.apply_brightness)
        self.effects_panel.contrast_changed.connect(self.editor.apply_contrast)
        self.effects_panel.grayscale_applied.connect(self.editor.apply_grayscale)
        self.effects_panel.sepia_applied.connect(self.editor.apply_sepia)
        self.effects_panel.invert_applied.connect(self.editor.apply_invert)
        
        self.transform_panel.rotate_90_cw.connect(lambda: self.editor.rotate(90))
        self.transform_panel.rotate_90_ccw.connect(lambda: self.editor.rotate(-90))
        self.transform_panel.flip_horizontal.connect(self.editor.flip_horizontal)
        self.transform_panel.flip_vertical.connect(self.editor.flip_vertical)
    
    def reset_controls(self):
        self.effects_panel.reset_sliders()
        self.crop_panel.crop_mode_checkbox.setChecked(False)
```

#### File: `gui\explorer.py`

```python
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
```

#### File: `gui\main_window.py`

```python
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
```

#### File: `gui\overlay_panel.py`

```python
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QPushButton, QCheckBox, QSlider, QLabel, QLineEdit,
                             QComboBox, QSpinBox, QColorDialog, QInputDialog)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont


class OverlayPanel(QGroupBox):
    grid_toggled = Signal()
    ruler_toggled = Signal()
    pixel_info_toggled = Signal()
    text_overlay_requested = Signal(str, str, int, QColor, bool)  # text, position, font_size, color, show_background
    shape_mode_changed = Signal(str)
    overlays_cleared = Signal()
    
    def __init__(self):
        super().__init__("Overlays")
        self.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        basic_group = self._create_basic_overlays_group()
        layout.addWidget(basic_group)
        
        shape_group = self._create_shape_drawing_group()
        layout.addWidget(shape_group)
        
        text_group = self._create_text_overlay_group()
        layout.addWidget(text_group)
        
        self.clear_btn = QPushButton("Clear All Overlays")
        self.clear_btn.setStyleSheet(self._button_style())
        layout.addWidget(self.clear_btn)
        
        self.setLayout(layout)
    
    def _create_basic_overlays_group(self):
        group = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.grid_checkbox = QCheckBox("Grid Overlay")
        self.grid_checkbox.setStyleSheet(self._checkbox_style())
        
        self.ruler_checkbox = QCheckBox("Ruler Overlay")
        self.ruler_checkbox.setStyleSheet(self._checkbox_style())
        
        self.pixel_info_checkbox = QCheckBox("Pixel Info Mode")
        self.pixel_info_checkbox.setStyleSheet(self._checkbox_style())
        
        layout.addWidget(self.grid_checkbox)
        layout.addWidget(self.ruler_checkbox)
        layout.addWidget(self.pixel_info_checkbox)
        
        group.setLayout(layout)
        return group
    
    def _create_shape_drawing_group(self):
        group = QGroupBox("Shape Drawing")
        group.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                border: 1px solid #404040;
                border-radius: 3px;
                margin-top: 8px;
                font-size: 11px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px 0 3px;
            }
        """)
        
        layout = QVBoxLayout()
        
        shape_buttons_layout = QHBoxLayout()
        
        self.rectangle_btn = QPushButton("Rectangle")
        self.rectangle_btn.setCheckable(True)
        self.rectangle_btn.setStyleSheet(self._toggle_button_style())
        
        self.circle_btn = QPushButton("Circle")
        self.circle_btn.setCheckable(True)
        self.circle_btn.setStyleSheet(self._toggle_button_style())
        
        self.line_btn = QPushButton("Line")
        self.line_btn.setCheckable(True)
        self.line_btn.setStyleSheet(self._toggle_button_style())
        
        shape_buttons_layout.addWidget(self.rectangle_btn)
        shape_buttons_layout.addWidget(self.circle_btn)
        shape_buttons_layout.addWidget(self.line_btn)
        
        layout.addLayout(shape_buttons_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_text_overlay_group(self):
        group = QGroupBox("Text Overlay")
        group.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                border: 1px solid #404040;
                border-radius: 3px;
                margin-top: 8px;
                font-size: 11px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px 0 3px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Text input row
        text_layout = QHBoxLayout()
        
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Enter text...")
        self.text_input.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b;
                border: 1px solid #404040;
                color: #ffffff;
                padding: 3px;
                border-radius: 3px;
            }
        """)
        
        text_layout.addWidget(self.text_input)
        layout.addLayout(text_layout)
        
        # Position and font size row
        pos_font_layout = QHBoxLayout()
        
        # Position dropdown
        pos_font_layout.addWidget(QLabel("Position:"))
        self.position_combo = QComboBox()
        self.position_combo.addItems([
            "Top Left", "Top Center", "Top Right",
            "Left Center", "Center", "Right Center", 
            "Bottom Left", "Bottom Center", "Bottom Right",
            "Click to Place"
        ])
        self.position_combo.setCurrentText("Click to Place")
        self.position_combo.setStyleSheet(self._combo_style())
        pos_font_layout.addWidget(self.position_combo)
        
        # Font size spinner
        pos_font_layout.addWidget(QLabel("Size:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(16)
        self.font_size_spin.setStyleSheet(self._spinbox_style())
        pos_font_layout.addWidget(self.font_size_spin)
        
        layout.addLayout(pos_font_layout)
        
        # Color and background row
        color_layout = QHBoxLayout()
        
        # Text color button
        self.text_color_btn = QPushButton("Text Color")
        self.text_color_btn.setStyleSheet(self._color_button_style(QColor(255, 255, 255)))
        self.text_color = QColor(255, 255, 255)
        color_layout.addWidget(self.text_color_btn)
        
        # Background toggle
        self.background_checkbox = QCheckBox("Background")
        self.background_checkbox.setChecked(True)
        self.background_checkbox.setStyleSheet(self._checkbox_style())
        color_layout.addWidget(self.background_checkbox)
        
        layout.addLayout(color_layout)
        
        # Add text button
        self.add_text_btn = QPushButton("Add Text")
        self.add_text_btn.setStyleSheet(self._button_style())
        layout.addWidget(self.add_text_btn)
        
        group.setLayout(layout)
        return group
    
    def connect_signals(self):
        self.grid_checkbox.toggled.connect(lambda: self.grid_toggled.emit())
        self.ruler_checkbox.toggled.connect(lambda: self.ruler_toggled.emit())
        self.pixel_info_checkbox.toggled.connect(lambda: self.pixel_info_toggled.emit())
        
        self.rectangle_btn.toggled.connect(lambda checked: self._on_shape_toggled("rectangle", checked))
        self.circle_btn.toggled.connect(lambda checked: self._on_shape_toggled("circle", checked))
        self.line_btn.toggled.connect(lambda checked: self._on_shape_toggled("line", checked))
        
        self.add_text_btn.clicked.connect(self._on_add_text_clicked)
        self.text_input.returnPressed.connect(self._on_add_text_clicked)
        self.text_color_btn.clicked.connect(self._on_text_color_clicked)
        
        self.clear_btn.clicked.connect(self.overlays_cleared.emit)
    
    def _on_shape_toggled(self, shape_type: str, checked: bool):
        if checked:
            for btn in [self.rectangle_btn, self.circle_btn, self.line_btn]:
                if btn.text().lower() != shape_type:
                    btn.setChecked(False)
            
            self.shape_mode_changed.emit(shape_type)
        else:
            self.shape_mode_changed.emit("")
    
    def _on_add_text_clicked(self):
        text = self.text_input.text().strip()
        if text:
            position = self.position_combo.currentText()
            font_size = self.font_size_spin.value()
            show_background = self.background_checkbox.isChecked()
            
            self.text_overlay_requested.emit(text, position, font_size, self.text_color, show_background)
            self.text_input.clear()
    
    def _on_text_color_clicked(self):
        color = QColorDialog.getColor(self.text_color, self, "Select Text Color")
        if color.isValid():
            self.text_color = color
            self.text_color_btn.setStyleSheet(self._color_button_style(color))
    
    def _button_style(self):
        return """
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                color: #ffffff;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #303030;
            }
        """
    
    def _toggle_button_style(self):
        return """
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                color: #ffffff;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #303030;
            }
            QPushButton:checked {
                background-color: #0078d4;
                border-color: #005a9e;
            }
        """
    
    def _checkbox_style(self):
        return """
            QCheckBox {
                color: #ffffff;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #2b2b2b;
                border: 1px solid #404040;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border: 1px solid #005a9e;
            }
        """
    
    def _combo_style(self):
        return """
            QComboBox {
                background-color: #2b2b2b;
                border: 1px solid #404040;
                color: #ffffff;
                padding: 2px 5px;
                border-radius: 3px;
                font-size: 10px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #ffffff;
                selection-background-color: #0078d4;
                border: 1px solid #404040;
            }
        """
    
    def _spinbox_style(self):
        return """
            QSpinBox {
                background-color: #2b2b2b;
                border: 1px solid #404040;
                color: #ffffff;
                padding: 2px;
                border-radius: 3px;
                font-size: 10px;
                max-width: 50px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #404040;
                border: 1px solid #555555;
                width: 12px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #505050;
            }
        """
    
    def _color_button_style(self, color: QColor):
        return f"""
            QPushButton {{
                background-color: {color.name()};
                border: 2px solid #555555;
                color: {'#000000' if color.lightness() > 128 else '#ffffff'};
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: #0078d4;
            }}
            QPushButton:pressed {{
                border-color: #005a9e;
            }}
        """
```

#### File: `gui\viewer.py`

```python
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
```
