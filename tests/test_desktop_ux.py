"""Offline UX regression coverage using real Qt widgets and isolated settings."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import io
import importlib
import json
import logging
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from dataclasses import asdict, replace
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QBuffer, QDate, QIODevice, QSettings, Qt, QThread, QUrl
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import main
from core.history import CheckHistory, CheckRecord, playlist_name, short_date
from core.models import Track, ScanConfiguration, ScanResult, PlaylistResult
from core.spotify_service import SpotifyReleaseService
from core.workers import AuthWorker, ScanWorker, ImageLoadWorker, LoadArtistsWorker
from fake_spotify import FakeSpotifyWebAPI, album, artist_ref, track as api_track
from ui.font_loader import load_bundled_fonts
from ui.main_window import MainWindow

NOVA = artist_ref('nova', 'Nova')
KITE = artist_ref('kite', 'Kite')


def days_ago(count):
    return (date.today() - timedelta(days=count)).isoformat()


def png_bytes():
    image = QImage(4, 4, QImage.Format_RGB32)
    image.fill(Qt.blue)
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    image.save(buffer, 'PNG')
    return bytes(buffer.data())


def track(number=1, **changes):
    base = Track(str(number), f'Song {number}', 'Album <live>', 'album', 'single', '2026-09-01',
                 'Artist', 'artist', False, 'main', ['Artist'], f'song {number}|artist')
    return replace(base, **changes)


class BrowserSignIn:
    """A real spotipy sign-in waiting on its local redirect server, with the browser launch patched out."""
    def __init__(self, test, directory):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        self.redirect_uri = f'http://127.0.0.1:{port}/callback'
        self.cache_path = str(Path(directory) / 'token-cache')
        browser = patch('spotipy.oauth2.webbrowser.open')
        self.browser_opened = browser.start()
        test.addCleanup(browser.stop)
        # Never leave a test thread blocked on the redirect server.
        test.addCleanup(self.redirect_back, 'test_cleanup')

    def service(self):
        return SpotifyReleaseService(client_id='test-id', client_secret='test-secret',
                                     redirect_uri=self.redirect_uri, cache_path=self.cache_path)

    def wait_until_waiting(self):
        # spotipy opens the browser only after its redirect server is listening.
        deadline = time.monotonic() + 3
        while not self.browser_opened.called and time.monotonic() < deadline:
            QTest.qWait(10)
        return self.browser_opened.called

    def redirect_back(self, error):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            opener.open(f'{self.redirect_uri}?error={error}', timeout=1).close()
        except OSError:
            pass


class DesktopFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        load_bundled_fonts()

    def setUp(self):
        self.qt_errors = []
        self.patch(patch.object(sys, 'excepthook', lambda *args: self.qt_errors.append(args)))
        self.addCleanup(lambda: self.assertEqual(self.qt_errors, [], 'Unhandled exception in a Qt slot'))
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        previous = os.getcwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, previous)
        settings_path = str(Path(self.directory.name) / 'settings.ini')

        class IsolatedSettings(QSettings):
            def __init__(self, *args, **kwargs):
                super().__init__(settings_path, QSettings.IniFormat)

        self.settings = IsolatedSettings()
        for name in ('ui.main_window', 'ui.pages.settings_page'):
            self.patch(patch.object(importlib.import_module(name), 'QSettings', IsolatedSettings))
        self.patch(patch('ui.main_window.load_environment'))
        self.patch(patch.dict(os.environ, SPOTIPY_CLIENT_ID='test-id', SPOTIPY_CLIENT_SECRET='test-secret'))
        self.opened = []
        self.patch(patch('ui.main_window.QDesktopServices.openUrl',
                         side_effect=lambda url: self.opened.append(url.toString())))
        artwork = png_bytes()
        self.patch(patch('core.workers.urllib.request.urlopen', side_effect=lambda *args, **kwargs: io.BytesIO(artwork)))
        self.api = FakeSpotifyWebAPI()
        self.api.page_limit = 50
        self.api.followed = [NOVA, KITE]
        with patch.object(MainWindow, 'recheck_config'):
            self.window = MainWindow()
        self.addCleanup(self.close_window)

    def patch(self, patcher):
        patcher.start()
        self.addCleanup(patcher.stop)

    def close_window(self):
        self.window.thread_pool.waitForDone(3000)
        self.app.processEvents()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def wait_until(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(condition(), 'Timed out waiting for the window')

    def sign_in(self, user_id='listener'):
        service = SpotifyReleaseService(client_id='test-id', client_secret='test-secret')
        service.sp = self.api.client()
        service.user_data = {'id': user_id, 'display_name': 'Listener', 'images': []}
        service.sleep_between_requests = 0
        self.window.service = service
        self.window.on_auth_success(service.user_data)
        self.wait_until(lambda: self.window.operation is None)
        return self.window.home_page

    def release(self, artist, album_id, days, *titles):
        on = album(album_id, album_id.title(), 'single', days_ago(days), [artist], total_tracks=len(titles))
        self.api.artist_albums.setdefault(artist['id'], {}).setdefault('single', []).append(on)
        self.api.album_tracks[album_id] = [api_track(f'{album_id}{number}', title, [artist])
                                           for number, title in enumerate(titles, 1)]

    def hold_album_requests(self):
        gate = threading.Event()
        route = self.api.route

        def held(method, path, query, body):
            if path.endswith('/albums'):
                gate.wait(5)
            return route(method, path, query, body)

        self.api.route = held
        self.addCleanup(gate.set)
        return gate

    def stored_history(self, user_id='listener'):
        return CheckHistory.from_json(self.settings.value(f'check_history/{user_id}', '', type=str))

    def test_first_check_saves_a_dated_playlist_and_remembers_the_window(self):
        self.release(NOVA, 'glow', 3, 'Glow')
        home = self.sign_in()
        self.assertEqual(home.headline.text(), "Let's find your new music")
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'done')
        today, start = date.today(), date.today() - timedelta(days=30)
        created = self.api.playlists['playlist1']
        self.assertEqual(created['body']['name'], playlist_name(start, today))
        self.assertFalse(created['body']['public'])
        self.assertEqual(created['items'], ['spotify:track:glow1'])
        self.assertEqual(home.headline.text(), '1 new song saved')
        self.assertEqual([(r.start, r.end, r.songs, r.complete) for r in self.stored_history().records],
                         [(start.isoformat(), today.isoformat(), 1, True)])
        home.btn_quiet.click()
        self.assertEqual(home.headline.text(), "You're up to date")

    def test_next_check_starts_where_the_last_ended_and_skips_saved_songs(self):
        earlier = CheckHistory([CheckRecord(days_ago(9), days_ago(2), 'x', songs=1, track_ids=['glow1'])])
        self.settings.setValue('check_history/listener', earlier.to_json())
        self.release(NOVA, 'glow', 2, 'Glow', 'Glow (Night Mix)')
        home = self.sign_in()
        self.assertEqual(home.headline.text(), f'New music since {short_date(date.today() - timedelta(days=2))}')
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'done')
        self.assertEqual(self.api.playlists['playlist1']['items'], ['spotify:track:glow2'])

    def test_a_check_with_nothing_new_is_remembered_without_a_playlist(self):
        home = self.sign_in()
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'nothing_new')
        self.assertEqual(self.api.playlists, {})
        self.assertEqual([(r.songs, r.playlist_url, r.complete) for r in self.stored_history().records],
                         [(0, None, True)])

    def test_artists_that_fail_still_save_and_the_next_check_finishes_the_window(self):
        self.api.failures['/artists/kite/albums'] = 404
        self.release(NOVA, 'glow', 3, 'Glow')
        home = self.sign_in()
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'done')
        self.assertIn("Some artists couldn't be checked", home.note.text())
        self.assertFalse(self.stored_history().records[0].complete)
        home.btn_quiet.click()
        self.assertEqual(home.headline.text(), "Let's finish your last check")

    def test_a_playlist_spotify_did_not_create_can_be_saved_again(self):
        self.api.failures['/me/playlists'] = 500
        self.release(NOVA, 'glow', 3, 'Glow')
        home = self.sign_in()
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'not_saved')
        self.assertEqual(self.stored_history().records, [])
        del self.api.failures['/me/playlists']
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'done')
        self.assertEqual(self.api.playlists['playlist1']['items'], ['spotify:track:glow1'])
        self.assertEqual(len(self.stored_history().records), 1)

    def test_a_partly_saved_playlist_is_reported_and_finished_next_time(self):
        self.release(NOVA, 'big', 3, *[f'Song {number}' for number in range(120)])
        route = self.api.route
        calls = []

        def flaky(method, path, query, body):
            if path.endswith('/items'):
                calls.append(path)
                if len(calls) == 2:
                    return 500, {'error': {'status': 500, 'message': 'Server error'}}
            return route(method, path, query, body)

        self.api.route = flaky
        home = self.sign_in()
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'done')
        self.assertEqual(home.headline.text(), '100 of 120 songs saved')
        record = self.stored_history().records[0]
        self.assertEqual((record.songs, record.complete, len(record.track_ids)), (100, False, 100))

    def test_stopping_a_check_saves_nothing(self):
        gate = self.hold_album_requests()
        home = self.sign_in()
        home.btn_primary.click()
        self.assertEqual(home.state, 'checking')
        home.btn_quiet.click()
        self.assertEqual(home.btn_quiet.text(), 'Stopping…')
        gate.set()
        self.wait_until(lambda: home.state == 'stopped')
        self.assertEqual(self.api.playlists, {})
        self.assertEqual(self.stored_history().records, [])
        home.btn_quiet.click()
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'nothing_new')

    def test_changed_dates_apply_to_one_check(self):
        home = self.sign_in()
        home.btn_quiet.click()
        chosen = date.today() - timedelta(days=5)
        home.date_start.setDate(QDate(chosen.year, chosen.month, chosen.day))
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'nothing_new')
        self.assertEqual(self.window.check_config.cutoff_date_str, chosen.isoformat())
        self.assertEqual(self.stored_history().records[0].start, chosen.isoformat())
        home.btn_quiet.click()
        self.assertEqual(home.headline.text(), "You're up to date")

    def test_a_json_copy_is_saved_when_asked_for_and_its_folder_opens(self):
        self.settings.setValue('auto_export_json', True)
        self.release(NOVA, 'glow', 3, 'Glow')
        home = self.sign_in()
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'done')
        copies = list(Path(self.directory.name).glob('tracklist_*.json'))
        self.assertEqual(len(copies), 1)
        self.assertEqual(json.loads(copies[0].read_text(encoding='utf-8'))['metadata']['total_tracks'], 1)
        home.btn_extra.click()
        self.assertEqual(Path(QUrl(self.opened[-1]).toLocalFile()).resolve(), Path(self.directory.name).resolve())

    def test_checking_some_artists_keeps_the_window_open(self):
        for key, value in (('artist_range_enabled', True), ('artist_range_start', 2), ('artist_range_end', 2)):
            self.settings.setValue(key, value)
        self.release(NOVA, 'glow', 3, 'Glow')
        home = self.sign_in()
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'done')
        self.assertEqual((self.window.check_config.start_index, self.window.check_config.end_index), (2, 2))
        self.assertIn('Only artists 2–2 were checked', home.note.text())
        self.assertEqual(self.stored_history().records[0].artist_range, '2–2')
        self.assertTrue(self.api.playlists['playlist1']['body']['name'].endswith('(Artists 2-2)'))

    def test_settings_open_from_the_header_and_change_the_first_check(self):
        home = self.sign_in()
        self.window.btn_settings.click()
        self.assertIs(self.window.stack.currentWidget(), self.window.settings_page)
        self.window.settings_page.combo_look_back.setCurrentIndex(0)
        self.window.settings_page.btn_done.click()
        self.assertIs(self.window.stack.currentWidget(), home)
        self.assertEqual(home.btn_primary.text(), 'Check the last 7 days')

    def test_reduced_motion_keeps_the_wave_still(self):
        self.settings.setValue('reduced_motion', True)
        self.window.apply_preferences()
        home = self.window.home_page
        self.window.show_page(home)
        self.window.show()
        home.show_checking(5, date.today())
        self.app.processEvents()
        self.assertTrue(home.wave.isVisible())
        self.assertFalse(home.wave.timer.isActive())
        self.settings.setValue('reduced_motion', False)
        self.window.apply_preferences()
        self.assertTrue(home.wave.timer.isActive())

    def test_only_one_operation_runs_at_a_time(self):
        home = self.sign_in()
        with patch.object(self.window.thread_pool, 'start') as start:
            home.check_requested.emit(None)
            home.check_requested.emit(None)
            self.window.load_followed_artists()
        self.assertEqual(start.call_count, 1)
        self.window.set_operation(None)

    def test_each_account_keeps_its_own_history(self):
        other = CheckHistory([CheckRecord(days_ago(9), days_ago(2), 'x', songs=4)])
        self.settings.setValue('check_history/someone-else', other.to_json())
        home = self.sign_in('listener')
        self.assertEqual(home.headline.text(), "Let's find your new music")

    def test_disconnect_returns_to_sign_in_and_keeps_history(self):
        stored = CheckHistory([CheckRecord(days_ago(9), days_ago(2), 'x', songs=4)]).to_json()
        self.settings.setValue('check_history/listener', stored)
        self.sign_in()
        self.window.btn_settings.click()
        self.window.settings_page.btn_disconnect.click()
        self.assertIs(self.window.stack.currentWidget(), self.window.sign_in_page)
        self.assertTrue(self.window.header.isHidden())
        self.assertEqual(self.settings.value('check_history/listener', '', type=str), stored)

    def test_setup_saves_credentials_then_offers_sign_in(self):
        env_file = Path(self.directory.name) / '.env'
        with patch.dict(os.environ), patch.object(main, '_loaded_environment', {}), \
             patch('main.dotenv_search_paths', return_value=[str(env_file)]):
            os.environ.pop('SPOTIPY_CLIENT_ID')
            os.environ.pop('SPOTIPY_CLIENT_SECRET')
            self.window.recheck_config()
            self.assertIs(self.window.stack.currentWidget(), self.window.setup_page)
            self.assertTrue(self.window.header.isHidden())
            self.window.setup_page.txt_id.setText('abc123')
            self.window.setup_page.txt_secret.setText('secret456')
            self.window.setup_page.btn_save.click()
            self.assertIs(self.window.stack.currentWidget(), self.window.sign_in_page)
        self.assertIn("SPOTIPY_CLIENT_ID='abc123'", env_file.read_text())

    def test_cancel_sign_in_releases_the_browser_wait(self):
        sign_in = BrowserSignIn(self, self.directory.name)
        self.window.service = sign_in.service()
        self.window.show_page(self.window.sign_in_page)
        self.window.start_authentication()
        self.assertTrue(sign_in.wait_until_waiting())
        page = self.window.sign_in_page
        self.assertFalse(page.btn_cancel.isHidden())
        page.btn_cancel.click()
        self.wait_until(lambda: self.window.operation is None)
        self.assertFalse(page.btn_connect.isHidden())
        self.assertTrue(page.message.isHidden())

    def test_closing_during_sign_in_releases_the_browser_wait(self):
        sign_in = BrowserSignIn(self, self.directory.name)
        self.window.service = sign_in.service()
        self.window.show_page(self.window.sign_in_page)
        self.window.show()
        self.window.start_authentication()
        self.assertTrue(sign_in.wait_until_waiting())
        self.window.close()
        self.wait_until(lambda: not self.window.isVisible())
        self.assertEqual(self.window.thread_pool.activeThreadCount(), 0)

    def test_closing_during_a_check_waits_for_it_to_stop(self):
        gate = self.hold_album_requests()
        home = self.sign_in()
        self.window.show()
        home.btn_primary.click()
        self.window.close()
        self.assertTrue(self.window.isVisible())
        gate.set()
        self.wait_until(lambda: not self.window.isVisible())
        self.assertEqual(self.stored_history().records, [])

    def test_activity_log_opens_from_settings_and_copies(self):
        logging.getLogger('core.spotify_service').warning('Loaded 2 artists from cache')
        self.sign_in()
        self.window.btn_settings.click()
        settings = self.window.settings_page
        settings.btn_advanced.click()
        settings.btn_log.click()
        dialog = self.window.log_dialog
        self.assertTrue(dialog.isVisible())
        self.assertIn('Loaded 2 artists from cache', dialog.view.toPlainText())
        dialog.btn_copy.click()
        self.assertIn('Loaded 2 artists from cache', QGuiApplication.clipboard().text())
        dialog.btn_close.click()
        self.assertFalse(dialog.isVisible())

    def test_image_completion_is_delivered_on_the_ui_thread(self):
        for index in range(5):
            threads = []
            self.window.download_image(f'https://example.test/image-{index}',
                                       lambda image: threads.append(QThread.currentThread()), 20)
            # The worker is released by its own queued slot, which can run after the image callback.
            self.wait_until(lambda: threads and not self.window._workers)
            self.assertEqual(threads, [self.app.thread()])
            self.assertEqual(self.window.image_requests, {})


class WorkerAndServiceUXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.service = SpotifyReleaseService(client_id='test', client_secret='test')
        self.service.sp = MagicMock()
        self.service.user_data = {'id': 'user'}
        self.service.sleep_between_requests = 0

    def test_auth_failure_emits_once_and_detaches_callbacks(self):
        worker = AuthWorker(self.service)
        def fail():
            self.service.trigger_callback('auth_failed', 'Denied')
            return False
        self.service.authenticate = fail
        errors = []
        worker.signals.error.connect(errors.append)
        worker.run()
        self.assertEqual(errors, ['Denied'])
        self.assertEqual(self.service.callbacks, {})

    def test_cancel_authentication_releases_a_waiting_browser_sign_in(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        sign_in = BrowserSignIn(self, directory.name)
        service = sign_in.service()
        failures, outcome = [], []
        service.register_callback('auth_failed', failures.append)
        thread = threading.Thread(target=lambda: outcome.append(service.authenticate()))
        thread.start()
        self.assertTrue(sign_in.wait_until_waiting())

        service.cancel_authentication()
        thread.join(5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, [False])
        self.assertEqual(len(failures), 1)

    def test_image_load_scales_and_reports_decode_errors(self):
        image = QImage(100, 80, QImage.Format_RGB32)
        image.fill(Qt.green)
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, 'PNG')
        worker = ImageLoadWorker('https://example.test/art', 50)
        images, errors = [], []
        worker.signals.finished.connect(images.append)
        worker.signals.error.connect(errors.append)
        with patch('core.workers.urllib.request.urlopen', return_value=io.BytesIO(bytes(buffer.data()))):
            worker.run()
        self.assertEqual(images[0].width(), 50)
        self.assertEqual(errors, [])
        with patch('core.workers.urllib.request.urlopen', return_value=io.BytesIO(b'invalid')):
            worker.run()
        self.assertEqual(len(errors), 1)

    def test_duplicate_count_is_visible_in_scan_result(self):
        self.service.get_and_cache_followed_artists = MagicMock(return_value=[{'id': 'a', 'name': 'A'}, {'id': 'b', 'name': 'B'}])
        self.service.get_new_tracks = MagicMock(return_value=[asdict(track())])
        result = self.service.scan_releases(ScanConfiguration(cutoff_date_str='2026-08-01'))
        self.assertEqual(result.total_tracks, 1)
        self.assertEqual(result.duplicates_prevented, 1)

    def test_partial_playlist_preserves_link_and_confirmed_count(self):
        self.service.sp.current_user_playlist_create.return_value = {'id': 'p', 'external_urls': {'spotify': 'https://open.spotify.com/playlist/p'}}
        self.service.sp.playlist_add_items.side_effect = [None, RuntimeError('Connection lost')]
        result = self.service.create_playlist([track(i) for i in range(150)], ScanConfiguration(), 1, 5)
        self.assertEqual(result.tracks_added, 100)
        self.assertIn('Connection lost', result.error)
        self.assertEqual(self.service.sp.playlist_add_items.call_count, 2)
        self.assertEqual(result.playlist_id, 'p')

    def test_failed_artist_fetch_does_not_overwrite_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'artists.json'
            path.write_text('{"user_id":"old","artists":[]}')
            self.service.get_followed_artists = MagicMock(side_effect=RuntimeError('offline'))
            with self.assertRaises(RuntimeError):
                self.service.get_and_cache_followed_artists(str(path), refresh=True)
            self.assertEqual(json.loads(path.read_text())['user_id'], 'old')

    def test_account_cache_is_refreshed_on_account_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'artists.json'
            path.write_text('{"user_id":"old","artists":[{"id":"old"}]}')
            self.service.get_followed_artists = MagicMock(return_value=[{'id': 'new', 'name': 'New'}])
            artists = self.service.get_and_cache_followed_artists(str(path))
            self.assertEqual(artists[0]['id'], 'new')
            self.assertEqual(json.loads(path.read_text())['user_id'], 'user')

    def test_invalid_range_fails_before_network(self):
        errors = []
        self.service.register_callback('fatal_error', errors.append)
        self.assertIsNone(self.service.scan_releases(ScanConfiguration(start_index=5, end_index=2)))
        self.assertEqual(len(errors), 1)
        self.assertEqual(self.service.sp.mock_calls, [])

    def test_environment_recheck_updates_file_values_but_preserves_process_values(self):
        import main
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('SPOTIPY_CLIENT_ID=first\nSPOTIPY_CLIENT_SECRET=file-secret')
            with patch.dict(os.environ, {'SPOTIPY_CLIENT_SECRET': 'process-secret'}, clear=True), \
                 patch.object(main, '_loaded_environment', {}), \
                 patch.object(main, 'dotenv_search_paths', return_value=[path]):
                main.load_environment()
                self.assertEqual(os.environ['SPOTIPY_CLIENT_ID'], 'first')
                path.write_text('SPOTIPY_CLIENT_ID=second\nSPOTIPY_CLIENT_SECRET=changed')
                main.load_environment(refresh=True)
                self.assertEqual(os.environ['SPOTIPY_CLIENT_ID'], 'second')
                self.assertEqual(os.environ['SPOTIPY_CLIENT_SECRET'], 'process-secret')

    def test_cancellation_after_first_playlist_batch_has_accurate_count(self):
        self.service.sp.current_user_playlist_create.return_value = {'id': 'p', 'external_urls': {'spotify': 'https://open.spotify.com/playlist/p'}}
        self.service.register_callback('playlist_batch_completed', lambda *args: self.service.cancel_scan())
        result = self.service.create_playlist([track(i) for i in range(150)], ScanConfiguration(), 1, 5)
        self.assertEqual(result.tracks_added, 100)
        self.assertIn('Cancelled', result.error)
        self.assertEqual(self.service.sp.playlist_add_items.call_count, 1)

    def test_http_transport_does_not_retry_playlist_writes(self):
        with patch('core.spotify_service.SpotifyOAuth'), patch('core.spotify_service.spotipy.Spotify') as client:
            client.return_value.current_user.return_value = {'id': 'user'}
            self.assertTrue(self.service.authenticate())
        session = client.call_args.kwargs['requests_session']
        retry = session.get_adapter('https://api.spotify.com').max_retries
        self.assertEqual(retry.total, 0)
        self.assertFalse(retry.is_retry('POST', 500))
        self.assertFalse(retry.is_retry('POST', 429, has_retry_after=True))
        session.close()


if __name__ == '__main__':
    unittest.main()
