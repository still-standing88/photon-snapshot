"""Immutable pixel references with a bounded cache and managed disk spill."""
from collections import OrderedDict
from pathlib import Path
import tempfile
import uuid
import weakref
import threading
from functools import wraps
from PIL import Image
DEFAULT_CACHE_BYTES = 256 * 1024**2
DEFAULT_HISTORY_BYTES = 128 * 1024**2
DEFAULT_IMPORT_BYTES = 1024**3

def synchronized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call

class PixelRef:
    def __init__(self, store, key, size, mode):
        self.store, self.key, self.size, self.mode = store, key, size, mode
        self.byte_size = size[0] * size[1] * Image.getmodebands(mode)
        self._cleanup = weakref.finalize(self, store.release, key)

    def read(self):
        return self.store.read(self.key)

class FrameStore:
    def __init__(self, cache_bytes=DEFAULT_CACHE_BYTES):
        self._lock = threading.RLock()
        self.cache_bytes = cache_bytes
        self._directory = tempfile.TemporaryDirectory(prefix='photon-frames-')
        self.cache = OrderedDict()
        self.memory_bytes = 0
        self.disk_bytes = 0

    def __del__(self):
        directory = getattr(self, '_directory', None)
        if directory:
            directory.cleanup()

    @synchronized
    def put(self, image):
        image = image.copy()
        key = uuid.uuid4().hex
        self.cache[key] = image
        self.memory_bytes += self._size(image)
        self._trim()
        return PixelRef(self, key, image.size, image.mode)

    @staticmethod
    def _size(image):
        return image.width * image.height * len(image.getbands())

    def _path(self, key):
        return Path(self._directory.name) / (key + '.png')

    def _trim(self):
        while self.memory_bytes > self.cache_bytes and self.cache:
            key, image = self.cache.popitem(last=False)
            try:
                image.save(self._path(key), format='PNG')
                self.disk_bytes += self._path(key).stat().st_size
            except OSError as exc:
                self.cache[key] = image
                raise OSError('Not enough temporary disk space for image frames') from exc
            self.memory_bytes -= self._size(image)

    @synchronized
    def read(self, key):
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key].copy()
        with Image.open(self._path(key)) as image:
            return image.copy()

    @synchronized
    def release(self, key):
        image = self.cache.pop(key, None)
        if image is not None:
            self.memory_bytes -= self._size(image)
        path = self._path(key)
        if path.exists():
            self.disk_bytes -= path.stat().st_size
            path.unlink(missing_ok=True)
