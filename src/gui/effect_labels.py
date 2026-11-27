"""Literal gettext labels for the stable headless effect catalog."""
def effect_label(effect_id):
    return {'resize': _('Resize'), 'crop': _('Crop'), 'rotate': _('Rotate'),
            'flip_horizontal': _('Flip horizontal'), 'flip_vertical': _('Flip vertical'),
            'brightness': _('Brightness'), 'contrast': _('Contrast'), 'grayscale': _('Grayscale'),
            'invert': _('Invert'), 'sepia': _('Sepia'),
            'saturation': _('Saturation'), 'auto_contrast': _('Auto Contrast'),
            'sharpen': _('Sharpen'), 'gaussian_blur': _('Gaussian Blur'),
            'speckle_reduction': _('Speckle Reduction'), 'levels': _('Gamma and Levels'),
            'duotone': _('Duotone')}[effect_id]

def category_label(category):
    return {'Transform': _('Transform'), 'Adjustments': _('Adjustments'),
            'Colour': _('Colour'), 'Filters': _('Filters')}[category]

def parameter_label(key):
    return {'width': _('Width (pixels)'), 'height': _('Height (pixels)'), 'mode': _('Mode'),
            'left': _('Left'), 'top': _('Top'), 'degrees': _('Degrees'),
            'factor': _('Factor'), 'cutoff': _('Cutoff (%)'), 'radius': _('Radius (pixels)'),
            'strength': _('Strength (%)'), 'threshold': _('Threshold'),
            'neighborhood': _('Neighborhood radius (pixels)'), 'black_point': _('Black point'),
            'white_point': _('White point'), 'gamma': _('Gamma'),
            'shadows': _('Shadow colour'), 'highlights': _('Highlight colour')}[key]

def resize_mode_label(mode):
    return {'exact': _('Exact dimensions'), 'contain': _('Contain with padding'), 'fit': _('Bounded fit without enlargement')}[mode]
