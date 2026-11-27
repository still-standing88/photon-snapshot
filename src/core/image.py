from PIL import Image, ImageOps
import io
from .frame_store import FrameStore
from .processing import apply_effect, resize, draw_stroke


class PhotonImage:
    def __init__(self, pil_image, store=None, source_format=None):
        self.store = store or FrameStore()
        self._current = self.store.put(pil_image)
        self._original = self._current
        self.source_format = source_format or pil_image.format or 'PNG'
        self.format = self.source_format
        self.applied_filters = []
        self.metadata = {k: pil_image.info[k] for k in ('icc_profile', 'exif') if k in pil_image.info}

    @property
    def current(self):
        return self._current.read()

    @current.setter
    def current(self, image):
        self._current = self.store.put(image)

    @property
    def original(self):
        return self._original.read()

    @original.setter
    def original(self, image):
        self._original = self.store.put(image)

    @classmethod
    def from_file(cls, filepath):
        with Image.open(filepath) as image:
            source_format = image.format
            if getattr(image, 'n_frames', 1) > 1:
                raise ValueError('Use document loading to preserve all animation frames')
            normalized = ImageOps.exif_transpose(image)
            normalized.load()
            return cls(normalized, source_format=source_format)

    @classmethod
    def from_bytes(cls, data):
        with Image.open(io.BytesIO(data)) as image:
            return cls(ImageOps.exif_transpose(image), source_format=image.format)

    def copy(self):
        return self.copy_current()

    def copy_current(self):
        result = PhotonImage.__new__(PhotonImage)
        result.store = self.store
        result._current, result._original = self._current, self._original
        result.source_format, result.format = self.source_format, self.format
        result.applied_filters = list(self.applied_filters)
        result.metadata = dict(self.metadata)
        return result

    def restore_current(self, snapshot):
        self._current = snapshot._current
        self.applied_filters = list(snapshot.applied_filters)

    def reset_to_original(self):
        self._current = self._original
        self.applied_filters.clear()

    def apply_effect(self, name, values=None, *, region=None):
        self.current = apply_effect(self.current, name, values, region=region)
        self.applied_filters.append((name, values))

    def apply_brightness(self, factor):
        self.apply_effect('brightness', {'factor': factor})

    def apply_contrast(self, factor):
        self.apply_effect('contrast', {'factor': factor})

    def apply_grayscale(self):
        self.apply_effect('grayscale')

    def apply_invert(self):
        self.apply_effect('invert')

    def apply_sepia(self):
        self.apply_effect('sepia')

    def rotate(self, degrees):
        self.apply_effect('rotate', {'degrees': degrees})

    def flip_horizontal(self):
        self.apply_effect('flip_horizontal')

    def flip_vertical(self):
        self.apply_effect('flip_vertical')

    def resize(self, size, keep_aspect=True):
        self.current = resize(self.current, size, 'fit' if keep_aspect else 'exact')
        self.applied_filters.append(('resize', size))

    def crop(self, box):
        self.apply_effect('crop', dict(left=box[0], top=box[1], width=box[2]-box[0], height=box[3]-box[1]))

    def apply_freehand_stroke(self, points, color, width):
        self.current = draw_stroke(self.current, points, color, width)
        self.applied_filters.append(('freehand_stroke', (len(points), width)))

    def to_bytes(self, format=None):
        from .export import encode_images, ExportOptions
        return encode_images([self.current], [100], 1, ExportOptions(format_id=format or self.format), self.metadata)

    def save(self, filepath, format=None, quality=95):
        from .export import export_images, ExportOptions
        from .formats import format_for_path
        fmt = format or format_for_path(filepath).id
        options = ExportOptions(format_id=fmt, quality=min(quality, 95 if fmt == 'JPEG' else 100))
        export_images(filepath, [self.current], [100], 1, options, self.metadata)
        self.format = fmt

    @property
    def size(self):
        return self._current.size

    @property
    def mode(self):
        return self._current.mode
