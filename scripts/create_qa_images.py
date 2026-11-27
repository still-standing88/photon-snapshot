"""Fetch a public demo photograph and create deterministic animation inputs."""
from pathlib import Path
import urllib.request
from PIL import Image, ImageDraw

folder = Path(__file__).resolve().parents[1] / 'qa-artifacts'
folder.mkdir(exist_ok=True)
urllib.request.urlretrieve('https://picsum.photos/seed/photon-snapshot/640/480', folder / 'demo-photo.jpg')
frames = []
for index in range(3):
    image = Image.new('RGBA', (320, 240), (30, 40, 65, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((20+index*80, 80, 80+index*80, 140), fill=(255, 100+index*50, 30, 255))
    frames.append(image)
    image.save(folder / f'demo-frame-{index+1}.png')
frames[0].save(folder / 'demo-animation.gif', save_all=True, append_images=frames[1:], duration=[100, 250, 400], loop=2, disposal=2)
print('Demo images ready')
