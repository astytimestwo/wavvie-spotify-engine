"""Service behaviour against the Spotify Web API contract for Development Mode apps."""
import threading
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

    def test_uses_50_item_album_pages_where_spotify_still_allows_them(self):
        self.api.page_limit = 50
        unordered = [album(f'kite{n}', f'Kite {n}', 'single', f'{2000 + n % 20}-01-01', [KITE]) for n in range(120)]
        self.api.artist_albums['nova'] = {'appears_on': unordered}

        self.service.get_artist_albums_robust('nova', 'Nova', CUTOFF)

        self.assertEqual(self.album_requests('appears_on'), ['0', '50', '100'])

    def test_search_takes_each_query_in_one_request_where_allowed(self):
        self.api.page_limit = 50
        self.api.search_tracks = [kite_feature(number, '2026-09-20') for number in range(40)]

        self.service.get_artist_collaborations('nova', 'Nova', CUTOFF)

        self.assertEqual(len(self.api.requested('GET', '/search')), 6)

    def test_falls_back_to_10_item_pages_once_spotify_refuses_larger_ones(self):
        self.api.artist_albums['nova'] = {'single': [nova_single('new1', '2026-09-15')]}
        self.api.artist_albums['kite'] = {'single': [album('kite1', 'Kite 1', 'single', '2026-09-16', [KITE])]}

        found = [self.service.get_artist_albums_robust(artist_id, name, CUTOFF)
                 for artist_id, name in (('nova', 'Nova'), ('kite', 'Kite'))]

        self.assertEqual([[a['id'] for a in albums] for albums in found], [['new1'], ['kite1']])
        self.assertEqual(self.api.refused, 1)

    def test_unrelated_bad_requests_keep_large_pages(self):
        self.api.page_limit = 50
        route = self.api.route
        self.api.route = lambda method, path, query, body: (
            (400, {'error': {'status': 400, 'message': 'Malformed search query'}}) if path == '/search'
            else route(method, path, query, body))

        self.service.get_artist_collaborations('nova', 'Nova', CUTOFF)
        self.service.get_artist_albums_robust('nova', 'Nova', CUTOFF)

        self.assertEqual(self.api.requested('GET', '/artists/nova/albums')[0]['limit'], '50')

    def test_reads_every_page_when_spotify_caps_the_page_size_silently(self):
        self.api.large_pages = 'clamp'
        older = [album(f'kite{n}', f'Kite {n}', 'single', f'{2000 + n}-01-01', [KITE]) for n in range(24)]
        self.api.artist_albums['nova'] = {'appears_on': older + [album('late', 'Late', 'single', '2026-09-20', [KITE])]}

        albums = self.service.get_artist_albums_robust('nova', 'Nova', CUTOFF)

        self.assertEqual([a['id'] for a in albums], ['late'])

    def test_feature_notes_do_not_split_one_song_into_two_tracks(self):
        # Seen live: two editions of one album, one title missing its closing parenthesis.
        self.api.artist_albums['nova'] = {'appears_on': [album('edition1', 'Sky', 'album', '2026-10-02', [KITE])]}
        self.api.album_tracks['edition1'] = [track('t1', 'Baby Breath (feat. Nova)', [KITE, NOVA])]
        edition2 = album('edition2', 'Sky', 'album', '2026-10-01', [KITE])
        self.api.search_tracks = [track('t2', 'Baby Breath (feat. Nova', [KITE, NOVA], edition2)]

        tracks = self.service.get_new_tracks('nova', 'Nova', CUTOFF)

        self.assertEqual([t['track_id'] for t in tracks], ['t1'])

    def test_features_found_on_albums_name_the_releasing_artist(self):
        self.api.artist_albums['nova'] = {'appears_on': [album('sky', 'Sky', 'album', '2026-10-02', [KITE])]}
        self.api.album_tracks['sky'] = [track('t1', 'Baby Breath (feat. Nova)', [KITE, NOVA])]

        tracks = self.service.get_new_tracks('nova', 'Nova', CUTOFF)

        self.assertEqual([(t['main_artist'], t['performer_role']) for t in tracks], [('Kite', 'featured')])

    def test_artist_summary_counts_features_found_on_albums(self):
        self.api.artist_albums['nova'] = {'appears_on': [album('sky', 'Sky', 'album', '2026-10-02', [KITE])]}
        self.api.album_tracks['sky'] = [track('t1', 'Baby Breath (feat. Nova)', [KITE, NOVA])]

        with self.assertLogs('core.spotify_service', level='INFO') as logs:
            self.service.get_new_tracks('nova', 'Nova', CUTOFF)

        self.assertTrue(any('for Nova (1 collaborations)' in line for line in logs.output), logs.output)

    def test_repeated_album_listings_are_scanned_once(self):
        glow = album('glow', 'Glow', 'single', '2026-09-12', [NOVA])
        self.api.artist_albums['nova'] = {'single': [glow, glow]}
        self.api.album_tracks['glow'] = [track('glow1', 'Glow', [NOVA])]

        tracks = self.service.get_new_tracks('nova', 'Nova', CUTOFF)

        self.assertEqual([t['track_name'] for t in tracks], ['Glow'])
        self.assertEqual(len(self.api.requested('GET', '/albums/glow/tracks')), 1)

    def test_cancelling_during_a_rate_limit_wait_reports_no_warnings(self):
        route = self.api.route
        self.api.route = lambda method, path, query, body: (
            (429, {'error': {'status': 429, 'message': 'API rate limit exceeded'}}) if path.endswith('/albums')
            else route(method, path, query, body))
        waiting = threading.Event()
        self.service.register_callback('rate_limit_encountered', lambda seconds: waiting.set())
        scan = threading.Thread(target=self.service.get_artist_albums_robust, args=('nova', 'Nova', CUTOFF))
        scan.start()
        self.assertTrue(waiting.wait(5))

        self.service.cancel_scan()
        scan.join(5)

        self.assertFalse(scan.is_alive())
        self.assertEqual(self.warnings, [])

    def test_singles_with_four_or_more_tracks_are_labelled_ep(self):
        self.api.artist_albums['nova'] = {'single': [
            album('drive', 'Night Drive', 'single', '2026-09-12', [NOVA], total_tracks=4),
            album('glow', 'Glow', 'single', '2026-09-10', [NOVA], total_tracks=2),
        ]}
        self.api.album_tracks['drive'] = [track(f'drive{n}', f'Drive {n}', [NOVA]) for n in range(4)]
        self.api.album_tracks['glow'] = [track('glow1', 'Glow', [NOVA]), track('glow2', 'Glow (Edit)', [NOVA])]

        tracks = self.service.get_new_tracks('nova', 'Nova', CUTOFF)

        self.assertEqual({(t['album_name'], t['album_type']) for t in tracks},
                         {('Night Drive', 'ep'), ('Glow', 'single')})

    def test_features_on_four_track_singles_are_labelled_ep(self):
        on_ep = album('kite-ep', 'Kite EP', 'single', '2026-09-20', [KITE], total_tracks=5)
        self.api.search_tracks = [track('feature1', 'Wings (feat. Nova)', [KITE, NOVA], on_ep)]

        collaborations = self.service.get_artist_collaborations('nova', 'Nova', CUTOFF)

        self.assertEqual([t['album_type'] for t in collaborations], ['ep'])

    def test_playlist_name_mentions_the_artist_range_only_for_partial_scans(self):
        song = Track('t1', 'Song', 'Album', 'a', 'single', '2026-09-01', 'Nova', 'nova',
                     False, 'main', ['Nova'], 'song|nova')
        cases = [((1, 5), 'New Releases'), ((2, 5), 'New Releases (Artists 2-5)'),
                 ((1, 3), 'New Releases (Artists 1-3)')]
        for (start, end), expected in cases:
            with self.subTest(start=start, end=end):
                result = self.service.create_playlist([song], ScanConfiguration(), start, end, followed_artists=5)
                self.assertEqual(self.api.playlists[result.playlist_id]['body']['name'], expected)

    def test_create_playlist_adds_every_track_to_a_private_playlist(self):
        tracks = [Track(f't{n}', f'Song {n}', 'Album', 'a', 'single', '2026-09-01', 'Nova', 'nova',
                        False, 'main', ['Nova'], f'song {n}|nova') for n in range(150)]

        result = self.service.create_playlist(tracks, ScanConfiguration(), 2, 5)

        self.assertIsNone(result.error)
        self.assertEqual(result.tracks_added, 150)
        created = self.api.playlists[result.playlist_id]
        self.assertFalse(created['body']['public'])
        self.assertEqual(created['items'], [f'spotify:track:t{n}' for n in range(150)])

    def test_playlist_description_mentions_the_range_only_for_partial_scans(self):
        song = Track('t1', 'Song', 'Album', 'a', 'single', '2026-09-01', 'Nova', 'nova',
                     False, 'main', ['Nova'], 'song|nova')
        config = ScanConfiguration(playlist_description='Made with wavvie.')

        full = self.service.create_playlist([song], config, 1, 5, followed_artists=5)
        partial = self.service.create_playlist([song], config, 2, 5, followed_artists=5)

        self.assertEqual(self.api.playlists[full.playlist_id]['body']['description'], 'Made with wavvie.')
        self.assertEqual(self.api.playlists[partial.playlist_id]['body']['description'],
                         'Made with wavvie. - Range: 2-5')


if __name__ == '__main__':
    unittest.main()
