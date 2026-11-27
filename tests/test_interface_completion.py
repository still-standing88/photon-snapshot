import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch
import test_app_regressions as regressions
from test_animation_io import sample_document
from PySide6.QtCore import QTimer, Qt, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton, QMessageBox
from PIL import Image
from core.batch_conversion import SourceEntry
from gui.dialogs.export_dialog import ExportDialog

class InterfaceCompletionTests(regressions.AppRegressionTests):
    def drain_jobs(self, window):
        for job in list(window.jobs.jobs):
            job.control.cancel()
            job.wait(3000)
        self.app.processEvents()

    def test_menu_order_and_selection_sensitive_context_actions(self):
        window = self.window()
        self.assertEqual(window.accessibleName(), 'Photon Snapshot')
        self.assertEqual([a.text().replace('&', '') for a in window.menuBar().actions()], ['File', 'Edit', 'View', 'Tools', 'Options'])
        self.assertEqual([a.text() for a in window.new_menu.actions()], ['New Image...', 'New Animation...'])
        window.open_batch_converter()
        tool = window.batch_dialog
        self.assertEqual([b.text() for b in tool.findChildren(QPushButton) if b.isVisible()], ['Begin'])
        menu = tool.create_source_menu()
        self.assertEqual([a.isEnabled() for a in menu.actions()], [True, True, False, False])
        menu.deleteLater()
        tool.add_source(SourceEntry(self.directory.name))
        tool.sources.setCurrentItem(tool.sources.topLevelItem(0))
        menu = tool.create_source_menu()
        self.assertTrue(menu.actions()[2].isEnabled())
        menu.deleteLater()
        menu = tool.create_effect_menu()
        self.assertFalse(next(a for a in menu.actions() if a.text() == 'Edit').isEnabled())
        menu.deleteLater()
        tool.add_effect('invert', {})
        tool.effects.setCurrentRow(0)
        menu = tool.create_effect_menu()
        enabled = {a.text(): a.isEnabled() for a in menu.actions()}
        self.assertTrue(enabled['Edit'])
        self.assertFalse(enabled['Move Up'])
        self.assertFalse(enabled['Move Down'])
        menu.deleteLater()
        window.editor.load_document(sample_document())
        actions = window.animation_panel.frame_actions
        self.assertFalse(actions['earlier'].isEnabled())
        self.assertTrue(actions['delete'].isEnabled())
        self.drain_jobs(window)

    def test_worker_keeps_event_loop_responsive_and_cancellation_finishes(self):
        window = self.window()
        ticks = []
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(time.monotonic()))
        timer.start()
        value = window._run_worker('Responsiveness', lambda c, p: (time.sleep(.15), 42)[1])
        timer.stop()
        self.assertEqual(value, 42)
        self.assertGreaterEqual(len(ticks), 5)
        def cancel():
            for job in window.jobs.jobs:
                job.control.cancel()
        QTimer.singleShot(30, cancel)
        def cancellable(control, progress):
            for _ in range(100):
                control.checkpoint()
                time.sleep(.01)
        self.assertIsNone(window._run_worker('Cancellation', cancellable))
        self.assertFalse(window.jobs.active)

    def test_keyboard_coordinate_blur_and_crop_use_animation_scope(self):
        window = self.window()
        self.assertFalse(window.coordinate_crop_action.isEnabled())
        document = sample_document()
        for frame in document.frames:
            pixels = frame.image.current
            pixels.paste((255, 255, 255, 255), (4, 2, 8, 6))
            frame.image.current = pixels
        window.editor.load_document(document)
        blur = next(action for action in window.editor_panel.effect_menu.actions()
                    if action.text() == 'Gaussian Blur')

        def open_and_edit(action, edit):
            self.assertTrue(action.isEnabled())
            errors = []

            def edit_modal():
                dialog = self.app.activeModalWidget()
                try:
                    self.assertIsNotNone(dialog)
                    edit(dialog)
                except Exception as exc:
                    errors.append(exc)
                finally:
                    if dialog and dialog.isVisible():
                        dialog.reject()

            QTimer.singleShot(0, edit_modal)
            action.trigger()
            if errors:
                raise errors[0]

        def set_region(dialog):
            self.assertFalse(window.playback.playing)
            self.focus(dialog.region_mode)
            QTest.keyClick(dialog.region_mode, Qt.Key.Key_Down)
            self.assertEqual(dialog.region_mode.accessibleName(), 'Blur area')
            fields = dialog.region_fields
            self.assertTrue(fields.isVisible())
            self.focus(fields.left)
            fields.left.selectAll()
            QTest.keyClicks(fields.left, '2')
            QTest.keyClick(fields.left, Qt.Key.Key_Tab)
            self.assertEqual(self.app.focusWidget().accessibleName(), 'Top')
            fields.top.setValue(1)
            fields.width.setValue(8)
            fields.height.setValue(8)
            QTest.keyClick(fields.height, Qt.Key.Key_Return)

        window.playback.start()
        open_and_edit(blur, set_region)
        frames = window.editor.document.frames
        original = document.frames[0].image.current
        blurred = frames[0].image.current
        self.assertNotEqual(blurred.getpixel((4, 2)), original.getpixel((4, 2)))
        self.assertEqual(blurred.crop((10, 0, 16, 12)).tobytes(),
                         original.crop((10, 0, 16, 12)).tobytes())
        self.assertEqual(frames[1].image.current.tobytes(), document.frames[1].image.current.tobytes())
        self.assertTrue(window.editor.undo())
        self.assertEqual(window.editor.current_image.current.tobytes(), original.tobytes())

        def set_crop(dialog):
            fields = dialog.fields
            fields.left.setValue(14)
            self.assertEqual(fields.width.maximum(), 2)
            fields.top.setValue(3)
            fields.height.setValue(4)
            self.focus(fields.height)
            QTest.keyClick(fields.height, Qt.Key.Key_Return)

        open_and_edit(window.coordinate_crop_action, set_crop)
        self.assertEqual([frame.image.size for frame in window.editor.document.frames], [(2, 4)] * 3)
        self.assertTrue(window.editor.undo())
        self.assertEqual(window.editor.current_image.size, (16, 12))

    def test_still_save_as_retains_format_and_project_reopen(self):
        window = self.window()
        source = Path(self.directory.name) / 'source.jpg'
        Image.new('RGB', (20, 10), 'red').save(source)
        window.load_image_file(str(source))
        destination = Path(self.directory.name) / 'saved.webp'
        with (patch('gui.animation_workspace.QFileDialog.getSaveFileName', return_value=(str(destination), 'WebP (*.webp)')),
              patch.object(ExportDialog, 'exec', return_value=1)):
            window.save_file_as()
        self.assertEqual(window.export_options.format_id, 'WEBP')
        window.editor.apply_invert()
        window.save_file()
        self.assertFalse(window.editor.is_dirty)
        with Image.open(destination) as result:
            self.assertEqual(result.format, 'WEBP')
        window.editor.load_document(sample_document())
        project = Path(self.directory.name) / 'animation.photonanim'
        with patch('gui.animation_workspace.QFileDialog.getSaveFileName', return_value=(str(project), 'Photon Animation Project (*.photonanim)')):
            window.save_file_as()
        window.load_image_file(str(project))
        self.assertEqual([f.duration_ms for f in window.editor.document.frames], [40, 130, 70])
        self.drain_jobs(window)

    def test_translated_windows_fit_small_screen_and_frame_order_stays_chronological(self):
        from utilities.i18n import install_translation
        from utilities.theme_manager import apply_theme
        from PySide6.QtGui import QFont, QFontDatabase
        import os
        original_font = self.app.font()
        original_style = self.app.styleSheet()
        if os.name == 'nt':
            QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'segoeui.ttf'))
            self.app.setFont(QFont('Segoe UI', 9))
        try:
            for theme in ('light', 'dark'):
                apply_theme(theme, self.app)
                for language in ('en', 'fr', 'es', 'ar'):
                    install_translation(language)
                    window = self.window()
                    window.editor.load_document(sample_document())
                    window.resize(900, 700)
                    self.app.processEvents()
                    self.assertLessEqual(window.minimumSizeHint().width(), 900)
                    self.assertLessEqual(window.minimumSizeHint().height(), 700)
                    self.assertEqual(window.animation_panel.strip.layoutDirection(), Qt.LayoutDirection.LeftToRight)
                    window.open_batch_converter()
                    for index in range(4):
                        window.batch_dialog.tabs.setCurrentIndex(index)
                        self.app.processEvents()
                        self.assertLessEqual(window.batch_dialog.minimumSizeHint().width(), 900)
                        self.assertLessEqual(window.batch_dialog.minimumSizeHint().height(), 700)
                    self.drain_jobs(window)
        finally:
            install_translation('en')
            self.app.setFont(original_font)
            self.app.setStyleSheet(original_style)

for name in dir(regressions.AppRegressionTests):
    if name.startswith('test_'):
        setattr(InterfaceCompletionTests, name, None)
