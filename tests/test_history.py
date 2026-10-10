"""Date windows, saved songs and playlist names for wavvie's check history."""
import unittest
from datetime import date

from core.history import (CheckHistory, CheckRecord, NextWindow, playlist_description, playlist_name,
                          release_label)

TODAY = date(2026, 10, 17)


def record(start, end, complete=True, ids=(), songs=0):
    return CheckRecord(start=start, end=end, ran_at=f'{end}T09:00:00', songs=songs, complete=complete,
                       track_ids=list(ids))


class NextWindowTests(unittest.TestCase):
    def test_first_check_looks_back_the_configured_days(self):
        self.assertEqual(CheckHistory().next_window(TODAY, 30), NextWindow(date(2026, 9, 17), 'first'))

    def test_next_check_starts_on_the_day_the_last_check_ran(self):
        history = CheckHistory([record('2026-09-10', '2026-10-10')])
        self.assertEqual(history.next_window(TODAY, 30), NextWindow(date(2026, 10, 10), 'ready'))

    def test_a_check_that_ran_today_means_up_to_date(self):
        history = CheckHistory([record('2026-10-10', '2026-10-17')])
        self.assertEqual(history.next_window(TODAY, 30), NextWindow(TODAY, 'up_to_date'))

    def test_a_newest_check_dated_after_today_suggests_today(self):
        history = CheckHistory([record('2026-10-10', '2026-10-20')])
        self.assertEqual(history.next_window(TODAY, 30), NextWindow(TODAY, 'up_to_date'))

    def test_unfinished_checks_are_finished_from_their_oldest_start(self):
        history = CheckHistory([record('2026-10-12', '2026-10-16', complete=False),
                                record('2026-10-10', '2026-10-12', complete=False),
                                record('2026-09-10', '2026-10-10')])
        self.assertEqual(history.next_window(TODAY, 30), NextWindow(date(2026, 10, 10), 'finish'))


class SavedSongTests(unittest.TestCase):
    def test_songs_saved_by_overlapping_checks_are_skipped(self):
        history = CheckHistory([record('2026-10-10', '2026-10-12', ids=['b']),
                                record('2026-09-10', '2026-10-10', ids=['a']),
                                record('2026-08-01', '2026-09-10', ids=['old'])])
        self.assertEqual(history.saved_ids_since(date(2026, 10, 10)), {'a', 'b'})

    def test_adding_a_check_keeps_twenty_and_drops_ids_the_next_check_cannot_overlap(self):
        history = CheckHistory([record(f'2026-01-{day:02d}', f'2026-01-{day + 1:02d}', ids=[f'id{day}'])
                                for day in range(25, 0, -1)])
        history.add(record('2026-10-10', '2026-10-17', ids=['new']), TODAY, 30)
        self.assertEqual(len(history.records), 20)
        self.assertEqual(history.records[0].track_ids, ['new'])
        self.assertTrue(all(older.track_ids == [] for older in history.records[1:]))

    def test_ids_from_unfinished_checks_are_kept(self):
        history = CheckHistory([record('2026-09-10', '2026-10-10', ids=['a'])])
        history.add(record('2026-10-10', '2026-10-14', complete=False, ids=['b']), TODAY, 30)
        self.assertEqual(history.saved_ids_since(date(2026, 10, 10)), {'a', 'b'})

    def test_history_round_trips_and_ignores_damaged_entries(self):
        history = CheckHistory([record('2026-09-10', '2026-10-10', ids=['a'], songs=3)])
        self.assertEqual(CheckHistory.from_json(history.to_json()).records, history.records)
        damaged = '[{"start": "not a date", "end": "2026-10-10", "ran_at": "x"}, {"unexpected": 1}, 5]'
        self.assertEqual(CheckHistory.from_json(damaged).records, [])
        self.assertEqual(CheckHistory.from_json('not json').records, [])
        self.assertEqual(CheckHistory.from_json('').records, [])


class PlaylistNameTests(unittest.TestCase):
    def test_names_show_the_checked_dates(self):
        cases = [((date(2026, 10, 10), date(2026, 10, 17)), 'wavvie · New releases 10 Oct – 17 Oct'),
                 ((date(2026, 9, 28), date(2026, 10, 3)), 'wavvie · New releases 28 Sep – 3 Oct'),
                 ((date(2026, 12, 28), date(2027, 1, 4)), 'wavvie · New releases 28 Dec 2026 – 4 Jan 2027'),
                 ((date(2026, 10, 17), date(2026, 10, 17)), 'wavvie · New releases 17 Oct')]
        for (start, end), expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(playlist_name(start, end), expected)

    def test_description_names_the_year_once(self):
        self.assertEqual(playlist_description(date(2026, 10, 10), date(2026, 10, 17)),
                         'New releases from artists you follow, 10 Oct – 17 Oct 2026. Made with wavvie.')
        self.assertEqual(playlist_description(date(2026, 12, 28), date(2027, 1, 4)),
                         'New releases from artists you follow, 28 Dec 2026 – 4 Jan 2027. Made with wavvie.')

    def test_release_dates_are_short_and_keep_their_precision(self):
        self.assertEqual([release_label(value) for value in ('2026-10-09', '2026-10', '2026', '')],
                         ['9 Oct', 'Oct 2026', '2026', ''])


if __name__ == '__main__':
    unittest.main()
