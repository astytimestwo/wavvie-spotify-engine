"""Settings: saved immediately, advanced options tucked away."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

import ui.pages.settings_page as settings_module
from ui.pages.settings_page import Preferences, SettingsPage, read_preferences


class SettingsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = str(Path(directory.name) / 'settings.ini')

        class IsolatedSettings(QSettings):
            def __init__(self, *args, **kwargs):
                super().__init__(path, QSettings.IniFormat)

        self.settings = IsolatedSettings()
        patcher = patch.object(settings_module, 'QSettings', IsolatedSettings)
        patcher.start()
        self.addCleanup(patcher.stop)

    def page(self):
        page = SettingsPage()
        self.addCleanup(page.deleteLater)
        return page

    def test_loading_shows_saved_values_without_rewriting_them(self):
        for key, value in (('default_cutoff_days', 90), ('default_workers', 3), ('reduced_motion', True),
                           ('artist_range_enabled', True), ('artist_range_start', 2), ('artist_range_end', 4)):
            self.settings.setValue(key, value)
        page = self.page()
        self.assertEqual(page.combo_look_back.currentText(), '90 days')
        self.assertEqual((page.spin_workers.value(), page.spin_from.value(), page.spin_to.value()), (3, 2, 4))
        self.assertTrue(page.chk_motion.isChecked())
        self.assertTrue(page.spin_from.isEnabled())
        self.assertEqual(read_preferences(), Preferences(look_back_days=90, artist_range=(2, 4), workers=3,
                                                         export_json=False, reduced_motion=True))

    def test_changes_save_immediately_and_keep_the_range_valid(self):
        page = self.page()
        changes = []
        page.settings_changed.connect(lambda: changes.append(True))
        page.combo_look_back.setCurrentIndex(0)
        page.chk_range.setChecked(True)
        page.spin_from.setValue(5)
        page.spin_to.setValue(3)
        page.chk_json.setChecked(True)
        preferences = read_preferences()
        self.assertEqual((preferences.look_back_days, preferences.artist_range, preferences.export_json),
                         (7, (5, 5), True))
        self.assertEqual(page.spin_to.value(), 5)
        self.assertTrue(changes)

    def test_advanced_settings_start_hidden_and_toggle(self):
        page = self.page()
        self.assertTrue(page.advanced.isHidden())
        page.btn_advanced.click()
        self.assertFalse(page.advanced.isHidden())
        self.assertEqual(page.btn_advanced.text(), 'Hide advanced settings')
        page.btn_advanced.click()
        self.assertTrue(page.advanced.isHidden())

    def test_range_follows_the_checkbox_and_the_artist_count(self):
        page = self.page()
        page.set_artist_count(12)
        self.assertFalse(page.spin_from.isEnabled())
        page.chk_range.setChecked(True)
        self.assertTrue(page.spin_from.isEnabled())
        self.assertEqual(page.spin_to.maximum(), 12)

    def test_account_and_busy_state(self):
        page = self.page()
        page.set_account('Listener')
        self.assertEqual(page.lbl_account.text(), 'Connected as Listener')
        page.set_busy(True)
        self.assertFalse(page.btn_disconnect.isEnabled())
        self.assertFalse(page.btn_refresh.isEnabled())


if __name__ == '__main__':
    unittest.main()
