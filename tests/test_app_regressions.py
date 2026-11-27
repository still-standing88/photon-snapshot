r"""Regression checks for startup, shortcut configuration, and tray lifecycle.

Run: venv\Scripts\python.exe -m unittest discover -s tests -v
All database writes use temporary files; Qt runs with its offscreen plugin.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QWidget

from app_config import key_config, prefs
from app_db import base_database, db
from core.overlays import GridOverlay
from gui.dialogs.hotkeys_dialog import HotkeysDialog
from gui.main_window import MainWindow
from taskbar_icon import TaskbarIcon
from utilities.i18n import install_translation


class AppRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        install_translation('en')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(base_database, 'get_database_path',
            return_value=str(Path(self.directory.name) / 'app.db'))
        self.path_patch.start()
        db.initialize()
        prefs.initialize()
        prefs.prefs['check_for_updates_on_startup'] = False
        prefs.prefs['minimize_to_tray_on_close'] = False
        key_config.load_keys()
        self.widgets = []

    def tearDown(self):
        for widget in reversed(self.widgets):
            widget.hide()
            widget.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        db.close()
        self.path_patch.stop()
        self.directory.cleanup()

    def window(self):
        window = MainWindow()
        self.widgets.append(window)
        window.show()
        window.activateWindow()
        self.app.processEvents()
        return window

    def dialog(self, window=None):
        dialog = HotkeysDialog(window)
        self.widgets.append(dialog)
        dialog.show()
        dialog.activateWindow()
        self.app.processEvents()
        return dialog

    def focus(self, widget):
        widget.window().activateWindow()
        widget.setFocus()
        self.app.processEvents()

    def row(self, dialog, section, action):
        for index in range(dialog.tree.topLevelItemCount()):
            category = dialog.tree.topLevelItem(index)
            for child in range(category.childCount()):
                item = category.child(child)
                if dialog._item_key(item) == (section, action):
                    category.setExpanded(True)
                    return item
        self.fail(f'Missing shortcut {section}/{action}')

    def run_search(self, explorer, query):
        ready = QSignalSpy(explorer._search_worker.results_ready)
        explorer.search_edit.setCurrentText(query)
        explorer._on_search_submitted()
        self.assertTrue(explorer._search_worker.wait(3000))
        self.app.processEvents()
        self.assertEqual(ready.count(), 1)

    def test_startup_registers_every_configured_action(self):
        window = self.window()
        tray = TaskbarIcon(window)
        expected = {(s, a) for s, actions in key_config.key_dict.items() for a in actions}
        self.assertEqual(set(key_config._bound_targets), expected)
        self.assertIs(tray.tray_menu.parentWidget(), window)
        self.assertEqual(tray.show_action.text(), 'Hide')

    def test_upgrade_preserves_custom_and_unbound_keys(self):
        db.clear_key_bindings()
        db.set_key_binding('Main Window', 'Open file', 'Ctrl+Shift+P')
        db.set_key_binding('Viewer', 'Toggle Grid Overlay', '')
        db.set_key_binding('Explorer', 'Refresh', 'invalid input')
        db.set_pref('disabled_hotkeys', ['Main Window::Open file'])
        key_config.load_keys()
        self.assertEqual(key_config.get_sequence('Main Window', 'Open file'), 'Ctrl+Shift+P')
        self.assertEqual(key_config.get_sequence('Viewer', 'Toggle Grid Overlay'), '')
        self.assertEqual(key_config.get_sequence('Explorer', 'Refresh'), 'F5')
        self.assertFalse(key_config.is_hotkey_enabled('Main Window', 'Open file'))
        self.assertEqual(db.get_all_key_bindings(), key_config.bindings)

    def test_live_shortcut_remap_and_disable_survive_reload(self):
        parent = QWidget()
        self.widgets.append(parent)
        shortcut = key_config.make_shortcut('Explorer', 'Refresh', parent, lambda: None)
        key_config.set_sequence('Explorer', 'Refresh', 'Ctrl+Shift+R')
        self.assertEqual(shortcut.key().toString(), 'Ctrl+Shift+R')
        key_config.set_hotkey_enabled('Explorer', 'Refresh', False)
        self.assertTrue(shortcut.key().isEmpty())
        key_config.load_keys()
        self.assertTrue(shortcut.key().isEmpty())
        key_config.set_hotkey_enabled('Explorer', 'Refresh', True)
        self.assertEqual(shortcut.key().toString(), 'Ctrl+Shift+R')
        key_config.keys_to_default()
        self.assertEqual(shortcut.key().toString(), 'F5')

    def test_deleted_targets_are_removed(self):
        parent = QWidget()
        key_config.make_shortcut('Explorer', 'Refresh', parent, lambda: None)
        parent.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertNotIn(('Explorer', 'Refresh'), key_config._bound_targets)
        key_config.keys_to_default()

    def test_portable_keys_and_invalid_input(self):
        for text in ('Ctrl+,', 'Ctrl++', 'Ctrl+Win+P', 'Page Up', 'Escape', ''):
            with self.subTest(text=text):
                self.assertIsNotNone(key_config.normalize_sequence(text))
        for text in ('Ctrl', 'Ctrl+', 'not a key', 'Ctrl+K, Ctrl+C'):
            with self.subTest(text=text):
                self.assertIsNone(key_config.normalize_sequence(text))
        with self.assertRaises(ValueError):
            key_config.set_sequence('Explorer', 'Refresh', 'not a key')

    def test_save_failure_rolls_back_database_and_live_config(self):
        before, disabled = key_config.snapshot_configuration()
        draft = {s: dict(actions) for s, actions in before.items()}
        draft['Explorer']['Refresh'] = 'Ctrl+Shift+R'
        with patch.object(db, '_set_pref_impl', side_effect=OSError('simulated disk failure')):
            with self.assertLogs('app_db.base_database', level='ERROR'):
                with self.assertRaises(OSError):
                    key_config.save_configuration(draft, disabled)
        self.assertEqual(db.get_all_key_bindings(), before)
        self.assertEqual(key_config.bindings, before)

    def test_conflicts_respect_pane_scopes_and_disabled_keys(self):
        draft, disabled = key_config.snapshot_configuration()
        draft['Explorer']['Refresh'] = 'G'
        self.assertEqual(key_config.find_conflicts(draft), [])
        draft['Main Window']['Open file'] = 'G'
        self.assertEqual(len(key_config.find_conflicts(draft)), 2)
        disabled = {('Main Window', 'Open file')}
        self.assertEqual(key_config.find_conflicts(draft, disabled), [])

    def test_enter_opens_real_accessible_editor(self):
        dialog = self.dialog()
        item = self.row(dialog, 'Explorer', 'Refresh')
        dialog.tree.setCurrentItem(item)
        self.focus(dialog.tree)
        QTest.keyClick(dialog.tree, Qt.Key.Key_Return)
        self.assertTrue(dialog.edit_field.hasFocus())
        self.assertIs(dialog.edit_field.parentWidget(), dialog.edit_panel)

    def test_apply_commits_field_before_focus_changes(self):
        dialog = self.dialog()
        item = self.row(dialog, 'Explorer', 'Refresh')
        dialog.focus_editor(item)
        dialog.edit_field.selectAll()
        QTest.keyClicks(dialog.edit_field, 'Ctrl+Shift+R')
        QTest.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)
        self.assertEqual(key_config.get_sequence('Explorer', 'Refresh'), 'Ctrl+Shift+R')
        dialog._draft['Explorer']['Refresh'] = 'F9'
        dialog.reject()
        self.assertEqual(key_config.get_sequence('Explorer', 'Refresh'), 'Ctrl+Shift+R')

    def test_capture_modifier_return_and_escape(self):
        dialog = self.dialog()
        item = self.row(dialog, 'Explorer', 'Refresh')
        dialog.focus_editor(item)
        dialog.capture_button.setChecked(True)
        QTest.keyClick(dialog.edit_field, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        self.assertEqual(dialog._draft['Explorer']['Refresh'], 'Meta+Ctrl+P')
        dialog.capture_button.setChecked(True)
        QTest.keyClick(dialog.edit_field, Qt.Key.Key_Return)
        self.assertEqual(dialog._draft['Explorer']['Refresh'], 'Return')
        self.assertTrue(dialog.isVisible())
        dialog.capture_button.setChecked(True)
        QTest.keyClick(dialog.edit_field, Qt.Key.Key_Escape)
        self.assertEqual(dialog.edit_field.text(), 'Return')
        self.assertFalse(dialog.capture_button.isChecked())

    def test_cancel_discards_reset_and_enabled_state(self):
        key_config.set_sequence('Explorer', 'Refresh', 'F9')
        dialog = self.dialog()
        item = self.row(dialog, 'Explorer', 'Refresh')
        dialog.toggle_item_enabled(item)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            dialog.reset_to_default()
        dialog.reject()
        self.assertEqual(key_config.get_sequence('Explorer', 'Refresh'), 'F9')
        self.assertTrue(key_config.is_hotkey_enabled('Explorer', 'Refresh'))

    def test_conflict_and_invalid_input_do_not_save(self):
        dialog = self.dialog()
        item = self.row(dialog, 'Explorer', 'Refresh')
        dialog.focus_editor(item)
        dialog.edit_field.setText('Ctrl+O')
        dialog.on_field_edited('Ctrl+O')
        with patch.object(QMessageBox, 'warning') as warning:
            self.assertFalse(dialog.apply_changes())
            warning.assert_called_once()
        self.assertEqual(key_config.get_sequence('Explorer', 'Refresh'), 'F5')
        dialog.edit_field.setText('invalid input')
        dialog.on_field_edited('invalid input')
        with patch.object(QMessageBox, 'warning'):
            self.assertFalse(dialog.apply_changes())
        self.assertEqual(key_config.get_sequence('Explorer', 'Refresh'), 'F5')

    def test_search_and_space_toggle(self):
        dialog = self.dialog()
        item = self.row(dialog, 'Explorer', 'Refresh')
        dialog.search_edit.setText('Refresh')
        self.assertFalse(item.isHidden())
        dialog.tree.setCurrentItem(item, 1)
        self.focus(dialog.tree)
        QTest.keyClick(dialog.tree, Qt.Key.Key_Space)
        self.assertIn(('Explorer', 'Refresh'), dialog._disabled)
        self.assertTrue(dialog.apply_changes())
        self.assertEqual(key_config.get_active_sequence('Explorer', 'Refresh'), '')
        self.assertEqual(key_config.get_sequence('Explorer', 'Refresh'), 'F5')

    def test_viewer_shortcuts_are_local_and_modes_stay_in_sync(self):
        window = self.window()
        window.show_explorer_action.setChecked(True)
        self.focus(window.explorer_widget.file_list)
        QTest.keyClick(window.explorer_widget.file_list, Qt.Key.Key_G)
        self.assertEqual(window.viewer.overlay_manager.get_overlays_by_type(GridOverlay), [])
        self.focus(window.viewer)
        QTest.keyClick(window.viewer, Qt.Key.Key_G)
        self.assertTrue(window.editor_panel.overlay_panel.grid_btn.isChecked())
        QTest.keyClick(window.viewer, Qt.Key.Key_C)
        self.assertTrue(window.viewer.crop_mode)
        QTest.keyClick(window.viewer, Qt.Key.Key_D)
        self.assertTrue(window.viewer.drawing_mode)
        self.assertFalse(window.viewer.crop_mode)
        self.assertFalse(window.editor_panel.crop_panel.crop_mode_checkbox.isChecked())
        key_config.set_sequence('Viewer', 'Cancel/Escape Mode', 'F8')
        QTest.keyClick(window.viewer, Qt.Key.Key_Escape)
        self.assertTrue(window.viewer.drawing_mode)
        QTest.keyClick(window.viewer, Qt.Key.Key_F8)
        self.assertFalse(window.viewer.drawing_mode)
        QTest.keyClick(window.viewer, Qt.Key.Key_C, Qt.KeyboardModifier.AltModifier)
        self.assertFalse(window.editor_panel.overlay_panel.grid_btn.isChecked())
        self.assertEqual(window.viewer.overlay_manager.get_overlays_by_type(GridOverlay), [])

    def test_explorer_remap_navigation_and_text_editing(self):
        window = self.window()
        window.show_explorer_action.setChecked(True)
        explorer = window.explorer_widget
        self.focus(explorer.file_list)
        child = Path(self.directory.name) / 'folder'
        child.mkdir()
        explorer.explorer.navigate_to(str(child))
        key_config.set_sequence('Explorer', 'Go Up', 'Alt+Up')
        QTest.keyClick(explorer.file_list, Qt.Key.Key_Backspace)
        self.assertEqual(explorer.explorer.current_path, str(child))
        QTest.keyClick(explorer.file_list, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(Path(explorer.explorer.current_path), child.parent)
        QTest.keyClick(explorer.file_list, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        self.assertTrue(explorer.search_bar.hasFocus())
        QTest.keyClicks(explorer.search_bar, 'test')
        QTest.keyClick(explorer.search_bar, Qt.Key.Key_Backspace)
        self.assertEqual(explorer.search_bar.text(), 'tes')

    def test_tray_visibility_restores_minimized_window(self):
        window = self.window()
        tray = TaskbarIcon(window)
        window.hide()
        self.assertEqual(tray.show_action.text(), 'Show')
        tray.show_window()
        self.assertEqual(tray.show_action.text(), 'Hide')
        window.showMinimized()
        self.app.processEvents()
        self.assertEqual(tray.show_action.text(), 'Show')
        tray.show_window()
        self.assertFalse(window.isMinimized())
        self.assertTrue(window.isVisible())

    def test_quit_bypasses_hide_preference_but_honors_cancel(self):
        window = self.window()
        prefs.prefs['minimize_to_tray_on_close'] = True
        with patch.object(window, '_confirm_close', return_value=False) as confirm:
            window.close_application()
            confirm.assert_called_once()
        self.assertTrue(window.isVisible())
        self.assertFalse(window._force_exit)
        with patch.object(window, '_confirm_close', return_value=True):
            window.close_application()
        self.assertFalse(window.isVisible())

    def test_no_tray_minimizes_instead_of_hiding(self):
        window = self.window()
        with patch.object(QSystemTrayIcon, 'isSystemTrayAvailable', return_value=False):
            window._minimize_to_tray()
        self.assertTrue(window.isVisible())
        self.assertTrue(window.isMinimized())

    def test_recent_menu_keeps_clear_action(self):
        window = self.window()
        window.update_recent_files_menu()
        window.update_recent_files_menu()
        clear_actions = [a for a in window.recent_files_menu.actions() if a.data() == 'clear']
        self.assertEqual(len(clear_actions), 1)
        self.assertEqual(clear_actions[0].text(), 'Clear Recent Files')

    def test_main_shortcuts_work_from_floating_explorer(self):
        window = self.window()
        window.show_explorer_action.setChecked(True)
        window.explorer_dock.setFloating(True)
        self.focus(window.explorer_widget.file_list)
        QTest.keyClick(window.explorer_widget.file_list, Qt.Key.Key_F6)
        self.app.processEvents()
        self.assertTrue(window.viewer.hasFocus())

    def test_open_selected_favorites_library_and_refresh(self):
        from PIL import Image
        window = self.window()
        window.show_explorer_action.setChecked(True)
        explorer = window.explorer_widget
        image_path = Path(self.directory.name) / 'sample.png'
        Image.new('RGB', (16, 16)).save(image_path)
        explorer.explorer.navigate_to(self.directory.name)
        image_item = next(explorer.file_list.item(i) for i in range(explorer.file_list.count())
                          if explorer.file_list.item(i).text() == 'sample.png')
        explorer.file_list.setCurrentItem(image_item)
        self.focus(explorer.file_list)
        opened = QSignalSpy(explorer.open_image)
        key_config.set_sequence('Explorer', 'Open Selected', 'F7')
        QTest.keyClick(explorer.file_list, Qt.Key.Key_Return)
        self.assertEqual(opened.count(), 0)
        QTest.keyClick(explorer.file_list, Qt.Key.Key_F7)
        self.assertEqual(opened.count(), 1)
        self.assertIsNotNone(window.editor.current_image)
        QTest.keyClick(explorer.file_list, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
        self.assertIn(str(image_path), db.get_favorites())
        QTest.keyClick(explorer.file_list, Qt.Key.Key_L,
                       Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        self.assertIn(self.directory.name, db.get_library_folders())
        explorer.focus_search()
        self.run_search(explorer, 'sample')
        Image.new('RGB', (16, 16)).save(Path(self.directory.name) / 'sample2.png')
        self.assertEqual(explorer.file_list.count(), 1)
        key_config.set_sequence('Explorer', 'Refresh', 'F9')
        ready = QSignalSpy(explorer._search_worker.results_ready)
        QTest.keyClick(explorer.search_bar, Qt.Key.Key_F9)
        self.assertTrue(explorer._search_worker.wait(3000))
        self.app.processEvents()
        self.assertEqual(ready.count(), 1)
        self.assertEqual(explorer.file_list.count(), 2)

    def test_editable_path_and_parent_navigation(self):
        window = self.window()
        window.show_explorer_action.setChecked(True)
        explorer = window.explorer_widget
        folder = Path(self.directory.name) / 'album with spaces'
        folder.mkdir()
        self.focus(explorer.file_list)
        QTest.keyClick(explorer.file_list, Qt.Key.Key_D, Qt.KeyboardModifier.AltModifier)
        self.assertTrue(explorer.path_edit.hasFocus())
        explorer.path_edit.setText(f'"{folder}"')
        QTest.keyClick(explorer.path_edit, Qt.Key.Key_Return)
        self.assertEqual(explorer.explorer.current_path, str(folder))
        self.assertEqual(explorer.path_edit.text(), str(folder))
        self.assertEqual(prefs.prefs['last_explorer_path'], str(folder))
        with patch.object(QMessageBox, 'warning') as warning:
            explorer.path_edit.setText(str(folder / 'missing'))
            explorer.set_path()
            warning.assert_called_once()
        self.assertEqual(explorer.path_edit.text(), str(folder))
        QTest.mouseClick(explorer.parent_btn, Qt.MouseButton.LeftButton)
        self.assertEqual(Path(explorer.explorer.current_path), folder.parent)
        self.assertEqual(explorer.file_list.currentItem().text(), folder.name)

    def test_recursive_search_history_escape_and_stale_results(self):
        from PIL import Image
        window = self.window()
        window.show_explorer_action.setChecked(True)
        explorer = window.explorer_widget
        root = Path(self.directory.name) / 'photos'
        nested = root / 'nested'
        nested.mkdir(parents=True)
        for filename in (root / 'scene.png', nested / 'scene.png'):
            Image.new('RGB', (16, 16)).save(filename)
        (nested / 'scene.txt').write_text('not an image')
        explorer.explorer.navigate_to(str(root))
        self.run_search(explorer, 'scene')
        self.assertEqual(explorer.file_list.count(), 2)
        labels = [explorer.file_list.item(i).text() for i in range(2)]
        self.assertIn('scene.png', labels)
        self.assertIn(os.path.join('nested', 'scene.png'), labels)
        self.assertEqual(prefs.prefs['search_history'][0], 'scene')
        self.run_search(explorer, 'scene')
        self.assertEqual(prefs.prefs['search_history'], ['scene'])
        self.focus(explorer.search_edit)
        QTest.keyClick(explorer.search_bar, Qt.Key.Key_Escape)
        self.assertEqual(explorer.search_edit.currentText(), '')
        self.assertFalse(explorer._search_active)
        self.assertTrue(explorer.file_list.hasFocus())
        explorer.explorer.navigate_to(str(nested))
        explorer._on_search_results(str(root), 'scene', [('stale', False, True, str(root / 'scene.png'))])
        self.assertEqual(explorer.file_list.count(), 2)
        self.assertNotEqual(explorer.file_list.item(0).text(), 'stale')

    def test_selection_previews_without_loading_editor(self):
        from PIL import Image
        window = self.window()
        window.show_explorer_action.setChecked(True)
        explorer = window.explorer_widget
        root = Path(self.directory.name) / 'preview'
        root.mkdir()
        Image.new('RGB', (32, 16)).save(root / 'photo.png')
        (root / 'notes.txt').write_text('notes')
        explorer.explorer.navigate_to(str(root))
        image_item = explorer.file_list.findItems('photo.png', Qt.MatchFlag.MatchExactly)[0]
        explorer.file_list.setCurrentItem(image_item)
        self.assertFalse(explorer.image_preview_label.isHidden())
        self.assertIsNone(window.editor.current_image)
        explorer.file_list.open_selected()
        self.assertIsNotNone(window.editor.current_image)
        notes = explorer.file_list.findItems('notes.txt', Qt.MatchFlag.MatchExactly)[0]
        explorer.file_list.setCurrentItem(notes)
        self.assertTrue(explorer.image_preview_label.isHidden())

    def test_view_modes_filters_and_sort_persist(self):
        from PIL import Image
        from gui.explorer import ExplorerWidget
        window = self.window()
        explorer = window.explorer_widget
        root = Path(self.directory.name) / 'view-modes'
        root.mkdir()
        Image.new('RGB', (16, 16)).save(root / 'a.png')
        Image.new('RGB', (16, 16)).save(root / 'z.jpg')
        (root / 'notes.txt').write_text('notes')
        (root / 'folder').mkdir()
        explorer.explorer.navigate_to(str(root))
        explorer.view_icon_action.trigger()
        self.assertTrue(explorer.view_icon_action.isChecked())
        self.assertFalse(explorer.view_list_action.isChecked())
        explorer._set_filter('images')
        self.assertEqual(explorer.file_list.count(), 3)
        explorer._set_sort('name_desc')
        self.assertEqual(explorer.file_list.item(1).text(), 'z.jpg')
        explorer._set_filter('custom', 'png')
        self.assertEqual(explorer.file_list.count(), 2)
        recreated = ExplorerWidget()
        self.widgets.append(recreated)
        self.assertTrue(recreated.view_icon_action.isChecked())
        self.assertEqual(recreated.explorer.filter_extension, 'png')
        self.assertEqual(recreated.explorer.sort_mode, 'name_desc')
        self.assertEqual(recreated.file_list.count(), 2)

    def test_radio_indicators_follow_overlay_changes(self):
        from core.overlays import RulerOverlay
        window = self.window()
        panel = window.editor_panel.overlay_panel
        window.toggle_grid_action.trigger()
        window.toggle_ruler_action.trigger()
        self.assertTrue(window.viewer.grid_overlay_visible())
        self.assertTrue(window.viewer.ruler_overlay_visible())
        self.assertTrue(panel.grid_btn.isChecked())
        self.assertTrue(panel.ruler_btn.isChecked())
        grid = window.viewer.overlay_manager.get_overlays_by_type(GridOverlay)[0]
        grid.set_visible(False)
        self.assertFalse(window.toggle_grid_action.isChecked())
        self.assertFalse(panel.grid_btn.isChecked())
        grid.visible = True
        self.assertTrue(window.toggle_grid_action.isChecked())
        window.viewer.show_overlays = False
        self.assertFalse(window.toggle_grid_action.isChecked())
        self.assertFalse(window.toggle_ruler_action.isChecked())
        window.viewer.show_overlays = True
        self.assertTrue(window.toggle_grid_action.isChecked())
        self.assertTrue(window.toggle_ruler_action.isChecked())
        window.toggle_grid_action.trigger()
        self.assertFalse(window.viewer.grid_overlay_visible())
        window.viewer.set_pixel_info_mode(True)
        self.assertTrue(window.toggle_pixel_info_action.isChecked())
        window.viewer.clear_overlays()
        self.assertFalse(window.toggle_grid_action.isChecked())
        self.assertFalse(window.toggle_ruler_action.isChecked())
        self.assertFalse(window.toggle_pixel_info_action.isChecked())
        panel.ruler_btn.setChecked(True)
        self.assertTrue(window.toggle_ruler_action.isChecked())
        ruler = window.viewer.overlay_manager.get_overlays_by_type(RulerOverlay)[0]
        window.viewer.overlay_manager.remove_overlay(ruler)
        self.assertFalse(window.toggle_ruler_action.isChecked())

    def test_library_uses_full_paths_for_duplicate_folder_names(self):
        window = self.window()
        window.show_explorer_action.setChecked(True)
        explorer = window.explorer_widget
        first = Path(self.directory.name) / 'first' / 'Album'
        second = Path(self.directory.name) / 'second' / 'Album'
        first.mkdir(parents=True)
        second.mkdir(parents=True)
        explorer.explorer.add_library_folder(str(first))
        explorer.explorer.add_library_folder(str(second))
        tree = explorer.library_tree
        root = tree.topLevelItem(0)
        second_item = next(root.child(i) for i in range(root.childCount())
                           if root.child(i).data(0, Qt.ItemDataRole.UserRole) == str(second))
        tree._on_activated(second_item, 0)
        self.assertEqual(explorer.explorer.current_path, str(second))
        self.app.processEvents()
        tree.setCurrentItem(second_item)
        tree.remove_selected()
        self.assertIn(str(first), db.get_library_folders())
        self.assertNotIn(str(second), db.get_library_folders())

    def test_reset_single_hotkey_preserves_other_customizations(self):
        key_config.set_sequence('Explorer', 'Refresh', 'F9')
        key_config.set_sequence('Explorer', 'Search files', 'F3')
        key_config.set_hotkey_enabled('Explorer', 'Refresh', False)
        key_config.reset_hotkey('Explorer', 'Refresh')
        self.assertEqual(key_config.get_active_sequence('Explorer', 'Refresh'), 'F5')
        self.assertEqual(key_config.get_sequence('Explorer', 'Search files'), 'F3')

    def test_arabic_layout_keeps_shortcut_entry_left_to_right(self):
        try:
            install_translation('ar-SA')
            self.assertEqual(self.app.layoutDirection(), Qt.LayoutDirection.RightToLeft)
            dialog = self.dialog()
            self.assertEqual(dialog.tree.layoutDirection(), Qt.LayoutDirection.RightToLeft)
            self.assertEqual(dialog.edit_field.layoutDirection(), Qt.LayoutDirection.LeftToRight)
            install_translation('fr')
            self.assertEqual(self.app.layoutDirection(), Qt.LayoutDirection.LeftToRight)
        finally:
            install_translation('en')


if __name__ == '__main__':
    unittest.main()
