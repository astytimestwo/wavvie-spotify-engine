"""Offline UX regression coverage using real Qt widgets and isolated settings."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import io
import sys
import json
import tempfile
import time
import unittest
import importlib
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QSettings, Qt, QBuffer, QIODevice, QUrl, QThread
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QScrollArea
from PySide6.QtTest import QTest

from core.models import Track, ScanConfiguration, ScanResult, PlaylistResult
from core.spotify_service import SpotifyReleaseService
from core.workers import AuthWorker, ScanWorker, ImageLoadWorker, LoadArtistsWorker
from ui.main_window import MainWindow
from ui.pages.settings_page import SettingsPage
from ui.font_loader import load_bundled_fonts


def track(number=1, **changes):
    base = Track(str(number), f'Song {number}', 'Album <live>', 'album', 'single', '2026-09-01',
                 'Artist', 'artist', False, 'main', ['Artist'], f'song {number}|artist')
    return replace(base, **changes)


class DesktopUXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        load_bundled_fonts()

    def setUp(self):
        self.qt_errors = []
        patcher = patch.object(sys, 'excepthook', lambda *args: self.qt_errors.append(args))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: self.assertEqual(self.qt_errors, [], 'Unhandled exception in a Qt slot'))
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings_path = str(Path(self.directory.name) / 'settings.ini')
        class IsolatedSettings(QSettings):
            def __init__(self, *args, **kwargs):
                super().__init__(settings_path, QSettings.IniFormat)
        self.settings = IsolatedSettings()
        for name in ('ui.main_window', 'ui.pages.settings_page', 'ui.pages.dashboard_page'):
            patcher = patch.object(importlib.import_module(name), 'QSettings', IsolatedSettings)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch('ui.pages.auth_page.load_environment')
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.dict(os.environ, SPOTIPY_CLIENT_ID='test-id', SPOTIPY_CLIENT_SECRET='test-secret')
        patcher.start()
        self.addCleanup(patcher.stop)
        with patch.object(MainWindow, 'recheck_config'):
            self.window = MainWindow()
        self.window.service.user_data = {'id': 'test-user', 'display_name': 'Listener'}
        self.window.service.sp = MagicMock()
        self.window.on_artists_loaded([{'id': 'artist', 'name': 'Artist'}] * 5)
        self.window.switch_page(1)
        self.addCleanup(self.close_window)

    def close_window(self):
        self.window.thread_pool.waitForDone(2000)
        self.app.processEvents()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_selection_matches_visible_rows_and_actions(self):
        page = self.window.results_page
        page.create_playlist_requested.disconnect(self.window.create_playlist)
        tracks = [track(1), track(2, artist_name='Another', all_artists=['Another'])]
        page.set_results(tracks)
        captured = []
        page.create_playlist_requested.connect(captured.append)
        page.txt_search.setText('Another')
        self.assertEqual(page.selected_tracks(), [tracks[1]])
        self.assertIn('1 of 2 shown', page.lbl_selected_count.text())
        page.on_create_playlist_clicked()
        self.assertEqual(captured, [[tracks[1]]])
        page.toggle_all_selection(Qt.Unchecked.value)
        self.assertFalse(page.btn_export.isEnabled())
        self.assertTrue(page.item_widgets['1'].chk.isChecked())
        page.clear_filters()
        self.assertEqual(page.chk_select_all.checkState(), Qt.PartiallyChecked)
        page.toggle_all_selection(Qt.Checked.value)
        self.assertEqual(page.selected_tracks(), tracks)

    def test_empty_no_matches_and_reset_details(self):
        page = self.window.results_page
        self.assertFalse(page.btn_create_pl.isEnabled())
        page.set_results([track()])
        page.track_list.setCurrentRow(0)
        self.assertIsNotNone(page.detail_panel.current_track)
        page.txt_search.setText('nothing matches')
        self.assertIn('No releases match', page.empty_label.text())
        self.assertFalse(page.btn_export.isEnabled())
        page.set_results([])
        self.assertIsNone(page.detail_panel.current_track)
        self.assertFalse(page.detail_panel.btn_spotify.isEnabled())
        self.assertIn('No releases found', page.empty_label.text())

    def test_row_height_and_cached_artwork(self):
        page = self.window.results_page
        image = QImage(20, 20, QImage.Format_RGB32)
        image.fill(Qt.green)
        page.set_track_artwork('art', image)
        page.set_results([track(album_artwork_url='art')])
        self.assertGreaterEqual(page.track_list.item(0).sizeHint().height(), 72)
        self.assertFalse(page.item_widgets['1'].lbl_art.pixmap().isNull())
        page.track_list.setCurrentRow(0)
        self.assertIn('Album <live>', page.detail_panel.meta_text.toPlainText())
        self.assertNotIn('Signature', page.detail_panel.meta_text.toPlainText())

    def test_validation_gives_feedback_and_focus(self):
        page = self.window.scan_page
        emitted = []
        page.start_scan_requested.connect(emitted.append)
        page.spin_start.setValue(5)
        page.spin_end.setValue(2)
        page.on_start_clicked()
        self.assertEqual(emitted, [])
        self.assertIn('End artist', page.lbl_validation.text())
        page.spin_end.setValue(5)
        page.txt_playlist_name.setText('   ')
        page.on_start_clicked()
        self.assertIn('playlist name', page.lbl_validation.text())
        page.set_total_artists(0)
        self.assertFalse(page.btn_start.isEnabled())

    def test_settings_load_does_not_overwrite_saved_values(self):
        self.settings.setValue('default_playlist_name', 'My mix')
        self.settings.setValue('auto_export_json', False)
        self.settings.setValue('auto_create_playlist', False)
        self.settings.setValue('default_workers', 3)
        self.settings.setValue('reduced_motion', True)
        page = SettingsPage()
        self.addCleanup(page.deleteLater)
        self.assertEqual(self.settings.value('default_playlist_name'), 'My mix')
        self.assertFalse(self.settings.value('auto_export_json', type=bool))
        self.assertFalse(page.chk_create_pl.isChecked())
        page.spin_workers.setValue(4)
        self.assertEqual(self.settings.value('default_workers', type=int), 4)
        self.assertEqual(page.lbl_saved.text(), 'Preferences saved.')

    def test_reduced_motion_and_hidden_visualizers_stop_timers(self):
        self.window.show()
        self.app.processEvents()
        self.settings.setValue('reduced_motion', True)
        self.window.apply_preferences()
        self.assertFalse(self.window.dashboard_page.visualizer.timer.isActive())
        self.assertFalse(self.window.scan_page.visualizer.timer.isActive())
        self.assertFalse(self.window.sidebar.tip_timer.isActive())
        self.settings.setValue('reduced_motion', False)
        self.window.apply_preferences()
        self.assertTrue(self.window.dashboard_page.visualizer.timer.isActive())
        self.window.switch_page(3)
        self.app.processEvents()
        self.assertFalse(self.window.dashboard_page.visualizer.timer.isActive())

    def test_only_one_operation_and_cancellation_waits(self):
        window = self.window
        with patch.object(window.thread_pool, 'start') as start:
            config = ScanConfiguration(cutoff_date_str='2026-08-01')
            window.start_release_scan(config)
            window.start_release_scan(config)
            self.assertEqual(start.call_count, 1)
            window.cancel_release_scan()
            self.assertEqual(window.operation, 'cancelling')
            self.assertFalse(window.dashboard_page.btn_quick.isEnabled())
            self.assertFalse(window.scan_page.btn_cancel.isEnabled())
            window.start_release_scan(config)
            self.assertEqual(start.call_count, 1)
            window.on_scan_error('Scan cancelled by user.')
            self.assertTrue(window.dashboard_page.btn_quick.isEnabled())
            self.assertIsNone(window.scan_origin)

    def test_scan_worker_updates_real_window_and_automatic_actions(self):
        window = self.window
        window.service.get_and_cache_followed_artists = MagicMock(return_value=[{'id': 'artist', 'name': 'Artist'}])
        window.service.get_new_tracks = MagicMock(return_value=[asdict(track())])
        window.scan_origin = 'home'
        with patch.object(window, 'export_json') as export, patch.object(window, 'create_playlist') as playlist:
            window.start_release_scan(ScanConfiguration(cutoff_date_str='2026-08-01'))
            deadline = time.monotonic() + 3
            while window.operation and time.monotonic() < deadline:
                QTest.qWait(10)
            self.assertIsNone(window.operation)
            self.assertEqual(window.page_stack.currentIndex(), 1)
            self.assertEqual(window.scan_page.stacked_widget.currentIndex(), 0)
            self.assertEqual(window.results_page.selected_tracks()[0].track_id, '1')
            self.assertEqual(window.service.callbacks, {})
            export.assert_called_once()
            playlist.assert_called_once()
            self.assertIsNone(window.scan_origin)

    def test_warnings_skip_auto_playlist_but_keep_results(self):
        window = self.window
        window.active_scan_config = ScanConfiguration(export_json=False)
        window.scan_warnings = ['One artist failed']
        with patch.object(window, 'create_playlist') as playlist:
            window.on_scan_completed(ScanResult(tracks=[track()], total_artists=5, end_index=5))
        playlist.assert_not_called()
        self.assertIn('warnings', window.notice_text.text())
        self.assertEqual(window.results_page.selected_tracks(), [track()])

    def test_playlist_metadata_and_range_belong_to_displayed_results(self):
        window = self.window
        config = ScanConfiguration(playlist_name='Custom mix', playlist_description='My description',
                                   export_json=False, create_playlist_auto=False)
        window.active_scan_config = config
        window.on_scan_completed(ScanResult(tracks=[track()], start_index=2, end_index=4, total_artists=3))
        window.active_scan_config = ScanConfiguration(playlist_name='Another scan')
        with patch('ui.main_window.PlaylistWorker') as worker, patch.object(window.thread_pool, 'start'):
            window.create_playlist([track()])
        args = worker.call_args.args
        self.assertEqual(args[2].playlist_name, 'Custom mix')
        self.assertEqual(args[3:], (2, 4))
        window.on_playlist_created(PlaylistResult('Custom mix', 'p', 'https://open.spotify.com/playlist/p', 1))
        self.assertTrue(window.results_page.btn_create_pl.isEnabled())
        self.assertEqual(window.results_page.output_url, QUrl('https://open.spotify.com/playlist/p'))

    def test_manual_export_can_cancel_or_choose_destination(self):
        window = self.window
        window.results_range = (1, 5)
        with patch('ui.main_window.QFileDialog.getSaveFileName', return_value=('', '')):
            with patch.object(window.service, 'dump_tracklist_to_json') as export:
                window.export_json([track()], choose_path=True)
                export.assert_not_called()
        path = Path(self.directory.name) / 'chosen.json'
        with patch('ui.main_window.QFileDialog.getSaveFileName', return_value=(str(path), 'JSON')):
            window.export_json([track()], choose_path=True)
        self.assertEqual(json.loads(path.read_text())['metadata']['total_tracks'], 1)
        self.assertIn(str(path), window.results_page.output_label.text())

    def test_layouts_fit_supported_window_sizes(self):
        window = self.window
        window.results_page.set_results([track(track_name='A very long track title ' * 20)])
        window.show()
        for width, height in ((1000, 640), (1280, 820), (1600, 1000)):
            window.resize(width, height)
            self.app.processEvents()
            self.assertEqual(window.width(), width)
            self.assertEqual(window.height(), height)
            for index in range(6):
                window.switch_page(index)
                self.app.processEvents()
                current = window.page_stack.currentWidget()
                if isinstance(current, QScrollArea):
                    self.assertEqual(current.horizontalScrollBar().maximum(), 0, f'page {index}, {width}')
                self.assertLessEqual(current.width(), width)
            window.switch_page(3)
            self.app.processEvents()
            self.assertEqual(window.results_page.detail_panel.isVisible(), window.results_page.width() >= 1000)

    def test_activity_is_bounded_and_plain_text(self):
        page = self.window.activity_page
        for index in range(2100):
            page.append_log_record(f'line {index} <tag>', 20)
        page.refilter_logs()
        self.assertEqual(len(page.all_log_records), 2000)
        self.assertIn('<tag>', page.txt_log.toPlainText())
        self.assertTrue(page.refresh_timer.isActive())

    def test_missing_credentials_setup_fits_and_rechecks(self):
        with patch.dict(os.environ, SPOTIPY_CLIENT_ID='', SPOTIPY_CLIENT_SECRET=''):
            self.window.recheck_config()
            self.assertEqual(self.window.page_stack.currentIndex(), 0)
            self.assertFalse(self.window.service.is_configured())
            self.window.resize(1000, 640)
            self.window.show()
            self.app.processEvents()
            self.assertEqual(self.window.page_stack.currentWidget().horizontalScrollBar().maximum(), 0)
        with patch('ui.main_window.os.path.exists', return_value=False):
            self.window.recheck_config()
        self.assertTrue(self.window.service.is_configured())
        self.assertIsNotNone(self.window.auth_page.btn_connect)

    def test_outputs_remain_accessible_when_both_actions_finish(self):
        page = self.window.results_page
        page.show_output('Export saved', QUrl.fromLocalFile(self.directory.name), 'Open export folder')
        page.show_output('Playlist created', QUrl('https://open.spotify.com/playlist/p'), 'Open playlist')
        self.assertFalse(page.btn_export_folder.isHidden())
        self.assertFalse(page.btn_open_output.isHidden())
        self.assertIn('Export saved', page.output_label.text())
        self.assertIn('Playlist created', page.output_label.text())

    def test_image_completion_is_delivered_on_ui_thread(self):
        image = QImage(10, 10, QImage.Format_RGB32)
        image.fill(Qt.blue)
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, 'PNG')
        for index in range(5):
            threads = []
            with patch('core.workers.urllib.request.urlopen', return_value=io.BytesIO(bytes(buffer.data()))):
                self.window.download_image(f'https://example.test/image-{index}', lambda img: threads.append(QThread.currentThread()), 20)
                # The worker is released by its own queued slot, which can run after the image callback.
                deadline = time.monotonic() + 3
                while (not threads or self.window._workers) and time.monotonic() < deadline:
                    QTest.qWait(10)
            self.assertEqual(threads, [self.app.thread()])
            self.assertEqual(self.window.image_requests, {})
            self.assertEqual(self.window._workers, {})

    def test_artwork_requests_are_limited_to_visible_rows(self):
        page = self.window.results_page
        page.artwork_requested.disconnect(self.window.load_result_artwork)
        requested = []
        page.artwork_requested.connect(requested.append)
        page.set_results([track(i, album_artwork_url=f'art-{i}') for i in range(40)])
        self.window.show()
        self.window.switch_page(3)
        self.app.processEvents()
        self.assertGreater(len(set(requested)), 0)
        self.assertLess(len(set(requested)), 20)
        self.assertNotIn('art-39', requested)
        page.track_list.scrollToItem(page.track_list.item(39))
        self.app.processEvents()
        self.assertIn('art-39', requested)

    def test_closing_defers_destruction_until_workers_finish(self):
        window = self.window
        window.set_operation('scan')
        event = MagicMock()
        with patch.object(window.thread_pool, 'activeThreadCount', return_value=1):
            window.closeEvent(event)
        event.ignore.assert_called_once()
        self.assertTrue(window.closing)
        self.assertTrue(window.service.cancelled)
        self.assertFalse(window.scan_page.btn_start.isEnabled())
        with patch.object(window.thread_pool, 'activeThreadCount', return_value=0), patch.object(window, 'close') as close:
            window.finish_close()
        close.assert_called_once()

    def test_large_results_and_long_names_remain_usable(self):
        page = self.window.results_page
        started = time.monotonic()
        page.set_results([track(i) for i in range(1000)])
        initial_elapsed = time.monotonic() - started
        self.assertLess(initial_elapsed, 1, 'Initial results batch blocks the event loop')
        self.assertTrue(page.loading)
        self.assertFalse(page.btn_export.isEnabled())
        while page.loading and time.monotonic() - started < 8:
            QTest.qWait(10)
        elapsed = time.monotonic() - started
        self.assertEqual(page.track_list.count(), 1000)
        page.txt_search.setText('Song 999')
        self.assertEqual(len(page.selected_tracks()), 1)
        self.assertLess(elapsed, 8, 'Populating 1000 results unexpectedly stalls the UI')
        print(f'\n1000 result rows: initial batch {initial_elapsed:.2f}s; all rows {elapsed:.2f}s')

    def test_new_results_replace_pending_batches(self):
        page = self.window.results_page
        page.set_results([track(i) for i in range(500)])
        self.assertTrue(page.loading)
        page.set_results([track(999)])
        QTest.qWait(20)
        self.assertFalse(page.loading)
        self.assertEqual(page.selected_tracks(), [track(999)])

    def test_keyboard_search_and_form_accessibility(self):
        self.window.on_shortcut_focus_search()
        self.assertEqual(self.window.page_stack.currentIndex(), 3)
        self.assertTrue(self.window.scan_page.spin_start.accessibleName())
        self.assertTrue(self.window.settings_page.spin_workers.accessibleName())


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
