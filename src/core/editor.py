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
