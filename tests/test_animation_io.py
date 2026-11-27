import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from PIL import Image
from core.document import Document, Frame
from core.image import PhotonImage
from core.animation_io import decode_document, save_project, load_project
from core.export import ExportOptions, export_document
from core.frame_store import FrameStore

def sample_document():
    store = FrameStore()
    return Document([Frame(PhotonImage(Image.new('RGBA', (16, 12), colour), store), duration)
                     for colour, duration in [('red', 40), ('blue', 130), ('green', 70)]],
                    total_plays=3, animation=True, store=store)

class AnimationIOTests(unittest.TestCase):
    def test_embedded_source_profile_applies_to_every_animation_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profile.webp'
            colours = [(20, 0, 0), (40, 0, 0), (60, 0, 0)]
            images = [Image.new('RGB', (4, 4), colour) for colour in colours]
            images[0].save(path, save_all=True, append_images=images[1:], duration=100,
                           lossless=True, icc_profile=b'source profile')
            def convert(image, profile):
                pixels = image.convert('RGBA')
                # Model a source profile with different channel interpretation.
                if profile == b'source profile':
                    pixels = pixels.point(lambda value: min(255, value + 10))
                return pixels, b'normalized profile'
            with patch('core.animation_io.normalize_colour', side_effect=convert):
                document = decode_document(path)
            self.assertEqual([frame.image.current.getpixel((0, 0))[0] for frame in document.frames], [30, 50, 70])
            self.assertEqual(document.metadata['icc_profile'], b'normalized profile')

    def test_variable_timing_loops_and_pixels(self):
        with tempfile.TemporaryDirectory() as folder:
            for fmt, ext in (('GIF', '.gif'), ('WEBP', '.webp')):
                source = sample_document()
                path = Path(folder) / ('animation' + ext)
                export_document(path, source, ExportOptions(fmt, lossless=True))
                result = decode_document(path)
                self.assertEqual([f.duration_ms for f in result.frames], [40, 130, 70])
                self.assertEqual(result.total_plays, 3)
                self.assertEqual([f.image.current.getpixel((0, 0))[:3] for f in result.frames],
                                 [f.image.current.getpixel((0, 0))[:3] for f in source.frames])

    def test_project_roundtrip_and_unsafe_archive_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source = sample_document()
            source.frames[1].artwork = [{'kind': 'text', 'text': 'Photon', 'x': 1, 'y': 1}]
            path = Path(folder) / 'editable.photonanim'
            save_project(path, source)
            result = load_project(path)
            self.assertEqual(result.frames[1].artwork, source.frames[1].artwork)
            self.assertEqual([f.id for f in result.frames], [f.id for f in source.frames])
            with zipfile.ZipFile(path, 'a') as archive:
                archive.writestr('../escape.png', b'bad')
            with self.assertRaises(ValueError):
                load_project(path)

    def test_spill_and_resource_limit(self):
        store = FrameStore(64)
        image = PhotonImage(Image.new('RGBA', (16, 16), 'red'), store)
        self.assertEqual(store.memory_bytes, 0)
        self.assertGreater(store.disk_bytes, 0)
        self.assertEqual(image.current.getpixel((0, 0)), (255, 0, 0, 255))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'animation.gif'
            export_document(path, sample_document(), ExportOptions('GIF'))
            with self.assertRaises(ValueError):
                decode_document(path, import_limit=20)
