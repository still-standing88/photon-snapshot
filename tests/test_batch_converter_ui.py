import test_app_regressions as regressions
from core.batch_conversion import SourceEntry
from app_db import db

class BatchConverterUITests(regressions.AppRegressionTests):
    def test_pause_resume_cancel_progress_reopen_and_ui_responsiveness(self):
        from pathlib import Path
        from PIL import Image
        from PySide6.QtCore import QTimer
        from PySide6.QtTest import QTest
        import time
        window = self.window()
        window.open_batch_converter()
        tool = window.batch_dialog
        source = Path(self.directory.name) / 'batch'
        source.mkdir()
        for index in range(80):
            Image.new('RGB', (32,32), 'red').save(source / f'{index}.png')
        tool.add_source(SourceEntry(str(source)))
        tool.encoding.format.setCurrentIndex(tool.encoding.format.findData('JPEG'))
        ticks = []
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(time.monotonic()))
        timer.start()
        tool.start()
        progress = tool.progress_dialog
        progress._pause()
        progress.hide()
        tool.reopen_progress()
        self.assertIs(tool.progress_dialog, progress)
        self.assertTrue(progress.isVisible())
        self.assertFalse(tool.job.control.running.is_set())
        deadline = time.monotonic() + 2
        while not ticks and time.monotonic() < deadline:
            QTest.qWait(20)
        self.assertTrue(ticks, "The GUI timer did not fire while the batch job was paused")
        self.assertTrue(tool.job.isRunning())
        progress._pause()
        QTest.qWait(80)
        progress._cancel()
        deadline = time.monotonic()+5
        while tool.job.isRunning() and time.monotonic() < deadline:
            QTest.qWait(20)
        timer.stop()
        self.app.processEvents()
        self.assertFalse(tool.job.isRunning())
        self.assertTrue(progress.finished_run)
        self.assertFalse(list(source.glob('.photon-*.tmp')))
    def test_tab_order_conditional_controls_and_preset_persistence(self):
        window = self.window()
        window.open_batch_converter()
        tool = window.batch_dialog
        self.assertEqual([tool.tabs.tabText(i) for i in range(4)], ['Source', 'Convert', 'Processing', 'Destination'])
        tool.encoding.format.setCurrentIndex(tool.encoding.format.findData('BMP'))
        self.assertFalse(tool.encoding.form.isRowVisible(tool.encoding.controls['quality']))
        tool.add_effect('resize', {'width': 80, 'height': 60, 'mode': 'exact'})
        tool.preset.setCurrentText('Small images')
        tool.save_preset()
        payload = db.get_preset('image_batch', 'Small images')
        self.assertNotIn('source', payload)
        self.assertNotIn('destination', payload)
        tool.effects.clear()
        tool.load_preset(0)
        self.assertEqual(tool.processing_values()[0][0], 'resize')
        tool.hide()
        window.open_batch_converter()
        self.assertIs(window.batch_dialog, tool)

    def test_invalid_preset_disables_begin(self):
        window = self.window()
        window.open_batch_converter()
        tool = window.batch_dialog
        db.save_preset('image_batch', 'Obsolete', {'version': 1, 'convert': {'format_id': 'PNG'},
                       'animation_handling': 'preserve', 'processing': [('unknown', {})]})
        tool.refresh_presets()
        tool.preset.setCurrentText('Obsolete')
        tool.load_preset(0)
        self.assertFalse(tool.begin.isEnabled())
        self.assertIn('Unknown effect', tool.validation.text())

for name in dir(regressions.AppRegressionTests):
    if name.startswith('test_'):
        setattr(BatchConverterUITests, name, None)
