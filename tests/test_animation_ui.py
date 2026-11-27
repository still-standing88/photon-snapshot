import test_app_regressions as regressions
from test_animation_io import sample_document
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from app_config import key_config
from gui.artwork_renderer import render_frame

class AnimationUITests(regressions.AppRegressionTests):
    def tearDown(self):
        # Drain workers before the inherited teardown destroys their owners,
        # including when an assertion or dialog setup fails.
        for window in self.widgets:
            if hasattr(window, 'jobs'):
                window.jobs.cancel_all()
                for job in list(window.jobs.jobs):
                    job.wait(3000)
        self.app.processEvents()
        super().tearDown()

    def test_new_imported_animation_scoped_drawing_and_project_export(self):
        from pathlib import Path
        from unittest.mock import patch
        from PIL import Image
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QCheckBox, QDialog
        from gui.dialogs.new_animation_dialog import NewAnimationDialog
        from core.animation_io import save_project, load_project
        from core.export import ExportOptions, export_document
        window = self.window()
        with patch.object(NewAnimationDialog, 'exec', return_value=1), \
             patch.object(NewAnimationDialog, 'values', return_value=(16, 12, QColor('white'))):
            window.new_animation()
        self.assertTrue(window.editor.document.animation)
        self.assertEqual(window.editor.document.frames[0].image.current.getpixel((0, 0))[3], 0)
        root = Path(self.directory.name)
        paths = []
        for name, colour in (('frame10.png', 'blue'), ('frame2.png', 'red')):
            path = root / name
            Image.new('RGBA', (16, 8), colour).save(path)
            paths.append(str(path))
        original_exec = QDialog.exec
        def accept_import(dialog):
            if dialog.windowTitle() == 'Import Frame Sizing':
                dialog.findChildren(QCheckBox)[0].setChecked(True)
                return 1
            return original_exec(dialog)
        with patch('gui.animation_workspace.QFileDialog.getOpenFileNames', return_value=(paths, 'PNG')), \
             patch('gui.animation_workspace.QDialog.exec', new=accept_import):
            window.import_frames()
        document = window.editor.document
        self.assertEqual([f.image.current.getpixel((8, 6))[:3] for f in document.frames[1:]],
                         [(255, 0, 0), (0, 0, 255)])
        self.assertEqual(document.frames[1].image.current.getpixel((0, 0))[3], 0)
        ids = {f.id for f in document.frames[1:]}
        window.editor.set_active_frame(document.frames[1].id, ids)
        window.editor.state.set_scope('selected')
        window.editor.draw_stroke([(1, 3), (8, 3)], (255, 255, 0, 255), 2)
        window.editor.add_artwork({'kind': 'text', 'text': 'X', 'x': 8, 'y': 8, 'font_size': 8})
        document = window.editor.document
        self.assertFalse(document.frames[0].artwork)
        self.assertEqual([f.image.current.getpixel((3, 3))[:3] for f in document.frames[1:]], [(255, 255, 0)]*2)
        project = root / 'created.photonanim'
        save_project(project, document)
        reopened = load_project(project)
        self.assertEqual(reopened.frames[1].artwork, document.frames[1].artwork)
        window.viewer.zoom_in()
        target = root / 'frame.png'
        export_document(target, reopened, ExportOptions('PNG'), render_frame, frame_ids={reopened.frames[1].id})
        with Image.open(target) as output:
            self.assertEqual(output.size, (16, 12))
            self.assertEqual(output.getpixel((3, 3))[:3], (255, 255, 0))
        window.jobs.cancel_all()
        for job in list(window.jobs.jobs):
            job.wait(3000)
        self.app.processEvents()

    def test_range_selection_and_drag_reorder(self):
        window = self.window()
        window.editor.load_document(sample_document())
        panel = window.animation_panel
        self.focus(panel.strip)
        QTest.keyClick(panel.strip, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
        self.app.processEvents()
        self.assertEqual(len(window.editor.state.selected_frame_ids), 2)
        original = [f.id for f in window.editor.document.frames]
        mime = panel.model.mimeData([panel.model.index(0)])
        from PySide6.QtCore import QModelIndex
        self.assertTrue(panel.model.dropMimeData(mime, Qt.DropAction.MoveAction, 3, 0, QModelIndex()))
        self.assertEqual([f.id for f in window.editor.document.frames], original[1:]+original[:1])
        window.editor.undo()
        self.assertEqual([f.id for f in window.editor.document.frames], original)
        window.jobs.cancel_all()
        for job in list(window.jobs.jobs):
            job.wait(3000)
        self.app.processEvents()
    # Inherit the isolated Qt/database setup, not the existing test methods.
    def test_frame_navigation_remapping_and_numeric_typing(self):
        window = self.window()
        window.editor.load_document(sample_document())
        panel = window.animation_panel
        self.focus(panel.strip)
        first = window.editor.state.active_frame_id
        QTest.keyClick(panel.strip, Qt.Key.Key_Right)
        self.assertNotEqual(window.editor.state.active_frame_id, first)
        self.assertFalse(window.editor.is_dirty)
        key_config.set_sequence('Animation', 'Next Frame', 'Down')
        self.focus(panel.duration)
        index = window.editor.state.active_frame_id
        QTest.keyClick(panel.duration, Qt.Key.Key_Down)
        self.assertEqual(window.editor.state.active_frame_id, index)
        self.focus(panel.strip)
        QTest.keyClick(panel.strip, Qt.Key.Key_Down)
        self.assertEqual(window.editor.state.active_frame_id, window.editor.document.frames[-1].id)
        window.jobs.cancel_all()
        for job in list(window.jobs.jobs):
            job.wait(3000)
        self.app.processEvents()

    def test_artwork_rendering_independent_of_zoom(self):
        window = self.window()
        window.editor.load_document(sample_document())
        window.editor.add_artwork({'kind': 'rectangle', 'x': 2, 'y': 2, 'width': 6, 'height': 6,
                                   'color': [255, 255, 255, 255], 'fill': [255, 255, 255, 255]})
        before = render_frame(window.editor.document.frames[0]).tobytes()
        window.viewer.zoom_in()
        window.viewer.set_grid_overlay_visible(True)
        self.assertEqual(render_frame(window.editor.document.frames[0]).tobytes(), before)
        window.jobs.cancel_all()
        for job in list(window.jobs.jobs):
            job.wait(3000)
        self.app.processEvents()

# unittest includes inherited tests: remove them from this subclass by shadowing.
for name in dir(regressions.AppRegressionTests):
    if name.startswith('test_'):
        setattr(AnimationUITests, name, None)
