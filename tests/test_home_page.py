"""The home screen's states, with real widgets."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from datetime import date, timedelta

from PySide6.QtCore import QDate, QPoint, Qt
from PySide6.QtGui import QColor, QTextFormat
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QLabel

from core.history import CheckRecord, NextWindow, short_date
from core.models import Track
from ui.pages.home_page import HomePage
from ui.theme import Theme

TODAY = date.today()


def days_ago(count):
    return TODAY - timedelta(days=count)


def song(number, featured=False, art=None):
    artists = ['Kite', 'Nova'] if featured else ['Nova']
    return Track(f't{number}', f'Song {number}', 'Album', 'a', 'single', days_ago(2).isoformat(), artists[0],
                 'nova', featured, 'featured' if featured else 'main', artists, f'song {number}|nova', art)


def record(start, end, songs=3, url='https://open.spotify.com/playlist/p1', complete=True):
    return CheckRecord(start.isoformat(), end.isoformat(), 'x', songs=songs, playlist_name='wavvie',
                       playlist_url=url, complete=complete)


class HomePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.page = HomePage()
        self.addCleanup(self.page.deleteLater)
        self.events = []
        for name in ('check_requested', 'stop_requested', 'done_requested', 'retry_save_requested',
                     'refresh_artists_requested', 'open_url_requested', 'show_file_requested'):
            getattr(self.page, name).connect(lambda *args, name=name: self.events.append((name,) + args))

    def test_first_check_offers_the_look_back_window(self):
        self.page.show_ready(NextWindow(days_ago(30), 'first'), 325, 30, [])
        self.assertEqual(self.page.headline.text(), "Let's find your new music")
        self.assertIn('325 artists', self.page.body.text())
        self.assertEqual(self.page.btn_primary.text(), 'Check the last 30 days')
        self.assertTrue(self.page.history_box.isHidden())
        self.page.btn_primary.click()
        self.assertEqual(self.events, [('check_requested', days_ago(30))])

    def test_ready_states_describe_the_last_check(self):
        self.page.show_ready(NextWindow(days_ago(7), 'ready'), 5, 30, [record(days_ago(30), days_ago(7))])
        self.assertEqual(self.page.headline.text(), f'New music since {short_date(days_ago(7))}')
        self.assertIn('saved 3 songs', self.page.body.text())
        self.assertEqual(self.page.btn_primary.text(), f'Check {short_date(days_ago(7))} – today')
        self.assertFalse(self.page.history_box.isHidden())
        self.page.show_ready(NextWindow(TODAY, 'up_to_date'), 5, 30, [record(days_ago(7), TODAY, songs=0, url=None)])
        self.assertEqual((self.page.headline.text(), self.page.btn_primary.text()), ("You're up to date", 'Check again'))
        self.assertIn('found nothing new', self.page.body.text())
        self.page.show_ready(NextWindow(days_ago(7), 'finish'), 5, 30,
                             [record(days_ago(7), days_ago(1), complete=False)])
        self.assertEqual(self.page.headline.text(), "Let's finish your last check")

    def test_changed_dates_relabel_the_check_and_can_be_reset(self):
        self.page.show_ready(NextWindow(days_ago(30), 'first'), 5, 30, [])
        self.page.btn_quiet.click()
        self.assertFalse(self.page.dates_row.isHidden())
        self.assertTrue(self.page.btn_quiet.isHidden())
        chosen = days_ago(5)
        self.page.date_start.setDate(QDate(chosen.year, chosen.month, chosen.day))
        self.assertEqual(self.page.btn_primary.text(), f'Check {short_date(chosen)} – today')
        self.page.btn_primary.click()
        self.assertEqual(self.events[-1], ('check_requested', chosen))
        self.page.btn_reset_dates.click()
        self.assertEqual(self.page.btn_primary.text(), 'Check the last 30 days')
        self.assertTrue(self.page.dates_row.isHidden())
        self.assertFalse(self.page.btn_quiet.isHidden())

    def test_the_date_picker_greys_out_the_days_it_will_not_take(self):
        self.page.show_ready(NextWindow(days_ago(7), 'ready'), 5, 30, [record(days_ago(30), days_ago(7))])
        calendar = self.page.date_start.calendarWidget()
        today = QDate(TODAY.year, TODAY.month, TODAY.day)
        self.assertEqual(calendar.dateTextFormat(today.addDays(1)).foreground().color(), QColor(Theme.DIM))
        self.assertFalse(calendar.dateTextFormat(today).hasProperty(QTextFormat.ForegroundBrush))
        for day in (Qt.Saturday, Qt.Sunday):  # Qt's default red weekends are off-palette
            self.assertFalse(calendar.weekdayTextFormat(day).hasProperty(QTextFormat.ForegroundBrush))

    def test_checking_shows_progress_and_stops(self):
        self.page.show_checking(4, days_ago(7))
        self.page.update_progress(2, 4, 3)
        self.assertEqual(self.page.progress.text(), '2 of 4 artists · 3 new songs so far')
        self.assertEqual(self.page.wave.progress, 0.5)
        self.page.show_rate_limited(30)
        self.assertIn('slow down', self.page.note.text())
        self.page.btn_quiet.click()
        self.assertEqual(self.events, [('stop_requested',)])
        self.page.show_stopping()
        self.assertEqual(self.page.btn_quiet.text(), 'Stopping…')
        self.assertFalse(self.page.btn_quiet.isEnabled())
        self.assertTrue(self.page.btn_primary.isHidden())

    def test_done_lists_the_saved_songs_and_opens_them(self):
        self.page.show_done('wavvie · New releases 10 Oct – 17 Oct', 'https://open.spotify.com/playlist/p',
                            [song(1), song(2, featured=True)])
        self.assertEqual(self.page.headline.text(), '2 new songs saved')
        self.assertIn('wavvie · New releases 10 Oct – 17 Oct', self.page.body.text())
        self.assertEqual(len(self.page.song_rows), 2)
        self.assertTrue(self.page.btn_extra.isHidden())
        tags = [found.text() for found in self.page.song_rows[1].findChildren(QLabel) if found.property('role') == 'tag']
        self.assertEqual(tags, ['feature'])
        self.page.btn_primary.click()
        QTest.mouseClick(self.page.song_rows[0], Qt.LeftButton)
        self.page.btn_quiet.click()
        self.assertEqual(self.events, [('open_url_requested', 'https://open.spotify.com/playlist/p'),
                                       ('open_url_requested', 'https://open.spotify.com/track/t1'),
                                       ('done_requested',)])

    def rules(self, box):
        return [found for found in box.findChildren(QFrame) if found.property('role') == 'rule']

    def test_saved_songs_are_separated_by_hairlines(self):
        self.page.show_done('wavvie', 'u', [song(1), song(2), song(3)])
        self.assertEqual(len(self.rules(self.page.songs_box)), 2)

    def test_earlier_checks_line_up_in_columns_between_hairlines(self):
        records = [record(days_ago(7), days_ago(1)), record(days_ago(30), days_ago(7), songs=0, url=None),
                   record(days_ago(60), days_ago(30), songs=12)]
        self.page.resize(900, 680)
        self.page.show()
        self.page.show_ready(NextWindow(days_ago(1), 'ready'), 5, 30, records)
        self.app.processEvents()
        counts = [found for found in self.page.history_box.findChildren(QLabel)
                  if found.text() in ('3 songs', 'Nothing new', '12 songs')]
        self.assertEqual(len(counts), 3)
        self.assertEqual(len({found.mapTo(self.page, QPoint(found.width(), 0)).x() for found in counts}), 1)
        # One hairline above "Earlier checks", then one between each pair of rows.
        self.assertEqual(len(self.rules(self.page.history_box)), 3)

    def test_done_variants_name_partial_saves_and_json_copies(self):
        copy = os.path.join('folder', 'tracklist_1.json')
        self.page.show_done('wavvie', 'u', [song(1)], json_file=copy)
        self.assertEqual(self.page.headline.text(), '1 new song saved')
        self.assertIn('tracklist_1.json', self.page.body.text())
        self.page.btn_extra.click()
        self.assertEqual(self.events[-1], ('show_file_requested', copy))
        self.page.show_done('wavvie', 'u', [song(1), song(2), song(3)], notes=['Spotify stopped responding.'], added=2)
        self.assertEqual(self.page.headline.text(), '2 of 3 songs saved')
        self.assertEqual(self.page.note.text(), 'Spotify stopped responding.')

    def test_end_states_offer_the_right_next_step(self):
        self.page.show_nothing_new(days_ago(7), ["Some artists couldn't be checked."])
        self.assertEqual(self.page.headline.text(), f'Nothing new since {short_date(days_ago(7))}')
        self.assertFalse(self.page.note.isHidden())
        self.assertTrue(self.page.btn_primary.isHidden())
        self.page.show_not_saved(3, 'Spotify is busy right now.')
        self.page.btn_primary.click()
        self.page.show_checking(4, days_ago(7))
        self.page.show_failed('Spotify reported a problem: boom')
        self.page.btn_primary.click()
        self.page.show_no_artists()
        self.page.btn_primary.click()
        self.assertEqual(self.events, [('retry_save_requested',), ('check_requested', days_ago(7)),
                                       ('refresh_artists_requested',)])

    def test_artwork_is_requested_only_near_the_visible_rows(self):
        requested = []
        self.page.artwork_requested.connect(requested.append)
        self.page.resize(720, 420)
        self.page.show()
        self.page.show_done('wavvie', 'u', [song(number, art=f'art-{number}') for number in range(40)])
        QTest.qWait(50)
        self.assertIn('art-0', requested)
        self.assertNotIn('art-39', requested)
        self.page.scroll.verticalScrollBar().setValue(self.page.scroll.verticalScrollBar().maximum())
        QTest.qWait(50)
        self.assertIn('art-39', requested)


if __name__ == '__main__':
    unittest.main()
