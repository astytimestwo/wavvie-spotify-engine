import os
import logging
from typing import Dict, List, Optional
from PySide6.QtCore import Qt, QThreadPool, QSettings, Slot, QDate
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QFrame, QLabel
from PySide6.QtGui import QImage, QIcon, QAction, QKeySequence

from ui.theme import Theme
from ui.widgets.sidebar import Sidebar
from ui.widgets.toast import Toast
from ui.pages.auth_page import AuthPage
from ui.pages.dashboard_page import DashboardPage
from ui.pages.scan_page import ScanPage
from ui.pages.results_page import ResultsPage
from ui.pages.activity_page import ActivityPage
from ui.pages.settings_page import SettingsPage

from core.spotify_service import SpotifyReleaseService
from core.models import ScanConfiguration, ScanResult, PlaylistResult
from core.workers import AuthWorker, LoadArtistsWorker, ScanWorker, PlaylistWorker, ImageLoadWorker

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Wavefeed - Spotify Release Dashboard")
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(Theme.get_style_sheet())
        
        # Init thread pool and service
        self.thread_pool = QThreadPool.globalInstance()
        # Set max threads for image downloading / concurrent tasks
        self.thread_pool.setMaxThreadCount(10)
        self.service = SpotifyReleaseService()
        
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
        
        self.page_stack = QStackedWidget(self)
        self.content_layout.addWidget(self.page_stack)
        
        # Bottom activity rail (persistent now-processing indicator)
        self.activity_rail = QFrame(self)
        self.activity_rail.setStyleSheet(f"""
            QFrame {{
                background-color: {Theme.SECONDARY_SURFACE};
                border-top: 1px solid {Theme.BORDER};
                border-bottom-right-radius: 26px;
                min-height: 36px;
                max-height: 36px;
            }}
            QLabel {{
                color: {Theme.SECONDARY_TEXT};
                font-size: 11px;
                font-family: {Theme.FONT_BODY};
                padding-left: 16px;
            }}
        """)
        ar_layout = QHBoxLayout(self.activity_rail)
        ar_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_ar_status = QLabel("Status: Idle")
        ar_layout.addWidget(self.lbl_ar_status)
        
        self.content_layout.addWidget(self.activity_rail)
        self.main_layout.addWidget(self.content_canvas, 1)
        
        # Instantiate pages
        self.auth_page = AuthPage(self)
        self.dashboard_page = DashboardPage(self)
        self.scan_page = ScanPage(self)
        self.results_page = ResultsPage(self)
        self.activity_page = ActivityPage(self)
        self.settings_page = SettingsPage(self)
        
        # Add to stack
        self.page_stack.addWidget(self.auth_page)        # Index 0
        self.page_stack.addWidget(self.dashboard_page)   # Index 1
        self.page_stack.addWidget(self.scan_page)        # Index 2
        self.page_stack.addWidget(self.results_page)     # Index 3
        self.page_stack.addWidget(self.activity_page)    # Index 4
        self.page_stack.addWidget(self.settings_page)    # Index 5
        
        # Setup page connections
        self.auth_page.auth_requested.connect(self.start_authentication)
        self.auth_page.recheck_requested.connect(self.recheck_config)
        self.dashboard_page.quick_start_requested.connect(self.quick_start_scan)
        self.scan_page.start_scan_requested.connect(self.start_release_scan)
        self.scan_page.cancel_scan_requested.connect(self.cancel_release_scan)
        self.results_page.create_playlist_requested.connect(self.create_playlist)
        self.results_page.export_json_requested.connect(self.export_json)
        self.settings_page.disconnect_requested.connect(self.disconnect_account)
        self.settings_page.clear_cache_requested.connect(self.clear_followed_cache)
        self.settings_page.settings_changed.connect(self.apply_preferences)
        
        # Keyboard shortcuts
        self.setup_shortcuts()
        
        # Check initial connection status
        self.recheck_config()

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
        if self.page_stack.currentIndex() == 3:  # ResultsPage
            self.results_page.focus_search()

    def show_toast(self, message: str, level: str = "info"):
        toast = Toast(message, level, self)
        toast.show_toast()

    def switch_page(self, idx: int):
        self.page_stack.setCurrentIndex(idx)
        self.sidebar.set_active_index(idx)

    def recheck_config(self):
        self.auth_page.update_ui_state()
        
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
        self.activity_rail.hide()
        self.switch_page(0)  # Show AuthPage

    def show_authenticated(self, user_data):
        self.sidebar.show()
        self.activity_rail.show()
        
        display_name = user_data.get('display_name', 'Spotify User')
        
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
        self.service.disconnect()
        self.sidebar.update_user_profile("Not Connected", None)
        self.dashboard_page.update_user_info("")
        self.settings_page.update_connection_status("", self.service.redirect_uri)
        self.show_auth_required()
        self.show_toast("Spotify account disconnected.")

    # --- ASYNC AUTH WORKER ---
    def start_authentication(self):
        self.auth_page.set_connecting(True)
        self.lbl_ar_status.setText("Status: Connecting to Spotify...")
        
        worker = AuthWorker(self.service)
        worker.signals.finished.connect(self.on_auth_success)
        worker.signals.error.connect(self.on_auth_error)
        self.thread_pool.start(worker)

    @Slot(object)
    def on_auth_success(self, user_data):
        self.auth_page.set_connecting(False)
        self.lbl_ar_status.setText("Status: Connected")
        self.show_authenticated(user_data)

    @Slot(str)
    def on_auth_error(self, err_msg):
        self.auth_page.set_connecting(False)
        self.lbl_ar_status.setText("Status: Connection Failed")
        self.show_toast(f"Connection failed: {err_msg}", "error")
        self.show_auth_required()

    # --- ASYNC LOAD ARTISTS WORKER ---
    def load_followed_artists(self, refresh=False):
        worker = LoadArtistsWorker(self.service, refresh)
        worker.signals.finished.connect(self.on_artists_loaded)
        worker.signals.warning.connect(lambda msg: self.show_toast(msg, "warning"))
        worker.signals.error.connect(lambda err: self.show_toast(f"Failed to load artists: {err}", "error"))
        self.thread_pool.start(worker)

    @Slot(object)
    def on_artists_loaded(self, artists):
        count = len(artists)
        self.dashboard_page.update_followed_artists_count(count)
        self.scan_page.set_total_artists(count)

    def clear_followed_cache(self):
        try:
            self.service.clear_artists_cache()
            self.show_toast("Followed artists cache cleared.", "success")
            self.load_followed_artists(refresh=True)
        except Exception as e:
            self.show_toast(f"Failed to clear cache: {e}", "error")

    def apply_preferences(self):
        # Refresh cutoff days, workers, etc. on the scan config forms
        settings = QSettings("Wavefeed", "SpotifyPlaylistCreator")
        workers = settings.value("default_workers", 5, type=int)
        playlist_name = settings.value("default_playlist_name", "New Releases", type=str)
        playlist_desc = settings.value("default_playlist_desc", "New tracks from followed artists", type=str)
        
        self.scan_page.spin_workers.setValue(workers)
        self.scan_page.txt_playlist_name.setText(playlist_name)
        self.scan_page.txt_playlist_desc.setText(playlist_desc)
        
        # Calculate dynamic date based on cutoff days preference
        days = settings.value("default_cutoff_days", 30, type=int)
        cutoff_date = QDate.currentDate().addDays(-days)
        self.scan_page.date_cutoff.setDate(cutoff_date)

    # --- IMAGE ASYNC DOWNLOADER ---
    def download_image(self, url: str, callback, target_size: int = 200):
        if not url:
            return
            
        if url in self.artwork_cache:
            callback(self.artwork_cache[url])
            return
            
        worker = ImageLoadWorker(url, target_size)
        def on_success(qimage):
            self.artwork_cache[url] = qimage
            callback(qimage)
        worker.signals.finished.connect(on_success)
        self.thread_pool.start(worker)

    # --- SCAN OPERATION ---
    def quick_start_scan(self):
        self.switch_page(2) # Switch to scan page
        # Automatically load preferences and trigger start click
        self.apply_preferences()
        self.scan_page.on_start_clicked()

    def start_release_scan(self, config: ScanConfiguration):
        self.scan_page.show_active()
        self.lbl_ar_status.setText("Status: Scanning releases...")
        
        # Persist scan ranges for playlist naming
        settings = QSettings("Wavefeed", "SpotifyPlaylistCreator")
        settings.setValue("last_scan_start_idx", config.config.start_index if hasattr(config, 'config') else config.start_index)
        settings.setValue("last_scan_end_idx", config.config.end_index if hasattr(config, 'config') else config.end_index)
        
        # Log init params
        self.scan_page.add_log_line(f"Starting scan: Start Index {config.start_index}, End Index {config.end_index}", Theme.SPOTIFY_GREEN)
        self.scan_page.add_log_line(f"Cutoff Date: {config.cutoff_date_str}", Theme.SPOTIFY_GREEN)
        
        # Run scan worker
        self.scan_worker = ScanWorker(self.service, config)
        self.scan_worker.signals.started.connect(lambda: logger.info("Scan started..."))
        self.scan_worker.signals.artist_started.connect(self.on_scan_artist_started)
        self.scan_worker.signals.artist_scanned.connect(self.on_scan_artist_completed)
        self.scan_worker.signals.track_discovered.connect(self.on_scan_track_discovered)
        self.scan_worker.signals.duplicate_prevented.connect(self.on_scan_duplicate_prevented)
        self.scan_worker.signals.rate_limit.connect(self.on_scan_rate_limit)
        self.scan_worker.signals.warning.connect(lambda msg: self.scan_page.add_log_line(f"[WARNING] {msg}", Theme.WARNING))
        self.scan_worker.signals.progress.connect(self.on_scan_progress)
        self.scan_worker.signals.finished.connect(self.on_scan_completed)
        self.scan_worker.signals.error.connect(self.on_scan_error)
        
        self.thread_pool.start(self.scan_worker)

    def cancel_release_scan(self):
        self.service.cancel_scan()
        self.scan_page.add_log_line("Cancelling scan operation cooperatively...", Theme.ERROR)
        self.lbl_ar_status.setText("Status: Cancelling scan...")

    @Slot(int, str, str)
    def on_scan_artist_started(self, idx, name, img_url):
        self.scan_page.add_log_line(f"Scanning artist [{idx}]: {name}")
        
        # Retrieve image in background
        if img_url:
            self.download_image(img_url, lambda img: self.scan_page.set_current_artist(name, img), 120)
        else:
            self.scan_page.set_current_artist(name, None)

    @Slot(int, str, int)
    def on_scan_artist_completed(self, idx, name, count):
        self.scan_page.add_log_line(f"Finished {name} - Found {count} releases", Theme.MUTED_TEXT)

    @Slot(object)
    def on_scan_track_discovered(self, track):
        is_collab = track.is_collaboration
        role_tag = "[COLLAB]" if is_collab else "[MAIN]"
        color = Theme.SOFT_MINT if is_collab else Theme.CYAN_ACCENT
        
        # Log discoveries
        self.scan_page.add_log_line(f"{role_tag} Discovered: {track.artist_name} - {track.track_name}", color)
        
        # Trigger visualizer pulse
        self.scan_page.trigger_track_discovery(is_collab)
        
        # Download artwork asynchronously
        if track.album_artwork_url:
            self.download_image(track.album_artwork_url, lambda img: self.results_page.set_track_artwork(track.album_artwork_url, img), 60)

    @Slot(str, str)
    def on_scan_duplicate_prevented(self, track_name, original_artist):
        self.scan_page.add_log_line(f"Skipped Duplicate: {track_name} (already found for {original_artist})", Theme.MUTED_TEXT)

    @Slot(int)
    def on_scan_rate_limit(self, retry_after):
        self.scan_page.add_log_line(f"[RATE LIMIT] Hit rate limits. Sleeping for {retry_after}s...", Theme.WARNING)

    @Slot(object)
    def on_scan_progress(self, progress_tuple):
        # Handle progress update
        prog_type, data = progress_tuple
        if prog_type == "progress":
            self.scan_page.update_scan_progress(data)

    @Slot(object)
    def on_scan_completed(self, result: ScanResult):
        self.scan_page.add_log_line("Scan completed successfully!", Theme.SPOTIFY_GREEN)
        self.lbl_ar_status.setText("Status: Scan Complete")
        self.show_toast("Scan completed!", "success")
        
        # Populate Results Page
        self.results_page.set_results(result.tracks)
        self.switch_page(3) # Switch to Results page
        
        # Persist stats summary
        settings = QSettings("Wavefeed", "SpotifyPlaylistCreator")
        settings.setValue("last_scan_date", datetime.now().strftime("%Y-%m-%d %H:%M"))
        settings.setValue("last_scan_tracks", len(result.tracks))
        self.dashboard_page.load_dashboard_settings()

    @Slot(str)
    def on_scan_error(self, err_msg):
        self.scan_page.add_log_line(f"Scan Stopped: {err_msg}", Theme.ERROR)
        self.lbl_ar_status.setText("Status: Scan Failed")
        self.show_toast(f"Scan failed: {err_msg}", "error")
        self.scan_page.show_config()

    # --- PLAYLIST & JSON EXPORTS ---
    def create_playlist(self, tracks: List[Track]):
        if not tracks:
            self.show_toast("No tracks selected.", "warning")
            return
            
        settings = QSettings("Wavefeed", "SpotifyPlaylistCreator")
        config = ScanConfiguration(
            playlist_name=settings.value("default_playlist_name", "New Releases", type=str),
            playlist_description=settings.value("default_playlist_desc", "New tracks from followed artists", type=str)
        )
        
        self.lbl_ar_status.setText("Status: Creating Spotify Playlist...")
        
        # Trigger background playlist creator worker
        # Use first and last indices as ranges
        start_idx = settings.value("last_scan_start_idx", 1, type=int)
        end_idx = settings.value("last_scan_end_idx", 9999, type=int)
        
        worker = PlaylistWorker(self.service, tracks, config, start_idx, end_idx)
        worker.signals.started.connect(lambda: self.show_toast("Creating Spotify playlist..."))
        worker.signals.finished.connect(self.on_playlist_created)
        worker.signals.error.connect(lambda err: self.show_toast(f"Playlist failed: {err}", "error"))
        worker.signals.warning.connect(lambda msg: self.show_toast(msg, "warning"))
        
        self.thread_pool.start(worker)

    @Slot(object)
    def on_playlist_created(self, result: PlaylistResult):
        self.lbl_ar_status.setText("Status: Playlist Created")
        self.show_toast(f"Playlist '{result.playlist_name}' created successfully!", "success")

    def export_json(self, tracks: List[Track]):
        if not tracks:
            self.show_toast("No tracks selected.", "warning")
            return
            
        settings = QSettings("Wavefeed", "SpotifyPlaylistCreator")
        start_idx = settings.value("last_scan_start_idx", 1, type=int)
        end_idx = settings.value("last_scan_end_idx", 9999, type=int)
        
        filename = self.service.dump_tracklist_to_json(tracks, start_idx, end_idx)
        if filename:
            self.show_toast(f"Tracklist exported to {filename}", "success")
        else:
            self.show_toast("Failed to export JSON.", "error")
