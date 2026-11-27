import io
import struct
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from test_animation_io import sample_document
from core.animation_io import decode_document
from core.export import ExportOptions, export_document
from core.image import PhotonImage
from core.document import Frame, Document

def pixel_block(index, width=1):
    image = Image.new('P', (width, 1), index)
    image.putpalette([255, 255, 255, 255, 0, 0, 0, 0, 255] + [0]*759)
    buffer = io.BytesIO()
    image.save(buffer, format='GIF', optimize=False)
    data = buffer.getvalue()
    offset = data.index(b',', 13+768)
    return data[offset+10:-1]

def disposal_fixture():
    # Four hand-specified displayed canvases. Individual 1-pixel records
    # explicitly test offsets, background disposal and previous disposal.
    data = b'GIF89a' + struct.pack('<HHBBB', 3, 1, 0xF7, 0, 0)
    data += bytes([255, 255, 255, 255, 0, 0, 0, 0, 255] + [0]*759)
    for index, x, width, disposal in ((0, 0, 3, 1), (1, 1, 1, 2), (2, 2, 1, 3), (1, 0, 1, 1)):
        data += b'!\xf9\x04' + bytes([disposal << 2]) + struct.pack('<H', 5) + b'\x00\x00'
        data += b',' + struct.pack('<HHHHB', x, 0, width, 1, 0) + pixel_block(index, width)
    return data + b';'

class DisposalTests(unittest.TestCase):
    def test_hand_specified_disposal_and_frame_offsets(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'disposal.gif'
            path.write_bytes(disposal_fixture())
            result = decode_document(path)
            white, red, blue = (255,255,255), (255,0,0), (0,0,255)
            expected = [[white]*3, [white,red,white], [white,white,blue], [red,white,white]]
            for frame, canvas in zip(result.frames, expected):
                self.assertEqual([frame.image.current.getpixel((x,0))[:3] for x in range(3)], canvas)

    def test_transparency_finite_once_infinite_and_duplicate_merging(self):
        with tempfile.TemporaryDirectory() as folder:
            for fmt in ('GIF', 'WEBP'):
                for plays in (0, 1, 3):
                    source = sample_document()
                    source.total_plays = plays
                    for frame in source.frames:
                        pixels = frame.image.current
                        pixels.putpixel((0,0), (0,0,0,0))
                        frame.image.current = pixels
                    path = Path(folder) / ('test.' + fmt.lower())
                    export_document(path, source, ExportOptions(fmt, lossless=True))
                    result = decode_document(path)
                    self.assertEqual(result.total_plays, plays)
                    self.assertTrue(all(f.image.current.getpixel((0,0))[3] == 0 for f in result.frames))
                source.frames[1].image = source.frames[0].image.copy_current()
                export_document(path, source, ExportOptions(fmt, lossless=True))
                self.assertEqual(sum(f.duration_ms for f in decode_document(path).frames), 240)
