"""Small widgets: the wave line, the account avatar and the activity log."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import logging
import unittest

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QRegion
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from ui.widgets.activity_log import ActivityLog, ActivityLogDialog
from ui.widgets.avatar import Avatar
from ui.widgets.focus_rings import FocusRings
from ui.widgets.wave_line import WaveLine
from ui.widgets.wordmark import Wordmark


def render(widget, scale):
    image = QImage(widget.size() * scale, QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(scale)
    image.fill(Qt.transparent)
    widget.render(image, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)  # no window background
    return image


def soft_pixels(image):
    """Pixels part-way between ink and background: few on a sharp edge, many on a stretched bitmap."""
    return sum(1 for y in range(image.height()) for x in range(image.width())
               if 40 < image.pixelColor(x, y).alpha() < 215)


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

    def test_focus_rings_follow_the_keyboard_and_not_the_mouse(self):
        window = QWidget()
        self.addCleanup(window.deleteLater)
        layout = QVBoxLayout(window)
        first, second = QPushButton('First'), QPushButton('Second')
        layout.addWidget(first)
        layout.addWidget(second)
        FocusRings(window)
        window.show()
        window.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(window, 1000))

        def ringed():
            return [button.text() for button in (first, second) if button.property('focusRing')]

        QTest.mouseClick(first, Qt.LeftButton)
        self.assertEqual(ringed(), [])
        first.hide()  # a clicked button that goes away hands focus on, still without a ring
        self.assertIs(QApplication.focusWidget(), second)
        self.assertEqual(ringed(), [])
        first.show()
        QTest.keyClick(second, Qt.Key_Tab)
        self.assertEqual(ringed(), ['First'])
        QTest.mouseClick(second, Qt.LeftButton)
        self.assertEqual(ringed(), [])

    def test_the_wordmark_stays_sharp_on_high_density_displays(self):
        mark = Wordmark(28)
        self.addCleanup(mark.deleteLater)
        self.assertEqual(mark.height(), 28)
        self.assertAlmostEqual(mark.width() / mark.height(), 1394 / 510, delta=0.05)  # the artwork's proportions
        sharp = render(mark, 2)
        stretched = render(mark, 1).scaled(sharp.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.assertGreater(soft_pixels(sharp), 0)
        self.assertLess(soft_pixels(sharp), 0.75 * soft_pixels(stretched))
        self.assertEqual(mark.accessibleName(), 'wavvie')

    def test_the_account_picture_keeps_its_detail_on_high_density_displays(self):
        picture = QImage(64, 64, QImage.Format_RGB32)
        for y in range(64):
            for x in range(64):
                picture.setPixelColor(x, y, QColor('white' if (x // 2) % 2 else 'black'))
        avatar = Avatar(30)
        self.addCleanup(avatar.deleteLater)
        avatar.set_user('augustya', picture)
        sharp = render(avatar, 2)
        stretched = render(avatar, 1).scaled(sharp.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        expected = picture.scaled(sharp.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        def error(image):  # mean lightness difference from the picture itself, well inside the circle
            centre = [(x, y) for y in range(15, 45) for x in range(15, 45)]
            return sum(abs(image.pixelColor(x, y).lightness() - expected.pixelColor(x, y).lightness())
                       for x, y in centre) / len(centre)

        self.assertLess(error(sharp), 0.5 * error(stretched))

    def test_detached_activity_log_stops_listening(self):
        log = ActivityLog()
        log.detach()
        logging.getLogger('wavvie.test').warning('after detach')
        self.assertEqual(log.lines, [])


if __name__ == '__main__':
    unittest.main()
