import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from PIL import Image
from core.export import ExportOptions, export_images, CancelledError
from core.processing import apply_effect, resize
from core.formats import format_for_path

class ImageExportTests(unittest.TestCase):
    def test_cancel_during_frame_preparation_stops_before_encoding(self):
        from core.export import encode_images, prepare_image
        cancelled = [False]
        calls = []
        def prepare(*args):
            calls.append(args)
            cancelled[0] = True
            return prepare_image(*args)
        with patch('core.export.prepare_image', side_effect=prepare):
            with self.assertRaises(CancelledError):
                encode_images([Image.new('RGBA', (8, 8)) for _ in range(3)], [100]*3, 1,
                              ExportOptions('GIF'), cancel=lambda: cancelled[0])
        self.assertEqual(len(calls), 1)

    def test_metadata_orientation_and_valid_profile(self):
        from PIL import ImageCms
        from core.animation_io import decode_document
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        exif = Image.Exif()
        exif[274] = 6
        exif[256] = 99
        exif[257] = 99
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.jpg'
            Image.new('RGB', (8, 4), 'red').save(source, exif=exif, icc_profile=profile)
            document = decode_document(source)
            self.assertEqual(document.canvas_size, (4, 8))
            from core.export import export_document
            target = Path(folder) / 'preserved.png'
            export_document(target, document, ExportOptions('PNG', preserve_metadata=True))
            with Image.open(target) as image:
                self.assertIn('icc_profile', image.info)
                self.assertNotIn(274, image.getexif())
                self.assertNotIn(256, image.getexif())
            target = Path(folder) / 'removed.png'
            export_document(target, document, ExportOptions('PNG'))
            with Image.open(target) as image:
                self.assertNotIn('icc_profile', image.info)
                self.assertFalse(image.getexif())
    def test_alpha_modes_composite_and_format_roundtrips(self):
        with tempfile.TemporaryDirectory() as folder:
            for mode in ('RGBA', 'LA', 'P', 'CMYK', 'L'):
                image = Image.new(mode, (8, 8))
                if mode == 'P':
                    image.info['transparency'] = 0
                path = Path(folder) / (mode + '.jpg')
                export_images(path, [image], [100], 1, ExportOptions('JPEG'))
                with Image.open(path) as output:
                    self.assertEqual(output.format, 'JPEG')
                    if mode in ('RGBA', 'LA', 'P'):
                        self.assertGreater(output.getpixel((0, 0))[0], 245)
            for fmt, ext in (('PNG', '.png'), ('BMP', '.bmp'), ('TIFF', '.tif'), ('GIF', '.gif'), ('WEBP', '.webp')):
                path = Path(folder) / ('output' + ext)
                export_images(path, [Image.new('RGBA', (8, 8), 'red')], [100], 1, ExportOptions(fmt))
                self.assertEqual(format_for_path(path).id, fmt)

    def test_atomic_failure_cancel_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'output.png'
            path.write_bytes(b'old')
            args = (path, [Image.new('RGB', (8, 8))], [100], 1, ExportOptions())
            with self.assertRaises(FileExistsError):
                export_images(*args, overwrite=False)
            with patch('core.export.validate_image', side_effect=OSError('validation failed')):
                with self.assertRaises(OSError):
                    export_images(*args)
            with self.assertRaises(CancelledError):
                export_images(*args, cancel=lambda: True)
            self.assertEqual(path.read_bytes(), b'old')
            self.assertEqual(len(list(Path(folder).iterdir())), 1)

    def test_resize_and_alpha_preserving_filters(self):
        image = Image.new('RGBA', (8, 4), (100, 50, 20, 70))
        self.assertEqual(resize(image, (32, 32), 'exact').size, (32, 32))
        self.assertEqual(resize(image, (32, 32), 'fit').size, (8, 4))
        self.assertEqual(resize(image, (32, 32), 'contain').size, (32, 32))
        for effect in ('grayscale', 'invert', 'sepia', 'brightness', 'contrast'):
            self.assertEqual(apply_effect(image, effect).getchannel('A').getextrema(), (70, 70))
