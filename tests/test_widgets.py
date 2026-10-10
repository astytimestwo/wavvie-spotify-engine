"""Small widgets: the wave line, the account avatar and the activity log."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import logging
import unittest

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from ui.widgets.activity_log import ActivityLog, ActivityLogDialog
from ui.widgets.avatar import Avatar
from ui.widgets.wave_line import WaveLine


class WidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_wave_animates_only_while_shown_active_and_motion_is_allowed(self):
        wave = WaveLine()
        self.addCleanup(wave.deleteLater)
        wave.show()
        self.assertFalse(wave.timer.isActive())
        wave.set_active(True)
        self.assertTrue(wave.timer.isActive())
        wave.set_reduced_motion(True)
        self.assertFalse(wave.timer.isActive())
        wave.set_reduced_motion(False)
        wave.hide()
        self.assertFalse(wave.timer.isActive())
        wave.show()
        self.assertTrue(wave.timer.isActive())
        wave.set_active(False)
        self.assertFalse(wave.timer.isActive())

    def test_wave_progress_stays_between_empty_and_full(self):
        wave = WaveLine()
        wave.set_progress(1.7)
        self.assertEqual(wave.progress, 1.0)
        wave.set_progress(-1)
        self.assertEqual(wave.progress, 0.0)

    def test_avatar_shows_the_account_initial_and_names_the_account(self):
        avatar = Avatar()
        avatar.set_user('augustya')
        self.assertEqual(avatar.initial, 'A')
        self.assertEqual(avatar.accessibleName(), 'Signed in as augustya')
        avatar.set_user('')
        self.assertEqual(avatar.accessibleName(), 'Not signed in')

    def test_activity_log_keeps_the_newest_lines_and_copies_them(self):
        log = ActivityLog(limit=3)
        self.addCleanup(log.detach)
        for number in range(5):
            logging.getLogger('wavvie.test').warning('message %s', number)
        self.assertEqual([line.split(' - ')[-1] for line in log.lines], ['message 2', 'message 3', 'message 4'])
        dialog = ActivityLogDialog(log)
        self.addCleanup(dialog.deleteLater)
        self.assertIn('message 4', dialog.view.toPlainText())
        dialog.btn_copy.click()
        self.assertIn('message 4', QGuiApplication.clipboard().text())
        self.assertEqual(dialog.btn_copy.text(), 'Copied')

    def test_detached_activity_log_stops_listening(self):
        log = ActivityLog()
        log.detach()
        logging.getLogger('wavvie.test').warning('after detach')
        self.assertEqual(log.lines, [])


if __name__ == '__main__':
    unittest.main()
