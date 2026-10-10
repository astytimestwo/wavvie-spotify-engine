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

from PySide6.QtCore import QBuffer, QDate, QIODevice, QPoint, QSettings, Qt, QThread, QUrl
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractButton, QAbstractSpinBox, QApplication, QComboBox, QScrollArea

import main
from core.history import CheckHistory, CheckRecord, playlist_name, short_date
from core.models import Track, ScanConfiguration, ScanResult, PlaylistResult
from core.spotify_service import SpotifyReleaseService
from core.workers import AuthWorker, ScanWorker, ImageLoadWorker, LoadArtistsWorker
from fake_spotify import FakeSpotifyWebAPI, album, artist_ref, track as api_track
from ui.font_loader import load_bundled_fonts
from ui.main_window import MainWindow, PendingSave
from ui.messages import keep_together
from ui.widgets.tide import Tide
from ui.widgets.wordmark import Wordmark

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
        self.assertFalse(self.window.btn_settings.isVisibleTo(self.window))  # the page has its own Done
        self.window.settings_page.combo_look_back.setCurrentIndex(0)
        self.window.settings_page.btn_done.click()
        self.assertIs(self.window.stack.currentWidget(), home)
        self.assertTrue(self.window.btn_settings.isVisibleTo(self.window))
        self.assertEqual(home.btn_primary.text(), 'Check the last 7 days')

    def test_the_header_lines_up_with_the_column_and_stays_put(self):
        home = self.sign_in()
        self.assertIsInstance(self.window.wordmark, Wordmark)  # vector, so sharp at any display scale
        self.window.show()
        for width, height in ((720, 560), (900, 680), (1600, 1000)):
            self.window.resize(width, height)
            self.window.show_page(home)
            self.app.processEvents()
            left = home.headline.mapTo(self.window, QPoint(0, 0)).x()
            right = left + home.headline.width()
            settings = self.window.btn_settings
            where = f'{width}×{height}'
            self.assertEqual(self.window.wordmark.mapTo(self.window, QPoint(0, 0)).x(), left, where)
            self.assertEqual(settings.mapTo(self.window, QPoint(settings.width(), 0)).x(), right, where)
            avatar = self.window.avatar.mapTo(self.window, QPoint(0, 0))
            self.window.show_page(self.window.settings_page)
            self.app.processEvents()
            self.assertEqual(self.window.avatar.mapTo(self.window, QPoint(0, 0)), avatar, where)

    def test_the_header_follows_the_column_when_the_page_scrolls(self):
        home = self.sign_in()
        self.window.show()
        self.window.resize(720, 560)
        songs = [track(number) for number in range(30)]
        for listed, scrolls in ((songs, True), (songs[:1], False)):
            home.show_done('wavvie', 'https://open.spotify.com/playlist/p', listed)
            self.app.processEvents()
            self.assertEqual(home.scroll.verticalScrollBar().isVisible(), scrolls)
            self.assertEqual(self.window.wordmark.mapTo(self.window, QPoint(0, 0)).x(),
                             home.headline.mapTo(self.window, QPoint(0, 0)).x(), f'{len(listed)} songs')

    def test_tab_only_stops_on_controls(self):
        home = self.sign_in()
        self.window.history = CheckHistory([CheckRecord(days_ago(9), days_ago(2), 'x', songs=3, playlist_name='wavvie',
                                                        playlist_url='https://open.spotify.com/playlist/p1')])
        self.window.show_home_ready()
        self.window.show()
        self.window.activateWindow()
        self.assertTrue(QTest.qWaitForWindowActive(self.window, 1000))
        for page in (home, self.window.settings_page):
            self.window.show_page(page)
            for _ in range(10):
                QTest.keyClick(self.app.focusWidget() or self.window, Qt.Key_Tab)
                focused = self.app.focusWidget()
                with self.subTest(page=type(page).__name__, stop=type(focused).__name__):
                    self.assertIsInstance(focused, (QAbstractButton, QComboBox, QAbstractSpinBox))

    def test_short_screens_sit_a_little_above_the_middle_over_the_tide(self):
        home = self.sign_in()  # first run: a headline, a sentence and one button
        sign_in = self.window.sign_in_page
        sign_in.show_idle()
        self.window.show()
        self.window.resize(900, 680)
        for page, first, last in ((home, home.headline, home.btn_primary), (sign_in, sign_in.logo, sign_in.btn_connect)):
            self.window.show_page(page)
            self.app.processEvents()
            viewport = page.scroll.viewport()
            above = first.mapTo(viewport, QPoint(0, 0)).y()
            below = viewport.height() - Tide.HEIGHT - last.mapTo(viewport, QPoint(0, last.height())).y()
            with self.subTest(page=type(page).__name__):
                self.assertIsInstance(page.scroll.widget(), Tide)
                self.assertGreater(below, 0)  # the tide keeps its own strip
                self.assertAlmostEqual(above / (above + below), 0.4, delta=0.06)

    def test_long_screens_scroll_from_the_top_and_end_above_the_tide(self):
        home = self.sign_in()
        self.window.show()
        self.window.resize(720, 560)
        home.show_done('wavvie', 'https://open.spotify.com/playlist/p', [track(number) for number in range(30)])
        self.app.processEvents()
        content = home.scroll.widget()
        self.assertGreater(content.height(), home.scroll.viewport().height())
        self.assertEqual(home.headline.mapTo(content, QPoint(0, 0)).y(), 20)
        last = home.song_rows[-1]
        self.assertLessEqual(last.mapTo(content, QPoint(0, last.height())).y(), content.height() - Tide.HEIGHT)

    def test_a_failed_sign_in_keeps_the_redirect_uri_on_one_line(self):
        self.window.on_auth_error('boom')
        message = self.window.sign_in_page.message.text()
        self.assertIn(keep_together(self.window.service.redirect_uri), message)
        self.assertEqual(message.replace('⁠', ''),
                         f"Couldn't connect to Spotify. Check that your app's redirect URI is "
                         f"{self.window.service.redirect_uri}, then try again.")

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

    def test_every_visible_button_does_what_it_says(self):
        home = self.sign_in()
        window, settings = self.window, self.window.settings_page
        user = dict(window.service.user_data)
        playlist = 'https://open.spotify.com/playlist/p1'
        earlier = CheckRecord(days_ago(9), days_ago(2), 'x', songs=3, playlist_name='wavvie', playlist_url=playlist)
        song = Track('t1', 'Glow', 'Glow', 'a', 'single', days_ago(2), 'Nova', 'nova', False, 'main', ['Nova'],
                     'glow|nova')
        json_copy = str(Path(self.directory.name) / 'tracklist_1.json')
        saved = []
        self.patch(patch.object(window.thread_pool, 'start'))  # workers never run; each click's effect is checked directly
        self.patch(patch('ui.main_window.save_environment', side_effect=lambda values: saved.append(values)))
        self.patch(patch.object(window.service, 'cancel_authentication'))

        def reset(page):
            window.set_operation(None)
            window.pending = None
            window.service.user_data = dict(user)
            window.service.cancelled = False
            window.followed_count = 2
            window.settings_page.set_account(user['display_name'])  # undo an earlier Disconnect click
            window.history = CheckHistory([earlier])
            if window.log_dialog is not None:
                window.log_dialog.close()
            window.show_page(page)

        def at_home(show):
            def enter():
                reset(home)
                show()
            return enter

        def dates():
            window.show_home_ready()
            home.btn_quiet.click()

        def checking():
            window.set_operation('scan')
            home.show_checking(2, date.today())

        def stopping():
            checking()
            window.stop_check()

        def not_saved():
            window.pending = PendingSave([song], ScanConfiguration(cutoff_date_str=days_ago(2)), 1, 2, 2, True)
            home.show_not_saved(1, 'Spotify is busy right now.')

        def failed():
            home.show_checking(2, date.today())
            home.show_failed('Spotify reported a problem: boom')

        def settings_page():
            reset(settings)
            self.settings.clear()
            settings.load_settings()
            if not settings.advanced.isHidden():
                settings.toggle_advanced()

        def advanced_settings():
            settings_page()
            settings.toggle_advanced()

        def activity_log():
            advanced_settings()
            window.open_activity_log()

        def sign_in_idle():
            reset(window.sign_in_page)
            window.sign_in_page.show_idle()

        def signing_in():
            sign_in_idle()
            window.start_authentication()

        def setup():
            reset(window.setup_page)
            window.setup_page.txt_id.setText('abc123')
            window.setup_page.txt_secret.setText('secret456')

        def opened(url):
            return lambda: self.assertEqual(self.opened[-1], url)

        def state(name):
            return lambda: self.assertEqual(home.state, name)

        def page(expected):
            return lambda: self.assertIs(window.stack.currentWidget(), expected)

        def operation(name):
            return lambda: self.assertEqual(window.operation, name)

        settings_buttons = {'closeSettings': page(home), 'disconnect': page(window.sign_in_page)}
        scenarios = [
            ('ready', at_home(window.show_home_ready), lambda: window, {
                'openSettings': page(settings), 'primaryAction': operation('scan'),
                'quietAction': lambda: self.assertFalse(home.dates_row.isHidden()),
                'openHistoryPlaylist': opened(playlist)}),
            ('changing dates', at_home(dates), lambda: window, {
                'openSettings': page(settings), 'primaryAction': operation('scan'),
                'useSuggestedDates': lambda: self.assertTrue(home.dates_row.isHidden()),
                'openHistoryPlaylist': opened(playlist)}),
            ('checking', at_home(checking), lambda: window, {
                'openSettings': page(settings), 'quietAction': operation('cancelling')}),
            ('stopping', at_home(stopping), lambda: window, {
                'openSettings': page(settings), 'quietAction': operation('cancelling')}),
            ('done', at_home(lambda: home.show_done('wavvie', playlist, [song], json_file=json_copy)), lambda: window, {
                'openSettings': page(settings), 'primaryAction': opened(playlist), 'quietAction': state('ready'),
                'extraAction': opened(QUrl.fromLocalFile(os.path.dirname(os.path.abspath(json_copy))).toString())}),
            ('nothing new', at_home(lambda: home.show_nothing_new(date.today())), lambda: window, {
                'openSettings': page(settings), 'quietAction': state('ready')}),
            ('not saved', at_home(not_saved), lambda: window, {
                'openSettings': page(settings), 'primaryAction': operation('playlist'),
                'quietAction': lambda: (self.assertEqual(home.state, 'ready'), self.assertIsNone(window.pending))}),
            ('stopped', at_home(home.show_stopped), lambda: window, {
                'openSettings': page(settings), 'quietAction': state('ready')}),
            ('failed', at_home(failed), lambda: window, {
                'openSettings': page(settings), 'primaryAction': operation('scan'), 'quietAction': state('ready')}),
            ('no artists', at_home(home.show_no_artists), lambda: window, {
                'openSettings': page(settings), 'primaryAction': operation('artists')}),
            ('artists failed', at_home(lambda: home.show_artists_failed('Spotify is busy right now.')), lambda: window, {
                'openSettings': page(settings), 'primaryAction': operation('artists')}),
            ('settings', settings_page, lambda: window, dict(settings_buttons, **{
                'toggleAdvanced': lambda: self.assertFalse(settings.advanced.isHidden())})),
            ('advanced settings', advanced_settings, lambda: window, dict(settings_buttons, **{
                'toggleAdvanced': lambda: self.assertTrue(settings.advanced.isHidden()),
                'artistRange': lambda: self.assertTrue(self.settings.value('artist_range_enabled', type=bool)),
                'saveJson': lambda: self.assertTrue(self.settings.value('auto_export_json', type=bool)),
                'reduceMotion': lambda: self.assertTrue(home.wave.reduced_motion),
                'refreshArtists': lambda: (self.assertEqual(window.operation, 'artists'),
                                           self.assertIs(window.stack.currentWidget(), home)),
                'viewActivityLog': lambda: self.assertTrue(window.log_dialog.isVisible())})),
            ('activity log', activity_log, lambda: window.log_dialog, {
                'copyLog': lambda: self.assertEqual(QGuiApplication.clipboard().text(), window.activity_log.text()),
                'closeLog': lambda: self.assertFalse(window.log_dialog.isVisible())}),
            ('sign in', sign_in_idle, lambda: window, {'connectSpotify': operation('auth')}),
            ('signing in', signing_in, lambda: window, {
                'cancelSignIn': lambda: self.assertTrue(window.sign_in_cancelled)}),
            ('setup', setup, lambda: window, {
                'openDashboard': opened('https://developer.spotify.com/dashboard'),
                'copyRedirect': lambda: self.assertEqual(QGuiApplication.clipboard().text(),
                                                         window.setup_page.redirect_uri),
                'saveCredentials': lambda: self.assertEqual(saved[-1]['SPOTIPY_CLIENT_ID'], 'abc123')}),
        ]

        def visible(root):
            return [found for found in root.findChildren(QAbstractButton)
                    if found.objectName() and found.isVisibleTo(root)]

        for name, enter, root, expectations in scenarios:
            enter()
            self.assertEqual(sorted({found.objectName() for found in visible(root())}), sorted(expectations), name)
            for button_name, verify in expectations.items():
                enter()
                targets = [found for found in visible(root()) if found.objectName() == button_name]
                self.assertTrue(targets, f'{name}: {button_name} is not visible')
                for target in targets:
                    target.click()
                    self.app.processEvents()
                    with self.subTest(state=name, button=button_name):
                        verify()

    def test_every_page_fits_supported_window_sizes_without_sideways_scrolling(self):
        long_title = 'An extremely long song title that keeps going and going ' * 4
        guest = artist_ref('guest', 'A guest artist with a very long name indeed ' * 3)
        self.api.artist_albums['nova'] = {'single': [album('long', long_title, 'single', days_ago(3), [NOVA])]}
        self.api.album_tracks['long'] = [api_track('long1', long_title, [NOVA, guest])]
        home = self.sign_in()
        home.btn_primary.click()
        self.wait_until(lambda: home.state == 'done')
        self.window.settings_page.toggle_advanced()
        self.window.show()
        for width, height in ((720, 560), (900, 680), (1600, 1000)):
            self.window.resize(width, height)
            for page in (self.window.setup_page, self.window.sign_in_page, home, self.window.settings_page):
                self.window.show_page(page)
                self.app.processEvents()
                self.assertEqual((self.window.width(), self.window.height()), (width, height))
                for area in page.findChildren(QScrollArea):
                    where = f'{type(page).__name__} at {width}×{height}'
                    self.assertEqual(area.horizontalScrollBar().maximum(), 0, where)
                    self.assertLessEqual(area.widget().width(), area.viewport().width(), where)


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
