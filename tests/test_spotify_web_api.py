"""Service behaviour against the Spotify Web API contract for Development Mode apps."""
import unittest
from datetime import datetime

from core.models import ScanConfiguration, Track
from core.spotify_service import SpotifyReleaseService
from fake_spotify import FakeSpotifyWebAPI, artist_ref, album, track

NOVA = artist_ref('nova', 'Nova')
KITE = artist_ref('kite', 'Kite')
CUTOFF = datetime(2026, 9, 1)


def nova_single(album_id, release_date):
    return album(album_id, f'Single {album_id}', 'single', release_date, [NOVA])


def kite_feature(number, release_date):
    on_album = album(f'kite{number}', f'Kite release {number}', 'single', release_date, [KITE])
    return track(f'feature{number}', f'Song {number} (feat. Nova)', [KITE, NOVA], on_album)


class SpotifyWebApiTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeSpotifyWebAPI()
        self.service = SpotifyReleaseService(client_id='id', client_secret='secret')
        self.service.sp = self.api.client()
        self.service.user_data = {'id': 'listener'}
        self.service.sleep_between_requests = 0
        self.warnings = []
        self.service.register_callback('warning', self.warnings.append)

    def album_requests(self, group):
        return [query['offset'] for query in self.api.requested('GET', '/artists/nova/albums')
                if query.get('include_groups') == group]

    def test_scan_finds_releases_and_features_within_page_limits(self):
        glow = album('glow', 'Glow', 'single', '2026-09-12', [NOVA], total_tracks=2)
        self.api.artist_albums['nova'] = {
            'album': [album('archive', 'Archive', 'album', '2019-05-01', [NOVA])],
            'single': [glow],
        }
        self.api.album_tracks['glow'] = [track('glow1', 'Glow', [NOVA]), track('glow2', 'Glow (Night Mix)', [NOVA])]
        self.api.search_tracks = [kite_feature(1, '2026-09-20')]
        self.service.get_and_cache_followed_artists = lambda refresh=False: [NOVA]

        result = self.service.scan_releases(ScanConfiguration(cutoff_date_str='2026-09-01', worker_count=1))

        self.assertEqual(sorted(t.track_name for t in result.tracks),
                         ['Glow', 'Glow (Night Mix)', 'Song 1 (feat. Nova)'])
        self.assertEqual(self.warnings, [])

    def test_full_search_pages_continue_to_the_next_page(self):
        self.api.search_tracks = [kite_feature(number, '2026-09-20') for number in range(12)]

        collaborations = self.service.get_artist_collaborations('nova', 'Nova', CUTOFF)

        self.assertEqual(len(collaborations), 12)
        self.assertEqual(self.warnings, [])

    def test_search_finds_recent_features_behind_older_matches(self):
        older = [kite_feature(number, '2015-03-01') for number in range(200)]
        self.api.search_tracks = older + [kite_feature(999, '2026-09-20')]

        collaborations = self.service.get_artist_collaborations('nova', 'Nova', CUTOFF)

        self.assertEqual([t['track_name'] for t in collaborations], ['Song 999 (feat. Nova)'])

    def test_album_paging_stops_once_newest_first_results_pass_the_cutoff(self):
        recent = [nova_single(f'new{day}', f'2026-09-{day:02d}') for day in (20, 10, 2)]
        older = [nova_single(f'old{year}', f'{year}-06-01') for year in range(2025, 1995, -1)]
        self.api.artist_albums['nova'] = {'single': recent + older}

        albums = self.service.get_artist_albums_robust('nova', 'Nova', CUTOFF)

        self.assertEqual([a['id'] for a in albums], ['new20', 'new10', 'new2'])
        self.assertEqual(self.album_requests('single'), ['0'])

    def test_album_paging_reads_on_when_results_are_not_newest_first(self):
        first_page = [nova_single('old2020', '2020-01-01'), nova_single('new5', '2026-09-05')]
        first_page += [nova_single(f'old{year}', f'{year}-01-01') for year in range(2012, 2004, -1)]
        self.api.artist_albums['nova'] = {'single': first_page + [nova_single('new9', '2026-09-09')]}

        albums = self.service.get_artist_albums_robust('nova', 'Nova', CUTOFF)

        self.assertEqual([a['id'] for a in albums], ['new5', 'new9'])

    def test_repeated_album_listings_are_scanned_once(self):
        glow = album('glow', 'Glow', 'single', '2026-09-12', [NOVA])
        self.api.artist_albums['nova'] = {'single': [glow, glow]}
        self.api.album_tracks['glow'] = [track('glow1', 'Glow', [NOVA])]

        tracks = self.service.get_new_tracks('nova', 'Nova', CUTOFF)

        self.assertEqual([t['track_name'] for t in tracks], ['Glow'])
        self.assertEqual(len(self.api.requested('GET', '/albums/glow/tracks')), 1)

    def test_create_playlist_adds_every_track_to_a_private_playlist(self):
        tracks = [Track(f't{n}', f'Song {n}', 'Album', 'a', 'single', '2026-09-01', 'Nova', 'nova',
                        False, 'main', ['Nova'], f'song {n}|nova') for n in range(150)]

        result = self.service.create_playlist(tracks, ScanConfiguration(), 2, 5)

        self.assertIsNone(result.error)
        self.assertEqual(result.tracks_added, 150)
        created = self.api.playlists[result.playlist_id]
        self.assertFalse(created['body']['public'])
        self.assertEqual(created['items'], [f'spotify:track:t{n}' for n in range(150)])


if __name__ == '__main__':
    unittest.main()
