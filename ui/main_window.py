import os
import logging
from datetime import datetime
from typing import Dict, List, Optional
from PySide6.QtCore import Qt, QThreadPool, QSettings, Slot, QDate, QUrl, QTimer
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QFrame, QLabel, QPushButton, QScrollArea, QFileDialog, QGridLayout
from PySide6.QtGui import QImage, QIcon, QAction, QKeySequence

from ui.theme import Theme
from ui.resources import resource_path
from ui.widgets.sidebar import Sidebar
from ui.pages.auth_page import AuthPage
from ui.pages.dashboard_page import DashboardPage
from ui.pages.scan_page import ScanPage
from ui.pages.results_page import ResultsPage
from ui.pages.activity_page import ActivityPage
from ui.pages.settings_page import SettingsPage

from core.spotify_service import SpotifyReleaseService
from core.models import ScanConfiguration, ScanResult, PlaylistResult, Track
from core.workers import AuthWorker, LoadArtistsWorker, ScanWorker, PlaylistWorker, ImageLoadWorker

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("wavvie - Spotify Release Dashboard")
        self.setWindowIcon(QIcon(str(resource_path("wavvie.ico"))))
        self.setMinimumSize(1000, 640)
        self.resize(1280, 820)
        self.setStyleSheet(Theme.get_style_sheet())
        
        # Init thread pool and service
        self.thread_pool = QThreadPool(self)
        # Set max threads for image downloading / concurrent tasks
        self.thread_pool.setMaxThreadCount(10)
        self.service = SpotifyReleaseService()
        self.operation = None
        self.scan_origin = None
        self.closing = False
        self.scan_warnings = []
        self.image_requests = {}
        self.account_generation = 0
        self.results_range = (1, 9999)
        self.results_config = None
        self._workers = {}
        
        # In-memory artwork/image cache
        self.artwork_cache: Dict[str, QImage] = {}
        
        # Set up UI layouts
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(0)
        
        # 1. Sidebar Navigation (hidden when unauthenticated)
        self.sidebar = Sidebar(self)
        self.sidebar.nav_changed.connect(self.switch_page)
        self.main_layout.addWidget(self.sidebar)
        
        # 2. Main Content Canvas Stack
        self.content_canvas = QFrame(self)
        self.content_canvas.setProperty("class", "canvas")
        self.content_layout = QVBoxLayout(self.content_canvas)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.notice = QFrame()
        notice_layout = QHBoxLayout(self.notice)
        self.notice_text = QLabel()
        self.notice_text.setWordWrap(True)
        self.notice_text.setTextFormat(Qt.PlainText)
        self.notice_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        notice_layout.addWidget(self.notice_text, 1)
        dismiss = QPushButton("Dismiss")
        dismiss.clicked.connect(self.notice.hide)
        notice_layout.addWidget(dismiss)
        self.content_layout.addWidget(self.notice)
        self.notice.hide()
        
        self.page_stack = QStackedWidget(self)
        self.content_layout.addWidget(self.page_stack)
        
        self.main_layout.addWidget(self.content_canvas, 1)
        
        # Instantiate pages
        self.auth_page = AuthPage(self)
        self.dashboard_page = DashboardPage(self)
        self.scan_page = ScanPage(self)
        self.results_page = ResultsPage(self)
        self.activity_page = ActivityPage(self)
        self.settings_page = SettingsPage(self)
        for page in (self.scan_page, self.settings_page):
            for grid in page.findChildren(QGridLayout):
                for row in range(grid.rowCount()):
                    label_item, control_item = grid.itemAtPosition(row, 0), grid.itemAtPosition(row, 1)
                    if label_item and control_item:
                        label, control = label_item.widget(), control_item.widget()
                        if isinstance(label, QLabel) and control and label is not control:
                            label.setBuddy(control)
                            control.setAccessibleName(label.text().rstrip(":"))
        
        # Add to stack
        self.page_stack.addWidget(self.scroll_page(self.auth_page))        # Index 0
        self.page_stack.addWidget(self.scroll_page(self.dashboard_page))   # Index 1
        self.page_stack.addWidget(self.scroll_page(self.scan_page))        # Index 2
        self.page_stack.addWidget(self.results_page)     # Index 3
        self.page_stack.addWidget(self.activity_page)    # Index 4
        self.page_stack.addWidget(self.scroll_page(self.settings_page))    # Index 5
        
        # Setup page connections
        self.auth_page.auth_requested.connect(self.start_authentication)
        self.auth_page.recheck_requested.connect(self.recheck_config)
        self.dashboard_page.quick_start_requested.connect(self.quick_start_scan)
        self.dashboard_page.cancel_scan_requested.connect(self.cancel_release_scan)
        self.dashboard_page.view_results_requested.connect(lambda: self.switch_page(3))
        self.scan_page.start_scan_requested.connect(self.start_release_scan)
        self.scan_page.cancel_scan_requested.connect(self.cancel_release_scan)
        self.results_page.create_playlist_requested.connect(self.create_playlist)
        self.results_page.artwork_requested.connect(self.load_result_artwork)
        self.results_page.export_json_requested.connect(lambda tracks: self.export_json(tracks, choose_path=True))
        self.settings_page.disconnect_requested.connect(self.disconnect_account)
        self.settings_page.clear_cache_requested.connect(self.clear_followed_cache)
        self.settings_page.settings_changed.connect(self.apply_preferences)
        
        # Keyboard shortcuts
        self.setup_shortcuts()
        self.apply_preferences()
        
        # Check initial connection status
        self.recheck_config()

    def scroll_page(self, page):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        return scroll

    def set_operation(self, operation):
        self.operation = operation
        busy = bool(operation) or self.closing
        ready = self.scan_page.total_artists_available > 0 and bool(self.service.user_data)
        self.scan_page.btn_start.setEnabled(ready and not busy)
        self.dashboard_page.btn_quick.setEnabled(ready and not busy)
        self.results_page.set_busy(busy)
        self.settings_page.btn_disconnect.setEnabled(not busy and bool(self.service.user_data))
        self.settings_page.btn_clear_cache.setEnabled(not busy and bool(self.service.user_data))

    def can_start_operation(self):
        return not self.operation and not self.closing

    def launch_worker(self, worker):
        # Keep signal objects alive until queued completion reaches the GUI thread.
        key = id(worker)
        self._workers[key] = worker
        worker.signals.finished.connect(lambda *args: self._workers.pop(key, None))
        worker.signals.error.connect(lambda *args: self._workers.pop(key, None))
        self.thread_pool.start(worker)

    def set_app_status(self, status: str):
        self.sidebar.set_status(status)

    def setup_shortcuts(self):
        # Ctrl+F to focus search in results
        self.act_focus_search = QAction(self)
        self.act_focus_search.setShortcut(QKeySequence("Ctrl+F"))
        self.act_focus_search.triggered.connect(self.on_shortcut_focus_search)
        self.addAction(self.act_focus_search)
        
        # Ctrl+L to open Activity log
        self.act_show_activity = QAction(self)
        self.act_show_activity.setShortcut(QKeySequence("Ctrl+L"))
        self.act_show_activity.triggered.connect(lambda: self.switch_page(4))
        self.addAction(self.act_show_activity)

    def on_shortcut_focus_search(self):
        if self.service.user_data:
            self.switch_page(3)
            self.results_page.focus_search()

    def show_toast(self, message: str, level: str = "info"):
        # Persistent feedback can be read, selected, and dismissed at the user's pace.
        color = {"error": Theme.ERROR, "warning": Theme.WARNING, "success": Theme.SOFT_MINT}.get(level, Theme.SECONDARY_TEXT)
        self.notice_text.setText(message)
        self.notice.setStyleSheet(f"QFrame {{ background: {Theme.ELEVATED_SURFACE}; border-radius: 12px; }} QLabel {{ color: {color}; }}")
        self.notice.show()

    def switch_page(self, idx: int):
        if idx and not self.service.user_data:
            idx = 0
        self.page_stack.setCurrentIndex(idx)
        self.sidebar.set_active_index(idx)

    def recheck_config(self):
        if not self.can_start_operation():
            return
        self.auth_page.update_ui_state()
        self.service = SpotifyReleaseService()
        
        if self.service.is_configured():
            # If env is present, check credentials in cache
            if os.path.exists(".spotifycache"):
                self.start_authentication()
            else:
                self.show_auth_required()
        else:
            self.show_auth_required()

    def show_auth_required(self):
        self.sidebar.hide()
        self.auth_page.set_connected(False)
        self.set_app_status("Not connected")
        self.switch_page(0)  # Show AuthPage

    def show_authenticated(self, user_data):
        self.sidebar.show()
        self.set_app_status("Connected")
        
        display_name = user_data.get('display_name') or 'Spotify User'
        self.auth_page.set_connected(True)
        
        # Load user avatar
        images = user_data.get('images', [])
        if images:
            self.download_image(images[0]['url'], lambda img: self.sidebar.update_user_profile(display_name, img), 64)
        else:
            self.sidebar.update_user_profile(display_name, None)
            
        self.dashboard_page.update_user_info(display_name)
        self.settings_page.update_connection_status(display_name, self.service.redirect_uri)
        
        # Load followed artists in background
        self.load_followed_artists()
        
        # Switch to Home dashboard
        self.switch_page(1)
        self.show_toast(f"Authenticated as {display_name}", "success")

    def disconnect_account(self):
        if not self.can_start_operation():
            return
        self.account_generation += 1
        self.service.disconnect()
        self.results_page.set_results([])
        self.results_page.has_scanned = False
        self.results_page.artwork_cache.clear()
        self.results_page.update_selection_metrics()
        self.artwork_cache.clear()
        self.scan_page.set_total_artists(0)
        self.dashboard_page.show_scan_ready()
        self.dashboard_page.update_followed_artists_count(0)
        self.results_config = None
        self.results_range = (1, 9999)
        self.auth_page.set_connected(False)
        self.sidebar.update_user_profile("", None)
        self.dashboard_page.update_user_info("")
        self.settings_page.update_connection_status("", self.service.redirect_uri)
        self.show_auth_required()
        self.show_toast("Spotify account disconnected.")
        self.set_operation(None)

    # --- ASYNC AUTH WORKER ---
    def start_authentication(self):
        if not self.can_start_operation():
            return
        self.set_operation("auth")
        self.auth_page.set_connecting(True)
        self.show_toast("Complete the Spotify sign-in in your browser. This window will update when you return.")
        self.set_app_status("Connecting")
        
        worker = AuthWorker(self.service)
        worker.signals.finished.connect(self.on_auth_success)
        worker.signals.error.connect(self.on_auth_error)
        self.launch_worker(worker)

    @Slot(object)
    def on_auth_success(self, user_data):
        self.set_operation(None)
        if self.closing:
            return
        self.auth_page.set_connecting(False)
        self.set_app_status("Connected")
        self.show_authenticated(user_data)

    @Slot(str)
    def on_auth_error(self, err_msg):
        self.set_operation(None)
        self.auth_page.set_connecting(False)
        self.set_app_status("Connection failed")
        self.show_toast(f"Could not connect to Spotify. Check your credentials and redirect URI, then try Connect again. {err_msg}", "error")
        self.show_auth_required()

    # --- ASYNC LOAD ARTISTS WORKER ---
    def load_followed_artists(self, refresh=False):
        if not self.can_start_operation():
            return
        self.service.cancelled = False
        self.set_operation("artists")
        self.set_app_status("Loading followed artists")
        worker = LoadArtistsWorker(self.service, refresh)
        worker.signals.finished.connect(self.on_artists_loaded)
        worker.signals.warning.connect(lambda msg: self.show_toast(msg, "warning"))
        worker.signals.error.connect(self.on_artists_error)
        self.launch_worker(worker)

    @Slot(object)
    def on_artists_loaded(self, artists):
        count = len(artists)
        self.dashboard_page.update_followed_artists_count(count)
        self.scan_page.set_total_artists(count)
        self.set_operation(None)
        self.set_app_status(f"Connected · {count} followed artists")
        if not count:
            self.show_toast("No followed artists found. Follow artists in Spotify, then refresh the list in Settings.", "warning")

    def on_artists_error(self, error):
        self.set_operation(None)
        self.set_app_status("Artist list unavailable")
        self.show_toast(f"Could not load artists. Use Refresh artist list in Settings to retry. {error}", "error")

    def clear_followed_cache(self):
        if not self.can_start_operation():
            return
        try:
            self.show_toast("Refreshing followed artists from Spotify…")
            self.load_followed_artists(refresh=True)
        except Exception as e:
            self.show_toast(f"Failed to clear cache: {e}", "error")

    def apply_preferences(self):
        # Refresh cutoff days, workers, etc. on the scan config forms
        settings = QSettings("wavvie", "SpotifyPlaylistCreator")
        reduced = settings.value("reduced_motion", False, type=bool)
        self.scan_page.visualizer.set_reduced_motion(reduced)
        self.dashboard_page.visualizer.set_reduced_motion(reduced)
        self.sidebar.set_reduced_motion(reduced)
        workers = settings.value("default_workers", 5, type=int)
        playlist_name = settings.value("default_playlist_name", "New Releases", type=str)
        playlist_desc = settings.value("default_playlist_desc", "New tracks from followed artists", type=str)
        auto_export = settings.value("auto_export_json", True, type=bool)
        auto_create = settings.value("auto_create_playlist", True, type=bool)
        
        self.scan_page.spin_workers.setValue(workers)
        self.scan_page.txt_playlist_name.setText(playlist_name)
        self.scan_page.txt_playlist_desc.setText(playlist_desc)
        self.scan_page.chk_export.setChecked(auto_export)
        self.scan_page.chk_create_playlist.setChecked(auto_create)
        
        # Calculate dynamic date based on cutoff days preference
        days = settings.value("default_cutoff_days", 30, type=int)
        cutoff_date = QDate.currentDate().addDays(-days)
        self.scan_page.date_cutoff.setDate(cutoff_date)
        actions = []
        if auto_export:
            actions.append("export JSON")
        if auto_create:
            actions.append("create a private playlist")
        summary = f"Quick Scan covers all followed artists from the last {days} days."
        if actions:
            summary += " After a successful scan: " + " and ".join(actions) + "."
        self.dashboard_page.quick_summary.setText(summary)

    # --- IMAGE ASYNC DOWNLOADER ---
    def download_image(self, url: str, callback, target_size: int = 200):
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
        def on_success(qimage):
            callbacks = self.image_requests.pop(key, [])
            if key[2] != self.account_generation:
                return
            if len(self.artwork_cache) >= 256:
                self.artwork_cache.pop(next(iter(self.artwork_cache)))
            self.artwork_cache[key] = qimage
            for apply_image in callbacks:
                apply_image(qimage)
        worker.signals.finished.connect(on_success)
        worker.signals.error.connect(lambda error: self.image_requests.pop(key, None))
        self.launch_worker(worker)

    # --- SCAN OPERATION ---
    def quick_start_scan(self):
        if not self.can_start_operation():
            return
        self.scan_origin = "home"
        self.switch_page(1)
        self.apply_preferences()
        self.scan_page.spin_start.setValue(1)
        self.scan_page.spin_end.setValue(self.scan_page.total_artists_available)
        self.scan_page.on_start_clicked()
        if self.operation != "scan":
            self.scan_origin = None
            self.switch_page(2)

    def start_release_scan(self, config: ScanConfiguration):
        if not self.can_start_operation():
            return
        self.set_operation("scan")
        self.scan_warnings = []
        self.notice.hide()
        if getattr(self, "scan_origin", None) != "home":
            self.scan_origin = "scan"
        self.scan_page.show_active()
        self.dashboard_page.show_scan_running(config)
        self.set_app_status("Scanning releases")
        self.active_scan_config = config
        
        # Log init params
        self.add_scan_log_line(f"Starting scan: Start Index {config.start_index}, End Index {config.end_index}", Theme.SPOTIFY_GREEN)
        self.add_scan_log_line(f"Cutoff Date: {config.cutoff_date_str}", Theme.SPOTIFY_GREEN)
        
        # Run scan worker
        self.scan_worker = ScanWorker(self.service, config)
        self.scan_worker.signals.started.connect(lambda: logger.info("Scan started..."))
        self.scan_worker.signals.artist_started.connect(self.on_scan_artist_started)
        self.scan_worker.signals.artist_scanned.connect(self.on_scan_artist_completed)
        self.scan_worker.signals.track_discovered.connect(self.on_scan_track_discovered)
        self.scan_worker.signals.duplicate_prevented.connect(self.on_scan_duplicate_prevented)
        self.scan_worker.signals.rate_limit.connect(self.on_scan_rate_limit)
        self.scan_worker.signals.warning.connect(self.on_scan_warning)
        self.scan_worker.signals.progress.connect(self.on_scan_progress)
        self.scan_worker.signals.finished.connect(self.on_scan_completed)
        self.scan_worker.signals.error.connect(self.on_scan_error)
        
        self.launch_worker(self.scan_worker)

    def cancel_release_scan(self):
        if self.operation != "scan":
            return
        self.set_operation("cancelling")
        self.service.cancel_scan()
        self.add_scan_log_line("Cancelling. Waiting for current requests to finish…", Theme.WARNING)
        self.dashboard_page.show_scan_cancelling()
        self.scan_page.btn_cancel.setEnabled(False)
        self.scan_page.btn_cancel.setText("Cancelling…")
        self.scan_page.lbl_status.setText("Waiting for current requests to finish…")
        self.set_app_status("Cancelling scan")

    def add_scan_log_line(self, message: str, color_hex: str = None):
        self.scan_page.add_log_line(message, color_hex)
        self.dashboard_page.add_scan_log_line(message, color_hex)

    @Slot(int, str, str)
    def on_scan_artist_started(self, idx, name, img_url):
        if self.operation != "scan":
            return
        self.current_artist_key = (idx, name)
        self.add_scan_log_line(f"Scanning artist [{idx}]: {name}")
        self.scan_page.set_current_artist(name, None)
        self.dashboard_page.set_scan_artist(name, None)
        
        # Retrieve image in background
        if img_url:
            def apply_artist_image(img):
                if self.operation != "scan" or self.current_artist_key != (idx, name):
                    return
                self.scan_page.set_current_artist(name, img)
                self.dashboard_page.set_scan_artist(name, img)
            self.download_image(img_url, apply_artist_image, 120)
        else:
            self.scan_page.set_current_artist(name, None)
            self.dashboard_page.set_scan_artist(name, None)

    @Slot(int, str, int)
    def on_scan_artist_completed(self, idx, name, count):
        self.add_scan_log_line(f"Finished {name} - Found {count} releases", Theme.MUTED_TEXT)

    @Slot(object)
    def on_scan_track_discovered(self, track):
        is_collab = track.is_collaboration
        role_tag = "[COLLAB]" if is_collab else "[MAIN]"
        color = Theme.SOFT_MINT if is_collab else Theme.CYAN_ACCENT
        
        # Log discoveries
        self.add_scan_log_line(f"{role_tag} Discovered: {track.artist_name} - {track.track_name}", color)
        
        # Trigger visualizer pulse
        self.scan_page.trigger_track_discovery(is_collab)
        self.dashboard_page.trigger_track_discovery(is_collab)
        
    @Slot(str)
    def load_result_artwork(self, url):
        if (url, 200, self.account_generation) not in self.image_requests:
            self.download_image(url, lambda img: self.results_page.set_track_artwork(url, img), 200)

    @Slot(str, str)
    def on_scan_duplicate_prevented(self, track_name, original_artist):
        self.add_scan_log_line(f"Skipped Duplicate: {track_name} (already found for {original_artist})", Theme.MUTED_TEXT)

    @Slot(int)
    def on_scan_rate_limit(self, retry_after):
        self.add_scan_log_line(f"[RATE LIMIT] Hit rate limits. Sleeping for {retry_after}s...", Theme.WARNING)
        if self.operation == "scan":
            self.set_app_status("Spotify asked us to slow down")
            self.scan_page.lbl_status.setText(f"Spotify is busy. Retrying automatically in about {retry_after}s…")
            self.scan_page.visualizer.set_state("rate_limit")
            self.dashboard_page.visualizer.set_state("rate_limit")

    def on_scan_warning(self, message):
        self.scan_warnings.append(message)
        self.add_scan_log_line(message, Theme.WARNING)

    @Slot(object)
    def on_scan_progress(self, progress_tuple):
        if self.operation == "cancelling":
            return
        # Handle progress update
        prog_type, data = progress_tuple
        if prog_type == "progress":
            self.scan_page.lbl_status.setText("Discovering releases…")
            self.scan_page.visualizer.set_state("scanning")
            self.dashboard_page.visualizer.set_state("scanning")
            self.scan_page.update_scan_progress(data)
            self.dashboard_page.update_scan_progress(data)

    @Slot(object)
    def on_scan_completed(self, result: ScanResult):
        self.scan_page.show_config()
        self.set_operation(None)
        self.add_scan_log_line("Scan completed successfully!", Theme.SPOTIFY_GREEN)
        self.set_app_status("Scan complete")
        self.show_toast("Scan completed!", "success")
        
        # Populate Results Page
        self.results_page.set_results(result.tracks)
        if getattr(self, "scan_origin", None) != "home":
            self.switch_page(3) # Switch to Results page
        self.scan_origin = None
        self.last_result = result
        self.results_config = getattr(self, "active_scan_config", None)
        
        # Persist stats summary
        settings = QSettings("wavvie", "SpotifyPlaylistCreator")
        active_config = getattr(self, "active_scan_config", None)
        actual_start = getattr(result, "start_index", None)
        if not actual_start or (actual_start == 1 and active_config and active_config.start_index != 1):
            actual_start = getattr(active_config, "start_index", 1)
        actual_end = getattr(result, "end_index", None)
        if not actual_end or actual_end == 9999:
            actual_end = actual_start + max(0, result.total_artists - 1)
        settings.setValue("last_scan_start_idx", actual_start)
        settings.setValue("last_scan_end_idx", actual_end)
        self.results_range = (actual_start, actual_end)
        settings.setValue("last_scan_date", datetime.now().strftime("%Y-%m-%d %H:%M"))
        settings.setValue("last_scan_tracks", len(result.tracks))
        self.dashboard_page.load_dashboard_settings()
        self.dashboard_page.show_scan_complete(result)
        self.set_operation(None)
        if self.scan_warnings:
            self.show_toast(f"Scan finished with {len(self.scan_warnings)} warnings. Results may be incomplete; review Activity before creating a playlist.", "warning")
        elif not result.tracks:
            self.show_toast("No releases found. Try an earlier date or a wider artist range.")

        config = getattr(self, "active_scan_config", None)
        if result.tracks and config and config.export_json and not self.closing:
            self.export_json(result.tracks)
        if result.tracks and config and config.create_playlist_auto and not self.scan_warnings:
            self.create_playlist(result.tracks)
        if self.scan_warnings:
            self.show_toast(f"Scan finished with {len(self.scan_warnings)} warnings. Review Activity; automatic playlist creation was skipped.", "warning")

    @Slot(str)
    def on_scan_error(self, err_msg):
        self.scan_origin = None
        self.set_operation(None)
        self.add_scan_log_line(f"Scan Stopped: {err_msg}", Theme.ERROR)
        is_cancelled = "cancel" in err_msg.lower()
        self.set_app_status("Scan cancelled" if is_cancelled else "Scan failed")
        if is_cancelled:
            if getattr(self.dashboard_page, "scan_state", None) != "cancelled":
                self.dashboard_page.show_scan_cancelled()
            self.show_toast("Scan cancelled.", "warning")
        else:
            self.dashboard_page.show_scan_failed(err_msg)
            self.show_toast(f"Scan failed: {err_msg}", "error")
        self.scan_page.show_config()
        self.set_operation(None)

    # --- PLAYLIST & JSON EXPORTS ---
    def create_playlist(self, tracks: List[Track]):
        if not self.can_start_operation():
            return
        if not tracks:
            self.show_toast("No tracks selected.", "warning")
            return
            
        settings = QSettings("wavvie", "SpotifyPlaylistCreator")
        config = getattr(self, "results_config", None) or ScanConfiguration(
            playlist_name=settings.value("default_playlist_name", "New Releases", type=str),
            playlist_description=settings.value("default_playlist_desc", "New tracks from followed artists", type=str)
        )
        
        self.set_app_status("Creating playlist")
        self.set_operation("playlist")
        self.service.cancelled = False
        
        # Trigger background playlist creator worker
        # Use first and last indices as ranges
        start_idx, end_idx = self.results_range

        worker = PlaylistWorker(self.service, tracks, config, start_idx, end_idx)
        worker.signals.started.connect(lambda: self.show_toast("Creating Spotify playlist..."))
        worker.signals.finished.connect(self.on_playlist_created)
        worker.signals.error.connect(self.on_playlist_error)
        worker.signals.batch_completed.connect(lambda done, total: self.set_app_status(f"Creating playlist · batch {done}/{total}"))
        worker.signals.warning.connect(lambda msg: self.show_toast(msg, "warning"))
        
        self.launch_worker(worker)

    @Slot(object)
    def on_playlist_created(self, result: PlaylistResult):
        self.set_operation(None)
        self.set_app_status("Playlist created")
        message = f"Added {result.tracks_added} tracks to {result.playlist_name}."
        if result.error:
            message += f" Some tracks were not added: {result.error}"
            self.set_app_status("Playlist partially created")
        self.results_page.show_output(message, QUrl(result.playlist_url), "Open playlist in Spotify")
        self.show_toast(message + " Open it from Results.", "warning" if result.error else "success")

    def on_playlist_error(self, error):
        self.set_operation(None)
        self.set_app_status("Playlist creation failed")
        self.show_toast(f"Playlist could not be completed. Check Spotify before retrying to avoid creating a second playlist. {error}", "error")

    def export_json(self, tracks: List[Track], choose_path=False):
        if not tracks:
            self.show_toast("No tracks selected.", "warning")
            return
            
        settings = QSettings("wavvie", "SpotifyPlaylistCreator")
        start_idx, end_idx = self.results_range

        output_path = None
        if choose_path:
            output_path, _ = QFileDialog.getSaveFileName(self, "Export selected tracks", "wavvie-releases.json", "JSON files (*.json)")
            if not output_path:
                return
        filename = self.service.dump_tracklist_to_json(tracks, start_idx, end_idx, output_path=output_path)
        if filename:
            path = os.path.abspath(filename)
            self.results_page.show_output(f"Exported {len(tracks)} tracks to {path}", QUrl.fromLocalFile(os.path.dirname(path)), "Open export folder")
            self.show_toast(f"Exported {len(tracks)} tracks. Open the export folder from Results.", "success")
        else:
            self.show_toast("Failed to export JSON.", "error")

    def closeEvent(self, event):
        if self.thread_pool.activeThreadCount():
            event.ignore()
            if not self.closing:
                self.closing = True
                if self.operation == "scan":
                    self.cancel_release_scan()
                else:
                    self.service.cancel_scan()
                self.set_operation(self.operation)
                self.show_toast("Finishing active requests before closing. Any created playlist will remain in Spotify.")
                self.close_timer = QTimer(self)
                self.close_timer.timeout.connect(self.finish_close)
                self.close_timer.start(200)
            return
        logging.getLogger().removeHandler(self.activity_page.handler)
        event.accept()

    def finish_close(self):
        if not self.thread_pool.activeThreadCount():
            self.close_timer.stop()
            self.close()
