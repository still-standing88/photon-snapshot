"""Stable effect IDs and validated parameter specifications."""
from dataclasses import dataclass
import math
import re

@dataclass(frozen=True)
class Effect:
    id: str
    label: str
    category: str
    parameters: dict

@dataclass(frozen=True)
class ColorParameter:
    default: str

EFFECTS = {e.id: e for e in (
    Effect('resize', 'Resize', 'Transform', {'width': (1, 32768, 512), 'height': (1, 32768, 512), 'mode': ('exact', 'contain', 'fit')}),
    Effect('crop', 'Crop', 'Transform', {'left': (0, 32767, 0), 'top': (0, 32767, 0), 'width': (1, 32768, 256), 'height': (1, 32768, 256)}),
    Effect('rotate', 'Rotate', 'Transform', {'degrees': (-360, 360, 90)}),
    Effect('flip_horizontal', 'Flip horizontal', 'Transform', {}),
    Effect('flip_vertical', 'Flip vertical', 'Transform', {}),
    Effect('brightness', 'Brightness', 'Adjustments', {'factor': (0.0, 4.0, 1.0)}),
    Effect('contrast', 'Contrast', 'Adjustments', {'factor': (0.0, 4.0, 1.0)}),
    Effect('grayscale', 'Grayscale', 'Colour', {}),
    Effect('invert', 'Invert', 'Colour', {}),
    Effect('sepia', 'Sepia', 'Colour', {}),
    Effect('saturation', 'Saturation', 'Adjustments', {'factor': (0.0, 4.0, 1.25)}),
    Effect('auto_contrast', 'Auto Contrast', 'Adjustments', {'cutoff': (0.0, 10.0, 0.0)}),
    Effect('sharpen', 'Sharpen', 'Filters', {'radius': (0.1, 20.0, 2.0), 'strength': (1, 500, 150), 'threshold': (0, 255, 3)}),
    Effect('gaussian_blur', 'Gaussian Blur', 'Filters', {'radius': (0.1, 100.0, 2.0)}),
    Effect('speckle_reduction', 'Speckle Reduction', 'Filters', {'neighborhood': (1, 3, 1)}),
    Effect('levels', 'Gamma and Levels', 'Adjustments', {'black_point': (0, 254, 0), 'white_point': (1, 255, 255), 'gamma': (0.1, 5.0, 1.0)}),
    Effect('duotone', 'Duotone', 'Colour', {'shadows': ColorParameter('#172554'), 'highlights': ColorParameter('#fef3c7')}),
)}

def defaults(effect_id):
    values = {}
    for key, spec in EFFECTS[effect_id].parameters.items():
        if isinstance(spec, ColorParameter):
            values[key] = spec.default
        else:
            values[key] = spec[0] if isinstance(spec[0], str) else spec[2]
    return values

def validate_effect(effect_id, values):
    if effect_id not in EFFECTS:
        raise ValueError(f'Unknown effect: {effect_id}')
    specs = EFFECTS[effect_id].parameters
    if set(values) - set(specs):
        raise ValueError(f'Unknown parameters for {effect_id}')
    result = defaults(effect_id)
    result.update(values)
    for key, spec in specs.items():
        value = result[key]
        if isinstance(spec, ColorParameter):
            if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
                raise ValueError(f'{key} must be a #RRGGBB colour')
        elif isinstance(spec[0], str):
            if value not in spec:
                raise ValueError(f'Invalid {key}: {value}')
        elif not isinstance(value, (float, int)) or isinstance(value, bool) or not math.isfinite(value) or not spec[0] <= value <= spec[1]:
            raise ValueError(f'{key} must be between {spec[0]} and {spec[1]}')
        elif isinstance(spec[2], int) and int(value) != value:
            raise ValueError(f'{key} must be an integer')
    if effect_id == 'levels' and result['black_point'] >= result['white_point']:
        raise ValueError('Black point must be below white point')
    return result
