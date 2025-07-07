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
