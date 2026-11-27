import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core.editor import Editor
from test_animation_io import sample_document

class DocumentHistoryTests(unittest.TestCase):
    def setUp(self):
        self.editor = Editor()
        self.editor.load_document(sample_document())

    def test_navigation_reorder_and_targeted_undo(self):
        editor = self.editor
        middle = editor.document.frames[1].id
        editor.set_active_frame(middle)
        editor.apply_invert()
        changed = editor.current_image.current.getpixel((0, 0))
        editor.move_frames(-1)
        editor.set_active_frame(editor.document.frames[-1].id)
        editor.undo()
        editor.undo()
        self.assertEqual(editor.document.frame(middle).image.current.getpixel((0, 0))[:3], (0, 0, 255))
        editor.redo()
        self.assertEqual(editor.document.frame(middle).image.current.getpixel((0, 0)), changed)

    def test_save_checkpoint_branching_and_scope(self):
        editor = self.editor
        editor.apply_invert()
        editor.mark_saved()
        self.assertFalse(editor.is_dirty)
        editor.undo()
        self.assertTrue(editor.is_dirty)
        editor.redo()
        self.assertFalse(editor.is_dirty)
        editor.state.set_scope('all')
        editor.apply_grayscale()
        self.assertEqual(len(editor.state.history), 2)
        editor.undo()
        self.assertFalse(editor.is_dirty)
        editor.apply_sepia()
        self.assertFalse(editor.can_redo())
        self.assertTrue(editor.is_dirty)

    def test_duplicate_independence_and_canvas_transform(self):
        editor = self.editor
        editor.duplicate_frames()
        duplicate = editor.document.frames[1].id
        editor.set_active_frame(duplicate)
        editor.draw_stroke([(0, 0), (8, 8)], (0, 0, 0, 255), 3)
        self.assertNotEqual(editor.document.frames[0].image.current.tobytes(), editor.current_image.current.tobytes())
        editor.rotate(90)
        self.assertEqual({f.image.size for f in editor.document.frames}, {(12, 16)})
        editor.undo()
        self.assertEqual({f.image.size for f in editor.document.frames}, {(16, 12)})
