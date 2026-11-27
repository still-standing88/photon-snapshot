"""Reproducible resource and throughput checks for release QA."""
import sys
import time
import json
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from PIL import Image, ImageDraw
from core.animation_io import decode_document
from core.batch_conversion import SourceEntry, BatchSettings, DestinationOptions, run_batch
from core.export import ExportOptions

def main():
    results = {}
    with tempfile.TemporaryDirectory(prefix='photon-performance-') as temporary:
        folder = Path(temporary)
        for width, height in ((512, 512), (1920, 1080)):
            images = []
            for index in range(100):
                image = Image.new('P', (width, height), index)
                image.putpalette([value for n in range(256) for value in (n, (n*7)%256, (n*13)%256)])
                images.append(image)
            path = folder / f'{width}.gif'
            images[0].save(path, save_all=True, append_images=images[1:], duration=100, loop=0, optimize=False)
            del images
            start = time.perf_counter()
            document = decode_document(path)
            seconds = time.perf_counter()-start
            results[f'100_frames_{width}x{height}'] = {'import_seconds': round(seconds, 3),
                'decoded_bytes': width*height*100*4, 'cache_bytes': document.store.memory_bytes,
                'spill_disk_bytes': document.store.disk_bytes, 'frame_count': len(document.frames)}
            start = time.perf_counter()
            for frame in document.frames:
                frame.image.current.resize((320, 180))
            results[f'100_frames_{width}x{height}']['frame_read_seconds'] = round(time.perf_counter()-start, 3)
            del document
        input_folder = folder / 'inputs'
        output_folder = folder / 'outputs'
        input_folder.mkdir()
        output_folder.mkdir()
        for index in range(1000):
            Image.new('RGB', (32, 32), (index%256, 80, 120)).save(input_folder / f'{index:04d}.png')
        start = time.perf_counter()
        batch = run_batch([SourceEntry(str(input_folder), True)], BatchSettings(ExportOptions('JPEG'), destination=DestinationOptions(str(output_folder))))
        results['1000_small_images'] = {'seconds': round(time.perf_counter()-start, 3), 'counts': batch.counts}
        try:
            decode_document(folder / '1920.gif', import_limit=1920*1080*99*4)
        except ValueError as error:
            results['resource_ceiling'] = str(error)
    output = ROOT / 'qa-artifacts' / 'performance.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()
