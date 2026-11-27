"""Serializable image-space artwork. Rendering is supplied by the GUI."""
import math
import copy

def validate_artwork(item):
    if not isinstance(item, dict) or item.get('kind') not in ('text', 'rectangle', 'ellipse', 'line'):
        raise ValueError('Invalid artwork type')
    if any(not isinstance(item.get(k, 0), (int, float)) or not math.isfinite(item.get(k, 0))
           or abs(item.get(k, 0)) > 1000000 for k in ('x', 'y', 'width', 'height', 'opacity', 'font_size', 'stroke_width')):
        raise ValueError('Invalid artwork dimensions')
    if len(str(item.get('text', ''))) > 100000:
        raise ValueError('Artwork text is too long')
    transform = item.get('transform', (1, 0, 0, 1, 0, 0))
    if not isinstance(transform, (list, tuple)) or len(transform) != 6 or any(not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 1000000 for v in transform):
        raise ValueError('Invalid artwork transformation')
    if not 0 <= item.get('opacity', 1) <= 1:
        raise ValueError('Artwork opacity must be between zero and one')
    for key in ('color', 'fill'):
        colour = item.get(key)
        if colour is not None and (not isinstance(colour, (list, tuple)) or len(colour) != 4 or
                                  any(not isinstance(v, int) or not 0 <= v <= 255 for v in colour)):
            raise ValueError('Invalid artwork colour')


def transform_artwork(items, old_size, new_size, effect_id, values):
    # Canvas edits rasterize artwork first via the GUI adapter, avoiding
    # divergent font metrics and preserving arbitrary-angle transforms.
    if items:
        raise ValueError('Render artwork before transforming the canvas')
    return items


def transform_for_action(items, action, old_size, new_size):
    from .actions import CropAction, ResizeAction, RotateAction, FlipAction
    w, h = old_size
    nw, nh = new_size
    matrix = None
    if isinstance(action, CropAction):
        matrix = (1, 0, 0, 1, -action.box[0], -action.box[1])
    elif isinstance(action, ResizeAction):
        matrix = (nw/w, 0, 0, nh/h, 0, 0)
    elif isinstance(action, RotateAction):
        angle = math.radians(action.degrees)
        c, s = math.cos(angle), math.sin(angle)
        matrix = (c, -s, s, c, nw/2-c*w/2-s*h/2, nh/2+s*w/2-c*h/2)
    elif isinstance(action, FlipAction):
        matrix = (-1, 0, 0, 1, w, 0) if action.direction == 'horizontal' else (1, 0, 0, -1, 0, h)
    if matrix is None:
        return items
    result = copy.deepcopy(items)
    a, b, c, d, e, f = matrix
    for item in result:
        aa, bb, cc, dd, ee, ff = item.get('transform', (1, 0, 0, 1, 0, 0))
        item['transform'] = [a*aa+c*bb, b*aa+d*bb, a*cc+c*dd, b*cc+d*dd, a*ee+c*ff+e, b*ee+d*ff+f]
    return result
