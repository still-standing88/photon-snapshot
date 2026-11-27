from typing import Optional, Callable
import logging
import copy
from dataclasses import dataclass
from .image import PhotonImage
from .actions import Action, CropAction, RotateAction, ResizeAction
from .document import Document, Frame, new_id
from .frame_store import DEFAULT_HISTORY_BYTES
logger = logging.getLogger(__name__)


@dataclass
class HistoryEntry:
    name: str
    before: Document
    after: Document
    before_id: str
    after_id: str
    coalesce_key: object = None


class EditorState:
    def __init__(self):
        self.document = None
        self.active_frame_id = None
        self.selected_frame_ids = set()
        self.scope = 'current'
        self.history = []
        self.current_index = -1
        self.max_history_size = 50
        self.history_budget = DEFAULT_HISTORY_BYTES
        self.on_state_changed = None
        self.state_id = new_id()
        self.saved_state_id = self.state_id
        self.baseline = None
        self.gesture = 0
        self.artwork_renderer = None
        self.on_before_edit = None
        self.processing_runner = None

    @property
    def current_image(self):
        return self.document.frame(self.active_frame_id).image if self.document else None

    @property
    def dirty(self):
        return self.state_id != self.saved_state_id

    @dirty.setter
    def dirty(self, value):
        self.saved_state_id = None if value else self.state_id

    def load_image(self, image):
        self.load_document(Document.still(image))

    def load_document(self, document, unsaved=False):
        document.validate()
        self.document = document
        self.active_frame_id = document.frames[0].id
        self.selected_frame_ids = {self.active_frame_id}
        self.history.clear()
        self.current_index = -1
        self.state_id = new_id()
        self.saved_state_id = None if unsaved else self.state_id
        self.baseline = document.snapshot()
        self.end_gesture()
        self._notify_state_changed()

    def end_gesture(self):
        self.gesture += 1

    def set_scope(self, scope):
        if scope not in ('current', 'selected', 'all'):
            raise ValueError('Invalid frame scope')
        self.scope = scope
        self.end_gesture()

    def set_active_frame(self, frame_id, selection=None):
        self.document.frame(frame_id)
        self.active_frame_id = frame_id
        self.selected_frame_ids = set(selection) if selection is not None else {frame_id}
        self.end_gesture()
        self._notify_state_changed()

    def target_ids(self, canvas=False):
        if canvas or self.scope == 'all':
            return tuple(f.id for f in self.document.frames)
        if self.scope == 'selected':
            return tuple(f.id for f in self.document.frames if f.id in self.selected_frame_ids)
        return (self.active_frame_id,)

    def commit(self, name, mutate, coalesce_key=None):
        if not self.document:
            return
        if self.on_before_edit:
            self.on_before_edit()
        document_id, revision = self.document.id, self.document.revision
        merge = self.current_index >= 0 and coalesce_key and self.history[self.current_index].coalesce_key == coalesce_key
        previous = self.history[self.current_index] if merge else None
        before = previous.before.snapshot() if merge else self.document.snapshot()
        before_id = previous.before_id if merge else self.state_id
        candidate = before.snapshot()
        mutate(candidate)
        candidate.validate()
        if self.document.id != document_id or self.document.revision != revision:
            from .export import CancelledError
            raise CancelledError('Document changed while the edit was being prepared')
        self.history[self.current_index+1:] = []
        candidate.revision = self.document.revision + 1
        after_id = new_id()
        entry = HistoryEntry(name, before, candidate.snapshot(), before_id, after_id, coalesce_key)
        if merge:
            self.history[self.current_index] = entry
        else:
            self.history.append(entry)
            self.current_index += 1
        self.document, self.state_id = candidate, after_id
        self._repair_selection()
        self._trim_history()
        self._notify_state_changed()

    def _trim_history(self):
        # Count unique pixel snapshots, including shared reference reuse.
        while self.history:
            retained = {id(f.image._current) for d in (self.document, self.baseline) if d for f in d.frames}
            refs = {id(f.image._current): f.image._current.byte_size for entry in self.history
                    for d in (entry.before, entry.after) for f in d.frames if id(f.image._current) not in retained}
            if len(self.history) <= self.max_history_size and sum(refs.values()) <= self.history_budget:
                break
            del self.history[0]
            self.current_index -= 1

    def _repair_selection(self):
        valid = {f.id for f in self.document.frames}
        self.selected_frame_ids &= valid
        if self.active_frame_id not in valid:
            self.active_frame_id = self.document.frames[0].id
        if not self.selected_frame_ids:
            self.selected_frame_ids = {self.active_frame_id}

    def execute_action(self, action, coalesce_key=None):
        if not self.current_image:
            return
        canvas = isinstance(action, (CropAction, RotateAction, ResizeAction))
        ids = self.target_ids(canvas)
        if not ids:
            return
        def mutate(document, checkpoint=lambda: None):
            from .artwork import transform_for_action
            for frame_id in ids:
                checkpoint()
                frame = document.frame(frame_id)
                old_size = frame.image.size
                action._apply(frame.image)
                frame.artwork = transform_for_action(frame.artwork, action, old_size, frame.image.size)
        key = (coalesce_key, ids, self.gesture) if coalesce_key else None
        if self.processing_runner and sum(self.document.frame(frame_id).image._current.byte_size for frame_id in ids) > 16*1024**2:
            from .export import CancelledError
            try:
                self.commit(action.name, lambda document: self.processing_runner(document, mutate, ids), key)
            except CancelledError:
                return
        else:
            self.commit(action.name, mutate, key)

    def undo(self):
        if not self.can_undo():
            return False
        entry = self.history[self.current_index]
        revision = self.document.revision + 1
        self.document = entry.before.snapshot()
        self.document.revision = revision
        self.state_id = entry.before_id
        self.current_index -= 1
        self._repair_selection()
        self.end_gesture()
        self._notify_state_changed()
        return True

    def redo(self):
        if not self.can_redo():
            return False
        self.current_index += 1
        entry = self.history[self.current_index]
        revision = self.document.revision + 1
        self.document = entry.after.snapshot()
        self.document.revision = revision
        self.state_id = entry.after_id
        self._repair_selection()
        self.end_gesture()
        self._notify_state_changed()
        return True

    def can_undo(self):
        return self.current_index >= 0

    def can_redo(self):
        return self.current_index < len(self.history)-1

    def get_current_action_name(self):
        return self.history[self.current_index].name if self.current_index >= 0 else 'No action'

    def get_history_names(self):
        return [entry.name for entry in self.history]

    def reset_to_original(self):
        if self.baseline:
            baseline = self.baseline.snapshot()
            def reset(document):
                document.frames = [f.snapshot() for f in baseline.frames]
                document.total_plays = baseline.total_plays
                document.animation = baseline.animation
            self.commit('Reset Document', reset)

    def _notify_state_changed(self):
        if self.on_state_changed:
            self.on_state_changed()
