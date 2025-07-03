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
