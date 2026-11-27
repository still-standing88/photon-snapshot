import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from PIL import Image
from core.batch_conversion import SourceEntry, BatchSettings, DestinationOptions, resolve_sources, run_batch, JobControl
from core.export import ExportOptions, export_document
from core.processing import apply_effect
from test_animation_io import sample_document

class BatchConversionTests(unittest.TestCase):
    def test_new_effects_run_in_order_and_preserve_alpha(self):
        effects = (
            ('saturation', {'factor': 1.3}),
            ('auto_contrast', {'cutoff': 1.5}),
            ('sharpen', {'strength': 120}),
            ('gaussian_blur', {'radius': 1.5}),
            ('speckle_reduction', {'neighborhood': 2}),
            ('levels', {'black_point': 20, 'white_point': 230, 'gamma': 1.4}),
            ('duotone', {'shadows': '#102030', 'highlights': '#eeddcc'}),
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / 'out'
            output.mkdir()
            source = root / 'source.png'
            pixels = Image.new('RGBA', (12, 12), (50, 80, 120, 255))
            pixels.paste((200, 100, 180, 100), (3, 3, 8, 8))
            pixels.save(source)
            expected = pixels
            for name, values in effects:
                expected = apply_effect(expected, name, values)
            self.assertNotEqual(expected.tobytes(), pixels.tobytes())

            settings = BatchSettings(ExportOptions('PNG'), effects, DestinationOptions(str(output)))
            result = run_batch([SourceEntry(str(source))], settings)
            self.assertEqual(result.counts['converted'], 1)
            with Image.open(output / 'source.png') as converted:
                self.assertEqual(converted.convert('RGBA').tobytes(), expected.tobytes())
                self.assertEqual(converted.getchannel('A').tobytes(), pixels.getchannel('A').tobytes())

    def test_separate_frame_collision_and_partial_failure_preserve_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'animation.gif'
            export_document(source, sample_document(), ExportOptions('GIF'))
            settings = BatchSettings(ExportOptions('PNG'), destination=DestinationOptions(delete_originals=True),
                                     animation_handling='separate')
            output_folder = root / 'animation_frames'
            output_folder.mkdir()
            collision = output_folder / 'animation_000002.png'
            collision.write_bytes(b'existing destination')
            result = run_batch([SourceEntry(str(source))], settings)
            self.assertEqual(result.counts['skipped'], 1)
            self.assertEqual(collision.read_bytes(), b'existing destination')
            self.assertFalse((output_folder / 'animation_000001.png').exists())
            collision.unlink()
            def write(path, *args, **kwargs):
                if Path(path).name == 'animation_000002.png':
                    raise PermissionError('Destination is locked')
                return export_document(path, *args, **kwargs)
            with patch('core.batch_conversion.export_document', side_effect=write):
                result = run_batch([SourceEntry(str(source))], settings)
            self.assertEqual(result.counts['failed'], 1)
            self.assertEqual(len(result.files[0].outputs), 1)
            self.assertTrue(source.exists())
            self.assertFalse(list(root.rglob('.photon-*.tmp')))

    def test_dedup_recursive_output_exclusion_and_processing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'photos'
            output = root / 'out'
            output.mkdir(parents=True)
            source = root / 'input.png'
            Image.new('RGBA', (16, 12), 'red').save(source)
            settings = BatchSettings(ExportOptions('WEBP', lossless=True), (('resize', {'width': 8, 'height': 6, 'mode': 'exact'}),), DestinationOptions(str(output)))
            sources = (SourceEntry(str(root), True), SourceEntry(str(source)))
            plan, errors = resolve_sources(sources, settings)
            self.assertEqual(len(plan), 1)
            result = run_batch(sources, settings)
            self.assertEqual(result.counts['converted'], 1)
            with Image.open(output / 'input.webp') as image:
                self.assertEqual(image.size, (8, 6))
            self.assertEqual(run_batch(sources, settings).counts['skipped'], 1)

    def test_animation_policy_source_protection_and_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / 'output'
            output.mkdir()
            source = root / 'animation.gif'
            export_document(source, sample_document(), ExportOptions('GIF'))
            preserve = BatchSettings(ExportOptions('PNG'), destination=DestinationOptions(str(output)))
            self.assertEqual(run_batch([SourceEntry(str(source))], preserve).counts['skipped'], 1)
            first = BatchSettings(ExportOptions('PNG'), destination=DestinationOptions(str(output)), animation_handling='first')
            self.assertEqual(run_batch([SourceEntry(str(source))], first).counts['converted'], 1)
            same = BatchSettings(ExportOptions('GIF'), destination=DestinationOptions(overwrite_existing=True))
            self.assertEqual(run_batch([SourceEntry(str(source))], same).counts['skipped'], 1)
            bad = root / 'bad.png'
            bad.write_bytes(b'corrupt')
            self.assertEqual(run_batch([SourceEntry(str(bad))], preserve).counts['failed'], 1)

    def test_cancel_keeps_prior_outputs_and_no_temporary_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / 'output'
            output.mkdir()
            sources = []
            for i in range(3):
                path = root / f'{i}.png'
                Image.new('RGB', (8, 8), 'red').save(path)
                sources.append(SourceEntry(str(path)))
            control = JobControl()
            def event(kind, *values):
                if kind == 'result':
                    control.cancel()
            result = run_batch(sources, BatchSettings(ExportOptions('JPEG'), destination=DestinationOptions(str(output))), control, event)
            self.assertEqual(result.counts, {'converted': 1, 'skipped': 0, 'failed': 0, 'cancelled': 2})
            self.assertEqual(len(list(output.iterdir())), 1)
