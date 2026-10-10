"""wavvie's window: set up, sign in, check for new music, and settings."""
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional

from PySide6.QtCore import QSettings, Qt, QThreadPool, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from core.history import CheckHistory, CheckRecord, playlist_description, playlist_name
from core.models import ScanConfiguration, Track
from core.spotify_service import SpotifyReleaseService
from core.workers import AuthWorker, ImageLoadWorker, LoadArtistsWorker, PlaylistWorker, ScanWorker
from main import load_environment, save_environment
from ui.messages import friendly_error
from ui.pages.home_page import HomePage
from ui.pages.settings_page import SettingsPage, read_preferences
from ui.pages.setup_page import SetupPage
from ui.pages.sign_in_page import SignInPage
from ui.resources import resource_path
from ui.theme import Theme
from ui.widgets.activity_log import ActivityLog, ActivityLogDialog
from ui.widgets.avatar import Avatar
from ui.widgets.controls import button

SOME_ARTISTS_FAILED = "Some artists couldn't be checked. Your next check will look at these dates again."
PARTLY_SAVED = ("Spotify stopped responding while adding songs. Open the playlist to check it; "
                "your next check will pick up the rest.")


@dataclass
class PendingSave:
    """Songs a check found, waiting to be saved to a playlist."""
    tracks: List[Track]
    config: ScanConfiguration
    start_index: int
    end_index: int
    followed_artists: int
    complete: bool
    notes: List[str] = field(default_factory=list)
    json_file: Optional[str] = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("wavvie")
        self.setWindowIcon(QIcon(str(resource_path("wavvie.ico"))))
        self.setMinimumSize(720, 560)
        self.resize(900, 680)
        self.setStyleSheet(Theme.get_style_sheet())

        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(10)
        self.service = SpotifyReleaseService()
        self.operation = None
        self.closing = False
        self.sign_in_cancelled = False
        self.image_requests = {}
        self.artwork_cache = {}
        self.account_generation = 0
        self._workers = {}
        self.followed_count = 0
        self.history = CheckHistory()
        self.pending: Optional[PendingSave] = None
        self.check_start: Optional[date] = None
        self.check_end: Optional[date] = None
        self.check_range = None
        self.check_config: Optional[ScanConfiguration] = None
        self.scan_warnings: List[str] = []
        self.log_dialog = None
        self.activity_log = ActivityLog(self)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.header = QWidget()
        header = QHBoxLayout(self.header)
        header.setContentsMargins(24, 14, 24, 4)
        header.setSpacing(12)
        self.wordmark = QLabel()
        self.wordmark.setPixmap(QPixmap(str(resource_path("wavvie_wordmark_white.png")))
                                .scaledToHeight(28, Qt.SmoothTransformation))
        self.wordmark.setAccessibleName("wavvie")
        self.avatar = Avatar(30)
        self.btn_settings = button("Settings", "quiet", "openSettings")
        header.addWidget(self.wordmark)
        header.addStretch()
        header.addWidget(self.avatar)
        header.addWidget(self.btn_settings)
        layout.addWidget(self.header)
        self.header.hide()

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.setup_page = SetupPage(self.service.redirect_uri)
        self.sign_in_page = SignInPage()
        self.home_page = HomePage()
        self.settings_page = SettingsPage()
        for page in (self.setup_page, self.sign_in_page, self.home_page, self.settings_page):
            self.stack.addWidget(page)

        self.setup_page.credentials_entered.connect(self.save_credentials)
        self.setup_page.open_url_requested.connect(self.open_url)
        self.sign_in_page.connect_requested.connect(self.start_authentication)
        self.sign_in_page.cancel_requested.connect(self.cancel_authentication)
        self.home_page.check_requested.connect(self.start_check)
        self.home_page.stop_requested.connect(self.stop_check)
        self.home_page.done_requested.connect(self.show_home_ready)
        self.home_page.retry_save_requested.connect(self.save_pending)
        self.home_page.refresh_artists_requested.connect(lambda: self.load_followed_artists(refresh=True))
        self.home_page.open_url_requested.connect(self.open_url)
        self.home_page.show_file_requested.connect(self.show_file)
        self.home_page.artwork_requested.connect(self.load_artwork)
        self.btn_settings.clicked.connect(self.open_settings)
        self.settings_page.done_requested.connect(self.close_settings)
        self.settings_page.disconnect_requested.connect(self.disconnect_account)
        self.settings_page.refresh_artists_requested.connect(self.refresh_artists_from_settings)
        self.settings_page.activity_log_requested.connect(self.open_activity_log)
        self.settings_page.settings_changed.connect(self.on_settings_changed)
        for keys, slot in (("Ctrl+,", self.open_settings), ("Esc", self.close_settings),
                           ("Ctrl+L", self.open_activity_log)):
            action = QAction(self)
            action.setShortcut(QKeySequence(keys))
            action.triggered.connect(slot)
            self.addAction(action)

        self.apply_preferences()
        self.recheck_config()

    def show_page(self, page):
        self.stack.setCurrentWidget(page)
        self.header.setVisible(page in (self.home_page, self.settings_page))

    def set_operation(self, operation):
        self.operation = operation
        self.settings_page.set_busy(bool(operation) or self.closing)

    def can_start_operation(self):
        return not self.operation and not self.closing

    def launch_worker(self, worker):
        # Keep signal objects alive until queued completion reaches the GUI thread.
        key = id(worker)
        self._workers[key] = worker
        worker.signals.finished.connect(lambda *args: self._workers.pop(key, None))
        worker.signals.error.connect(lambda *args: self._workers.pop(key, None))
        self.thread_pool.start(worker)

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def show_file(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(os.path.abspath(path))))

    def recheck_config(self):
        if not self.can_start_operation():
            return
        load_environment(refresh=True)
        self.service = SpotifyReleaseService()
        self.setup_page.set_redirect_uri(self.service.redirect_uri)
        if not self.service.is_configured():
            self.show_page(self.setup_page)
        elif os.path.exists(self.service.cache_path):
            self.show_page(self.sign_in_page)
            self.start_authentication()
        else:
            self.sign_in_page.show_idle()
            self.show_page(self.sign_in_page)

    def save_credentials(self, values):
        try:
            save_environment(values)
        except OSError as error:
            self.setup_page.show_error(f"wavvie couldn't save your details: {error.strerror or error}")
            return
        self.recheck_config()

    def start_authentication(self):
        if not self.can_start_operation():
            return
        self.set_operation("auth")
        self.sign_in_cancelled = False
        self.sign_in_page.show_waiting()
        worker = AuthWorker(self.service)
        worker.signals.finished.connect(self.on_auth_success)
        worker.signals.error.connect(self.on_auth_error)
        self.launch_worker(worker)

    def cancel_authentication(self):
        if self.operation != "auth":
            return
        self.sign_in_cancelled = True
        self.service.cancel_authentication()

    def on_auth_success(self, user):
        self.set_operation(None)
        if self.closing:
            return
        name = user.get('display_name') or 'Spotify user'
        self.avatar.set_user(name)
        images = user.get('images') or []
        if images:
            self.download_image(images[0]['url'], lambda image: self.avatar.set_user(name, image), 64)
        self.settings_page.set_account(name)
        stored = QSettings("wavvie", "SpotifyPlaylistCreator").value(self.history_key(), "", type=str)
        self.history = CheckHistory.from_json(stored)
        self.show_page(self.home_page)
        self.load_followed_artists()

    def on_auth_error(self, message):
        self.set_operation(None)
        if self.closing:
            return
        error = None
        if not self.sign_in_cancelled:
            error = friendly_error(message, fallback=False) or (
                f"Couldn't connect to Spotify. Check that your app's redirect URI is "
                f"{self.service.redirect_uri}, then try again.")
        self.sign_in_page.show_idle(error)
        self.show_page(self.sign_in_page)

    def history_key(self):
        return f"check_history/{(self.service.user_data or {}).get('id', 'unknown')}"

    def load_followed_artists(self, refresh=False):
        if not self.can_start_operation():
            return
        self.service.cancelled = False
        self.set_operation("artists")
        self.home_page.show_loading_artists()
        worker = LoadArtistsWorker(self.service, refresh)
        worker.signals.finished.connect(self.on_artists_loaded)
        worker.signals.error.connect(self.on_artists_error)
        self.launch_worker(worker)

    def on_artists_loaded(self, artists):
        self.set_operation(None)
        self.followed_count = len(artists)
        self.settings_page.set_artist_count(self.followed_count)
        if not self.closing:
            self.show_home_ready()

    def on_artists_error(self, message):
        self.set_operation(None)
        if not self.closing:
            self.home_page.show_artists_failed(friendly_error(message))

    def refresh_artists_from_settings(self):
        self.close_settings()
        self.load_followed_artists(refresh=True)

    def show_home_ready(self):
        self.pending = None
        if not self.followed_count:
            self.home_page.show_no_artists()
            return
        look_back = read_preferences().look_back_days
        window = self.history.next_window(date.today(), look_back)
        self.home_page.show_ready(window, self.followed_count, look_back, self.history.records)

    def start_check(self, start=None):
        if not self.can_start_operation():
            return
        preferences = read_preferences()
        today = date.today()
        start = min(start or self.history.next_window(today, preferences.look_back_days).start, today)
        first, last = preferences.artist_range or (1, 9999)
        self.check_start, self.check_end, self.check_range = start, today, preferences.artist_range
        self.scan_warnings = []
        self.check_config = ScanConfiguration(
            start_index=first, end_index=last, cutoff_date_str=start.isoformat(),
            playlist_name=playlist_name(start, today), playlist_description=playlist_description(start, today),
            worker_count=preferences.workers, export_json=preferences.export_json, create_playlist_auto=True)
        self.set_operation("scan")
        self.service.cancelled = False
        self.home_page.show_checking(max(0, min(last, self.followed_count) - first + 1), start)
        worker = ScanWorker(self.service, self.check_config)
        worker.signals.progress.connect(self.on_check_progress)
        worker.signals.rate_limit.connect(self.home_page.show_rate_limited)
        worker.signals.warning.connect(self.scan_warnings.append)
        worker.signals.finished.connect(self.on_check_finished)
        worker.signals.error.connect(self.on_check_error)
        self.launch_worker(worker)

    def on_check_progress(self, update):
        if self.operation == "scan":
            progress = update[1]
            self.home_page.update_progress(progress.processed_artists, progress.total_artists, progress.tracks_found)

    def stop_check(self):
        if self.operation != "scan":
            return
        self.set_operation("cancelling")
        self.service.cancel_scan()
        self.home_page.show_stopping()

    def on_check_error(self, message):
        cancelled = self.operation == "cancelling" or self.service.cancelled
        self.set_operation(None)
        if self.closing:
            return
        if cancelled:
            self.home_page.show_stopped()
        else:
            self.home_page.show_failed(friendly_error(message))

    def on_check_finished(self, result):
        self.set_operation(None)
        if self.closing:
            return
        skip = self.history.saved_ids_since(self.check_start)
        tracks = [track for track in result.tracks if track.track_id not in skip]
        notes = []
        if self.scan_warnings:
            notes.append(SOME_ARTISTS_FAILED)
        if self.check_range:
            notes.append(f"Only artists {self.check_range[0]}–{self.check_range[1]} were checked, "
                         f"so your next check will look at these dates again.")
        complete = not self.scan_warnings and not self.check_range
        if not tracks:
            self.record_check(songs=0, complete=complete)
            self.home_page.show_nothing_new(self.check_start, notes)
            return
        json_file = None
        if self.check_config.export_json:
            json_file = self.service.dump_tracklist_to_json(tracks, result.start_index, result.end_index)
        self.pending = PendingSave(tracks, self.check_config, result.start_index, result.end_index,
                                   result.followed_artists, complete, notes, json_file)
        self.save_pending()

    def save_pending(self):
        if self.pending is None or not self.can_start_operation():
            return
        pending = self.pending
        self.set_operation("playlist")
        self.service.cancelled = False
        self.home_page.show_saving(len(pending.tracks))
        worker = PlaylistWorker(self.service, pending.tracks, pending.config, pending.start_index,
                                pending.end_index, pending.followed_artists)
        worker.signals.finished.connect(self.on_playlist_saved)
        worker.signals.error.connect(self.on_playlist_failed)
        self.launch_worker(worker)

    def on_playlist_saved(self, result):
        self.set_operation(None)
        pending, self.pending = self.pending, None
        if pending is None:
            return
        saved = list(dict.fromkeys(track.track_id for track in pending.tracks if track.track_id))
        added = saved[:result.tracks_added]
        partial = bool(result.error) or len(added) < len(saved)
        notes = pending.notes + ([PARTLY_SAVED] if partial else [])
        self.record_check(songs=len(added), complete=pending.complete and not partial, playlist=result,
                          track_ids=added)
        if not self.closing:
            self.home_page.show_done(result.playlist_name, result.playlist_url, pending.tracks, notes,
                                     pending.json_file, added=len(added) if partial else None)

    def on_playlist_failed(self, message):
        self.set_operation(None)
        if self.pending is not None and not self.closing:
            self.home_page.show_not_saved(len(self.pending.tracks), friendly_error(message))

    def record_check(self, songs, complete, playlist=None, track_ids=()):
        record = CheckRecord(
            start=self.check_start.isoformat(), end=self.check_end.isoformat(),
            ran_at=datetime.now().isoformat(timespec='seconds'), songs=songs,
            playlist_name=getattr(playlist, 'playlist_name', None),
            playlist_url=getattr(playlist, 'playlist_url', None), complete=complete,
            artist_range=f"{self.check_range[0]}–{self.check_range[1]}" if self.check_range else None,
            track_ids=list(track_ids))
        self.history.add(record, date.today(), read_preferences().look_back_days)
        QSettings("wavvie", "SpotifyPlaylistCreator").setValue(self.history_key(), self.history.to_json())

    def download_image(self, url, callback, target_size=200):
        if not url:
            return
        key = (url, target_size, self.account_generation)
        if key in self.artwork_cache:
            callback(self.artwork_cache[key])
            return
        if key in self.image_requests:
            self.image_requests[key].append(callback)
            return
        self.image_requests[key] = [callback]
        worker = ImageLoadWorker(url, target_size)

        def on_success(image):
            callbacks = self.image_requests.pop(key, [])
            if key[2] != self.account_generation:
                return
            if len(self.artwork_cache) >= 256:
                self.artwork_cache.pop(next(iter(self.artwork_cache)))
            self.artwork_cache[key] = image
            for apply_image in callbacks:
                apply_image(image)

        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(lambda error: self.image_requests.pop(key, None))
        self.launch_worker(worker)

    def load_artwork(self, url):
        self.download_image(url, lambda image: self.home_page.set_artwork(url, image), 80)

    def open_settings(self):
        if self.service.user_data:
            self.show_page(self.settings_page)

    def close_settings(self):
        if self.stack.currentWidget() is self.settings_page:
            self.show_page(self.home_page)

    def apply_preferences(self):
        self.home_page.set_reduced_motion(read_preferences().reduced_motion)

    def on_settings_changed(self):
        self.apply_preferences()
        if self.home_page.state == 'ready' and not self.operation:
            self.show_home_ready()

    def open_activity_log(self):
        if self.log_dialog is None:
            self.log_dialog = ActivityLogDialog(self.activity_log, self)
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()

    def disconnect_account(self):
        if not self.can_start_operation():
            return
        self.account_generation += 1
        self.service.disconnect()
        self.artwork_cache.clear()
        self.followed_count = 0
        self.history = CheckHistory()
        self.pending = None
        self.avatar.set_user("")
        self.settings_page.set_account("")
        self.sign_in_page.show_idle()
        self.show_page(self.sign_in_page)

    def closeEvent(self, event):
        if self.thread_pool.activeThreadCount():
            event.ignore()
            if not self.closing:
                self.closing = True
                if self.operation == "scan":
                    self.stop_check()
                elif self.operation == "auth":
                    self.cancel_authentication()
                else:
                    self.service.cancel_scan()
                self.set_operation(self.operation)
                self.setWindowTitle("wavvie (finishing up…)")
                self.close_timer = QTimer(self)
                self.close_timer.timeout.connect(self.finish_close)
                self.close_timer.start(200)
            return
        self.activity_log.detach()
        if self.log_dialog is not None:
            self.log_dialog.close()
        event.accept()

    def finish_close(self):
        if self.operation == "auth":
            # Close may have been requested before spotipy started waiting for the browser.
            self.service.cancel_authentication()
        if not self.thread_pool.activeThreadCount():
            self.close_timer.stop()
            self.close()
