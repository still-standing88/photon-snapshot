from PIL import Image as PILImage, ImageEnhance, ImageOps, ImageFilter, ImageDraw, ImageFont
from typing import Optional, Tuple, List, Any
import io
import copy


class PhotonImage:
    def __init__(self, pil_image: PILImage.Image):
        self.original = pil_image.copy()
        self.current = pil_image.copy()
        self.format = pil_image.format or 'PNG'
        self.applied_filters = []
        self.metadata = {}
        
    @classmethod
    def from_file(cls, filepath: str) -> 'PhotonImage':
        pil_img = PILImage.open(filepath)
        return cls(pil_img)
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'PhotonImage':
        pil_img = PILImage.open(io.BytesIO(data))
        return cls(pil_img)
    
    def copy(self) -> 'PhotonImage':
        new_img = PhotonImage(self.current)
        new_img.original = self.original.copy()
        new_img.format = self.format
        new_img.applied_filters = self.applied_filters.copy()
        new_img.metadata = self.metadata.copy()
        return new_img
    
    def reset_to_original(self):
        self.current = self.original.copy()
        self.applied_filters.clear()
    
    def apply_brightness(self, factor: float):
        enhancer = ImageEnhance.Brightness(self.current)
        self.current = enhancer.enhance(factor)
        self.applied_filters.append(('brightness', factor))
    
    def apply_contrast(self, factor: float):
        enhancer = ImageEnhance.Contrast(self.current)
        self.current = enhancer.enhance(factor)
        self.applied_filters.append(('contrast', factor))
    
    def apply_grayscale(self):
        self.current = ImageOps.grayscale(self.current).convert('RGB')
        self.applied_filters.append(('grayscale', None))
    
    def apply_invert(self):
        self.current = ImageOps.invert(self.current)
        self.applied_filters.append(('invert', None))
    
    def apply_sepia(self):
        pixels = self.current.load()
        width, height = self.current.size
        
        for y in range(height):
            for x in range(width):
                r, g, b = pixels[x, y][:3]
                tr = int(0.393 * r + 0.769 * g + 0.189 * b)
                tg = int(0.349 * r + 0.686 * g + 0.168 * b)
                tb = int(0.272 * r + 0.534 * g + 0.131 * b)
                pixels[x, y] = (min(255, tr), min(255, tg), min(255, tb))
        
        self.applied_filters.append(('sepia', None))
    
    def rotate(self, degrees: float):
        self.current = self.current.rotate(degrees, expand=True)
        self.applied_filters.append(('rotate', degrees))
    
    def flip_horizontal(self):
        self.current = self.current.transpose(PILImage.FLIP_LEFT_RIGHT)
        self.applied_filters.append(('flip_horizontal', None))
    
    def flip_vertical(self):
        self.current = self.current.transpose(PILImage.FLIP_TOP_BOTTOM)
        self.applied_filters.append(('flip_vertical', None))
    
    def resize(self, size: Tuple[int, int], keep_aspect: bool = True):
        if keep_aspect:
            self.current.thumbnail(size, PILImage.Resampling.LANCZOS)
        else:
            self.current = self.current.resize(size, PILImage.Resampling.LANCZOS)
        self.applied_filters.append(('resize', size))
    
    def crop(self, box: Tuple[int, int, int, int]):
        self.current = self.current.crop(box)
        self.applied_filters.append(('crop', box))
    
    def to_bytes(self, format: str = None) -> bytes:
        format = format or self.format
        buffer = io.BytesIO()
        self.current.save(buffer, format=format)
        return buffer.getvalue()
    
    def save(self, filepath: str, format: str = None, quality: int = 95):
        format = format or self.format
        self.current.save(filepath, format=format, quality=quality)
    
    @property
    def size(self) -> Tuple[int, int]:
        return self.current.size
    
    @property
    def mode(self) -> str:
        return self.current.mode
