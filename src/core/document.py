"""Animation content; selection/playback belong to the editor view state."""
from dataclasses import dataclass, field
import copy
import uuid
from .image import PhotonImage
from .frame_store import FrameStore

def new_id():
    return uuid.uuid4().hex

@dataclass
class Frame:
    image: PhotonImage
    duration_ms: int = 100
    artwork: list = field(default_factory=list)
    id: str = field(default_factory=new_id)

    def snapshot(self, independent=False):
        return Frame(self.image.copy_current(), self.duration_ms, copy.deepcopy(self.artwork), new_id() if independent else self.id)

@dataclass
class Document:
    frames: list[Frame]
    source_format: str = 'PNG'
    total_plays: int = 1
    animation: bool = False
    metadata: dict = field(default_factory=dict)
    revision: int = 0
    id: str = field(default_factory=new_id)
    store: FrameStore = field(default_factory=FrameStore)
    import_notes: list = field(default_factory=list)

    @property
    def canvas_size(self):
        return self.frames[0].image.size

    @property
    def has_artwork(self):
        return any(f.artwork for f in self.frames)

    def frame(self, frame_id):
        return next(f for f in self.frames if f.id == frame_id)

    def snapshot(self):
        return Document([f.snapshot() for f in self.frames], self.source_format, self.total_plays,
                        self.animation, copy.deepcopy(self.metadata), self.revision, self.id,
                        self.store, list(self.import_notes))

    def validate(self):
        if not self.frames or len({f.id for f in self.frames}) != len(self.frames):
            raise ValueError('Document must contain uniquely identified frames')
        if any(f.image.size != self.canvas_size for f in self.frames):
            raise ValueError('All frames must use the same canvas size')
        if any(not isinstance(f.duration_ms, int) or not 1 <= f.duration_ms <= 3600000 for f in self.frames):
            raise ValueError('Frame duration must be between 1 and 3600000 milliseconds')
        if not isinstance(self.total_plays, int) or not 0 <= self.total_plays <= 65535:
            raise ValueError('Total plays must be 0 (infinite) or 1–65535')

    @classmethod
    def still(cls, image):
        return cls([Frame(image)], image.source_format, metadata=dict(image.metadata), store=image.store)
