"""Pillow-only transformations shared by interactive and batch editing."""
from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFilter
from .effects_catalog import validate_effect
SEPIA = (.393, .769, .189, 0, .349, .686, .168, 0, .272, .534, .131, 0)

def resize(image, size, mode='exact', background=(0, 0, 0, 0)):
    if mode == 'exact':
        return image.resize(size, Image.Resampling.LANCZOS)
    if mode == 'fill':
        return ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    if mode == 'fit':
        result = image.copy()
        result.thumbnail(size, Image.Resampling.LANCZOS)
        return result
    result = ImageOps.contain(image, size, Image.Resampling.LANCZOS).convert('RGBA')
    canvas = Image.new('RGBA', size, background)
    canvas.alpha_composite(result, ((size[0] - result.width)//2, (size[1] - result.height)//2))
    return canvas

def _blur(rgba, radius, region):
    source = rgba if region is None else rgba.crop(region)
    # Prevent invisible RGB from bleeding into visible pixels during blur.
    blurred = source.convert('RGBa').filter(ImageFilter.GaussianBlur(radius)).convert('RGBA')
    blurred.putalpha(source.getchannel('A'))
    if region is None:
        return blurred
    rgba.paste(blurred, region)
    return rgba


def _adjust_levels(rgb, black_point, white_point, gamma):
    table = []
    for value in range(256):
        level = (value - black_point) / (white_point - black_point)
        level = max(0, min(1, level))
        table.append(round(255 * level ** (1 / gamma)))
    return rgb.point(table * 3)


def apply_effect(image, effect_id, values=None, *, region=None):
    p = validate_effect(effect_id, values or {})
    if region is not None:
        left, top, right, bottom = region
        if effect_id != 'gaussian_blur' or not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
            raise ValueError('Invalid blur region')
    if effect_id == 'resize':
        return resize(image, (int(p['width']), int(p['height'])), p['mode'])
    if effect_id == 'crop':
        x, y, w, h = (int(p[k]) for k in ('left', 'top', 'width', 'height'))
        if x + w > image.width or y + h > image.height:
            raise ValueError('Crop lies outside the canvas')
        return image.crop((x, y, x + w, y + h))
    if effect_id == 'rotate':
        return image.rotate(p['degrees'], expand=True, resample=Image.Resampling.BICUBIC)
    if effect_id.startswith('flip_'):
        return image.transpose(Image.Transpose.FLIP_LEFT_RIGHT if effect_id == 'flip_horizontal' else Image.Transpose.FLIP_TOP_BOTTOM)
    rgba = image.convert('RGBA')
    preserve_alpha = image.mode in ('RGBA', 'LA', 'P', 'PA') or 'transparency' in image.info
    if effect_id == 'gaussian_blur':
        result = _blur(rgba, p['radius'], region)
        return result if preserve_alpha else result.convert('RGB')
    alpha = rgba.getchannel('A')
    rgb = rgba.convert('RGB')
    if effect_id == 'brightness':
        rgb = ImageEnhance.Brightness(rgb).enhance(p['factor'])
    elif effect_id == 'contrast':
        rgb = ImageEnhance.Contrast(rgb).enhance(p['factor'])
    elif effect_id == 'grayscale':
        rgb = ImageOps.grayscale(rgb).convert('RGB')
    elif effect_id == 'invert':
        rgb = ImageOps.invert(rgb)
    elif effect_id == 'sepia':
        rgb = rgb.convert('RGB', SEPIA)
    elif effect_id == 'saturation':
        rgb = ImageEnhance.Color(rgb).enhance(p['factor'])
    elif effect_id == 'auto_contrast':
        # Fully transparent pixels must not influence the histogram.
        rgb = ImageOps.autocontrast(rgb, cutoff=p['cutoff'], mask=alpha)
    elif effect_id == 'sharpen':
        rgb = rgb.filter(ImageFilter.UnsharpMask(p['radius'], int(p['strength']), int(p['threshold'])))
    elif effect_id == 'speckle_reduction':
        rgb = rgb.filter(ImageFilter.MedianFilter(2 * int(p['neighborhood']) + 1))
    elif effect_id == 'levels':
        rgb = _adjust_levels(rgb, p['black_point'], p['white_point'], p['gamma'])
    elif effect_id == 'duotone':
        rgb = ImageOps.colorize(rgb.convert('L'), p['shadows'], p['highlights'])
    result = rgb.convert('RGBA')
    result.putalpha(alpha)
    return result if preserve_alpha else result.convert('RGB')

def draw_stroke(image, points, color, width):
    result = image.convert('RGBA')
    if len(points) >= 2:
        layer = Image.new('RGBA', result.size)
        draw = ImageDraw.Draw(layer)
        width = max(1, int(width))
        draw.line(points, fill=color, width=width, joint='curve')
        r = width/2
        for x, y in (points[0], points[-1]):
            draw.ellipse((x-r, y-r, x+r, y+r), fill=color)
        result = Image.alpha_composite(result, layer)
    return result
