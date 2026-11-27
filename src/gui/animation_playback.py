"""Monotonic, cumulative-deadline animation playback."""
import time
from PySide6.QtCore import QObject, QTimer, Signal

class AnimationPlayback(QObject):
    frame_changed = Signal(str)
    state_changed = Signal(bool)

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._tick)
        self.playing = False

    def toggle(self):
        self.stop() if self.playing else self.start()

    def start(self):
        document = self.editor.document
        if not document or not document.animation:
            return
        self.document_id = document.id
        self.index = next(i for i, f in enumerate(document.frames) if f.id == self.editor.state.active_frame_id)
        self.plays = 0
        self.deadline = time.monotonic() + document.frames[self.index].duration_ms/1000
        self.playing = True
        self.state_changed.emit(True)
        self._schedule()

    def stop(self):
        self.timer.stop()
        if self.playing:
            self.playing = False
            self.state_changed.emit(False)

    def _schedule(self):
        self.timer.start(max(1, int((self.deadline-time.monotonic())*1000)))

    def _tick(self):
        document = self.editor.document
        if not self.playing or not document or document.id != self.document_id:
            self.stop()
            return
        now = time.monotonic()
        while now >= self.deadline:
            self.index += 1
            if self.index >= len(document.frames):
                self.plays += 1
                if document.total_plays and self.plays >= document.total_plays:
                    self.stop()
                    return
                self.index = 0
            self.deadline += document.frames[self.index].duration_ms/1000
        frame = document.frames[self.index]
        self.editor.state.active_frame_id = frame.id
        self.frame_changed.emit(frame.id)
        self._schedule()
