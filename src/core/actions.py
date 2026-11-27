from abc import ABC, abstractmethod
from typing import Any, Optional
from .image import PhotonImage


class Action(ABC):
    """Base undoable action.

    Memory model: each action snapshots ONLY the 'current' pixels via
    PhotonImage.copy_current() (one buffer, sharing the immutable
    ``original`` by reference). The previous design stored a full
    before-copy AND an unused after-copy - each of which duplicated
    ``original`` too - so a 50-entry history held hundreds of full-image
    buffers. Snapshot/restore is also faster than re-executing.

    ``coalesce_key``: when set, EditorState merges a new action with the
    same key into the previous one (used by adjustment sliders so a drag
    produces ONE undo step instead of one per slider tick).
    """

    coalesce_key: Optional[str] = None

    def __init__(self, name: str):
        self.name = name
        self.image_before: Optional[PhotonImage] = None

    def execute(self, image: PhotonImage) -> PhotonImage:
        # Snapshot BEFORE mutating; copy_current() is independent of any
        # in-place edits _apply() may make (e.g. freehand strokes).
        self.image_before = image.copy_current()
        self._apply(image)
        return image

    def undo(self, image: PhotonImage) -> PhotonImage:
        if self.image_before is not None:
            image.restore_current(self.image_before)
        return image

    @abstractmethod
    def _apply(self, image: PhotonImage) -> PhotonImage:
        """Apply this action's edit to the image in place."""
        pass


class BrightnessAction(Action):
    coalesce_key = "brightness"

    def __init__(self, factor: float):
        super().__init__(f"Brightness {factor}")
        self.factor = factor

    def _apply(self, image: PhotonImage) -> PhotonImage:
        image.apply_brightness(self.factor)
        return image


class ContrastAction(Action):
    coalesce_key = "contrast"

    def __init__(self, factor: float):
        super().__init__(f"Contrast {factor}")
        self.factor = factor

    def _apply(self, image: PhotonImage) -> PhotonImage:
        image.apply_contrast(self.factor)
        return image


class GrayscaleAction(Action):
    def __init__(self):
        super().__init__("Grayscale")

    def _apply(self, image: PhotonImage) -> PhotonImage:
        image.apply_grayscale()
        return image


class InvertAction(Action):
    def __init__(self):
        super().__init__("Invert Colors")

    def _apply(self, image: PhotonImage) -> PhotonImage:
        image.apply_invert()
        return image


class SepiaAction(Action):
    def __init__(self):
        super().__init__("Sepia")

    def _apply(self, image: PhotonImage) -> PhotonImage:
        image.apply_sepia()
        return image


class EffectAction(Action):
    def __init__(self, effect_id, values, region=None):
        from .effects_catalog import EFFECTS, validate_effect
        self.values = validate_effect(effect_id, values)
        effect = EFFECTS[effect_id]
        if effect.category == 'Transform':
            raise ValueError('Use the canvas transform action for this edit')
        super().__init__(effect.label)
        self.effect_id = effect_id
        self.region = region

    def _apply(self, image: PhotonImage) -> PhotonImage:
        image.apply_effect(self.effect_id, self.values, region=self.region)
        return image


class RotateAction(Action):
    def __init__(self, degrees: float):
        super().__init__(f"Rotate {degrees}°")
        self.degrees = degrees

    def _apply(self, image: PhotonImage) -> PhotonImage:
        image.rotate(self.degrees)
        return image


class FlipAction(Action):
    def __init__(self, direction: str):
        super().__init__(f"Flip {direction}")
        self.direction = direction

    def _apply(self, image: PhotonImage) -> PhotonImage:
        if self.direction == "horizontal":
            image.flip_horizontal()
        elif self.direction == "vertical":
            image.flip_vertical()
        return image


class CropAction(Action):
    def __init__(self, box: tuple):
        super().__init__("Crop")
        self.box = box

    def _apply(self, image: PhotonImage) -> PhotonImage:
        image.crop(self.box)
        return image


class DrawStrokeAction(Action):
    """One freehand pen stroke committed to the pixels, from Canvas Drawing
    mode (see gui.viewer.ImageViewer.set_drawing_mode)."""

    def __init__(self, points: list, color: tuple, width: int):
        super().__init__("Draw Stroke")
        self.points = points
        self.color = color
        self.width = width

    def _apply(self, image: PhotonImage) -> PhotonImage:
        image.apply_freehand_stroke(self.points, self.color, self.width)
        return image


class ResizeAction(Action):
    def __init__(self, size: tuple, keep_aspect: bool = True):
        super().__init__(f"Resize {size}")
        self.size = size
        self.keep_aspect = keep_aspect

    def _apply(self, image: PhotonImage) -> PhotonImage:
        image.resize(self.size, self.keep_aspect)
        return image
