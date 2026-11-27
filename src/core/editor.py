from typing import Optional, Callable
import logging
from .image import PhotonImage
from .history import EditorState
logger = logging.getLogger(__name__)

class Editor:
    def __init__(self):
        self.state = EditorState()

    def set_state_change_callback(self, callback: Callable):
        self.state.on_state_changed = callback

    def load_image_from_file(self, filepath: str):
        try:
            from .animation_io import decode_document
            self.state.load_document(decode_document(filepath))
            return True
        except Exception:
            logger.exception("Error loading image: %s", filepath)
            return False

    def load_image(self, image: PhotonImage):
        self.state.load_image(image)

    def apply_brightness(self, factor: float):
        from .actions import BrightnessAction
        action = BrightnessAction(factor)
        self.state.execute_action(action, coalesce_key=BrightnessAction.coalesce_key)

    def apply_contrast(self, factor: float):
        from .actions import ContrastAction
        action = ContrastAction(factor)
        self.state.execute_action(action, coalesce_key=ContrastAction.coalesce_key)

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

    def apply_effect(self, effect_id, values, *, region=None):
        from .actions import EffectAction
        self.state.execute_action(EffectAction(effect_id, values, region))

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

    def draw_stroke(self, points: list, color: tuple, width: int):
        from .actions import DrawStrokeAction
        action = DrawStrokeAction(points, color, width)
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

    @property
    def is_dirty(self) -> bool:
        """True when there are unsaved edits (see EditorState.dirty)."""
        return self.state.dirty

    def mark_saved(self, state_id=None):
        """Clear the dirty flag after a successful save without touching
        the undo history."""
        self.state.saved_state_id = state_id or self.state.state_id
        self.state.end_gesture()

    @property
    def document(self):
        return self.state.document

    def load_document(self, document, unsaved=False):
        self.state.load_document(document, unsaved)

    def set_active_frame(self, frame_id, selection=None):
        self.state.set_active_frame(frame_id, selection)

    def duplicate_frames(self):
        ids = self.state.selected_frame_ids or {self.state.active_frame_id}
        def duplicate(document):
            document.frames = [result for frame in document.frames
                               for result in ([frame, frame.snapshot(True)] if frame.id in ids else [frame])]
            document.animation = True
        self.state.commit('Duplicate Frames', duplicate)

    def delete_frames(self):
        ids = self.state.selected_frame_ids or {self.state.active_frame_id}
        if len(ids) >= len(self.document.frames):
            return
        old_index = next(i for i, f in enumerate(self.document.frames) if f.id == self.state.active_frame_id)
        def delete(document):
            document.frames = [f for f in document.frames if f.id not in ids]
        self.state.commit('Delete Frames', delete)
        self.set_active_frame(self.document.frames[min(old_index, len(self.document.frames)-1)].id)

    def move_frames(self, direction):
        ids = self.state.selected_frame_ids or {self.state.active_frame_id}
        def move(document):
            indices = range(1, len(document.frames)) if direction < 0 else range(len(document.frames)-2, -1, -1)
            for index in indices:
                other = index + (-1 if direction < 0 else 1)
                if document.frames[index].id in ids and document.frames[other].id not in ids:
                    document.frames[index], document.frames[other] = document.frames[other], document.frames[index]
        self.state.commit('Move Frames', move)

    def reorder_frames(self, ordered_ids):
        if set(ordered_ids) != {f.id for f in self.document.frames}:
            raise ValueError('Invalid frame order')
        self.state.commit('Reorder Frames', lambda d: setattr(d, 'frames', [d.frame(i) for i in ordered_ids]))

    def set_duration(self, duration):
        ids = self.state.target_ids()
        def change(document):
            for frame_id in ids:
                document.frame(frame_id).duration_ms = duration
        self.state.commit('Frame Duration', change)

    def set_loop(self, total_plays):
        self.state.commit('Loop Policy', lambda d: setattr(d, 'total_plays', total_plays))

    def add_frames(self, frames):
        def append(document):
            document.frames.extend(f.snapshot(True) for f in frames)
            document.animation = True
        self.state.commit('Import Frames', append)

    def add_artwork(self, item):
        import copy
        from .artwork import validate_artwork
        validate_artwork(item)
        ids = self.state.target_ids()
        def add(document):
            for frame_id in ids:
                document.frame(frame_id).artwork.append(copy.deepcopy(item))
        self.state.commit('Add Artwork', add)

    def update_artwork(self, index, item):
        import copy
        from .artwork import validate_artwork
        validate_artwork(item)
        ids = self.state.target_ids()
        def edit(document):
            for frame_id in ids:
                artwork = document.frame(frame_id).artwork
                if index < len(artwork):
                    artwork[index] = copy.deepcopy(item)
        self.state.commit('Edit Artwork', edit)

    def clear_artwork(self):
        ids = self.state.target_ids()
        def clear(document):
            for frame_id in ids:
                document.frame(frame_id).artwork.clear()
        self.state.commit('Clear Artwork', clear)

    def reset_current_frame(self):
        frame_id = self.state.active_frame_id
        try:
            original = self.state.baseline.frame(frame_id).snapshot()
        except StopIteration:
            original = self.document.frame(frame_id).snapshot()
            original.image.reset_to_original()
            original.artwork.clear()
        def reset(document):
            frame = document.frame(frame_id)
            frame.image = original.image.copy_current()
            frame.artwork = original.artwork
        self.state.commit('Reset Current Frame', reset)
