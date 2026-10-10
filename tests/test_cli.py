"""CLI orchestration with a stand-in service: no network, no files."""
import unittest
from unittest.mock import patch

import main
from core.models import PlaylistResult, ScanResult, Track


class StandInService:
    def __init__(self, result):
        self.result = result
        self.exports = []
        self.playlists = []

    def is_configured(self):
        return True

    def register_callback(self, event_name, callback):
        pass

    def authenticate(self):
        return True

    def scan_releases(self, config):
        return self.result

    def dump_tracklist_to_json(self, tracks, start_index, end_index, output_path=None):
        self.exports.append((len(tracks), start_index, end_index))
        return 'tracklist.json'

    def create_playlist(self, tracks, config, start_index, end_index, followed_artists=0):
        self.playlists.append((len(tracks), start_index, end_index, followed_artists))
        return PlaylistResult('New Releases', 'p', 'https://open.spotify.com/playlist/p', len(tracks))


class CliTests(unittest.TestCase):
    def run_cli(self, result):
        service = StandInService(result)
        with patch.object(main, 'SpotifyReleaseService', return_value=service):
            main.run_cli(1, 9999, '2026-09-01', False, False)
        return service

    def test_scan_without_new_releases_skips_outputs_without_reporting_failure(self):
        with self.assertNoLogs('main', level='ERROR'):
            service = self.run_cli(ScanResult(tracks=[], total_artists=5, end_index=5, followed_artists=5))

        self.assertEqual(service.exports, [])
        self.assertEqual(service.playlists, [])

    def test_outputs_receive_the_scanned_range_and_followed_artist_count(self):
        song = Track('t1', 'Song', 'Album', 'a', 'single', '2026-09-05', 'Nova', 'nova',
                     False, 'main', ['Nova'], 'song|nova')

        service = self.run_cli(ScanResult(tracks=[song], total_artists=3, start_index=1, end_index=3,
                                          followed_artists=3))

        self.assertEqual(service.exports, [(1, 1, 3)])
        self.assertEqual(service.playlists, [(1, 1, 3, 3)])


if __name__ == '__main__':
    unittest.main()
