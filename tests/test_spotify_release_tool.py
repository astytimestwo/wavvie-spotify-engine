import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path
import re
from types import SimpleNamespace

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from core.models import ScanConfiguration, ScanProgress, ScanResult, Track
from core.spotify_service import SpotifyReleaseService
from ui.theme import Theme
from ui.widgets.sidebar import Sidebar
from ui.pages.dashboard_page import DashboardPage
from ui.pages.scan_page import ScanPage
from ui.main_window import MainWindow

class TestSpotifyReleaseService(unittest.TestCase):
    def setUp(self):
        self.service = SpotifyReleaseService(
            client_id="mock_id",
            client_secret="mock_secret",
            redirect_uri="http://mock.uri"
        )

    def test_parse_release_date(self):
        # YYYY-MM-DD
        self.assertEqual(self.service.parse_release_date("2026-06-27"), datetime(2026, 6, 27))
        # YYYY-MM
        self.assertEqual(self.service.parse_release_date("2026-06"), datetime(2026, 6, 1))
        # YYYY
        self.assertEqual(self.service.parse_release_date("2026"), datetime(2026, 1, 1))
        # Invalid
        self.assertIsNone(self.service.parse_release_date("invalid-date"))
        self.assertIsNone(self.service.parse_release_date(""))

    def test_create_track_signature(self):
        sig1 = self.service.create_track_signature("Song A", ["Artist X", "Artist Y"])
        sig2 = self.service.create_track_signature("song a", ["artist y", "artist x"])
        self.assertEqual(sig1, sig2)
        self.assertEqual(sig1, "song a|artist x|artist y")

    def test_should_include_album_type(self):
        self.assertTrue(self.service.should_include_album_type("album"))
        self.assertTrue(self.service.should_include_album_type("single"))
        self.assertTrue(self.service.should_include_album_type("ep"))
        self.assertTrue(self.service.should_include_album_type("appears_on"))
        self.assertFalse(self.service.should_include_album_type("compilation"))
        self.assertFalse(self.service.should_include_album_type("unknown"))

    def test_is_trashy_compilation(self):
        # Compilation type
        self.assertTrue(self.service.is_trashy_compilation({"album_type": "compilation", "name": "Chill Tracks"}))
        # Keywords in name
        self.assertTrue(self.service.is_trashy_compilation({"album_type": "album", "name": "Best Of Bonobo"}))
        self.assertTrue(self.service.is_trashy_compilation({"album_type": "album", "name": "Workout Mix 2026"}))
        self.assertTrue(self.service.is_trashy_compilation({"album_type": "album", "name": "Greatest Hits"}))
        # Clean album
        self.assertFalse(self.service.is_trashy_compilation({"album_type": "album", "name": "Migration"}))

    def test_prioritize_album_version(self):
        track_album = {"album_type": "album", "album_name": "Migration", "release_date": "2017-01-13"}
        track_single = {"album_type": "single", "album_name": "Kerala", "release_date": "2016-11-03"}
        track_comp = {"album_type": "compilation", "album_name": "LateNightTales", "release_date": "2019-10-10"}
        
        # Priority order: Album > Single > EP > Compilation
        result = self.service.prioritize_album_version([track_comp, track_single, track_album])
        self.assertEqual(result["album_type"], "album")
        self.assertEqual(result["album_name"], "Migration")

    def test_is_actual_performer(self):
        artists = [{"id": "artist_1", "name": "Artist 1"}, {"id": "artist_2", "name": "Artist 2"}]
        self.assertTrue(self.service.is_actual_performer(artists, "artist_1"))
        self.assertTrue(self.service.is_actual_performer(artists, "artist_2"))
        self.assertFalse(self.service.is_actual_performer(artists, "artist_3"))

    def test_cancellation_state(self):
        self.service.cancel_scan()
        self.assertTrue(self.service.cancelled)

    def test_only_approved_fonts_are_referenced(self):
        self.assertEqual(Theme.FONT_HEADINGS, "Loubag")
        self.assertEqual(Theme.FONT_BODY, "Agrandir")
        self.assertEqual(Theme.FONT_MONO, "Agrandir")

        forbidden_font_patterns = {
            "Space Grotesk": re.compile(r"\bSpace\s+Grotesk\b", re.IGNORECASE),
            "Inter": re.compile(r"\bInter\b", re.IGNORECASE),
            "JetBrains Mono": re.compile(r"\bJetBrains\s+Mono\b", re.IGNORECASE),
            "Segoe UI": re.compile(r"\bSegoe\s+UI\b", re.IGNORECASE),
            "Arial": re.compile(r"\bArial\b", re.IGNORECASE),
            "Futura": re.compile(r"\bFutura(?:\s+PT)?\b", re.IGNORECASE),
            "Helvetica": re.compile(r"\bHelvetica\b", re.IGNORECASE),
            "sans-serif": re.compile(r"\bsans-serif\b", re.IGNORECASE),
            "monospace": re.compile(r"\bmonospace\b", re.IGNORECASE),
            "monospaced": re.compile(r"\bmonospaced\b", re.IGNORECASE),
        }
        searchable_files = list(Path("ui").rglob("*.py"))

        offenders = []
        for path in searchable_files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for font_name, pattern in forbidden_font_patterns.items():
                if pattern.search(text):
                    offenders.append(f"{path}: {font_name}")

        self.assertEqual(offenders, [])

    def test_explicit_letter_spacing_is_not_negative(self):
        searchable_files = list(Path("ui").rglob("*.py"))
        spacing_pattern = re.compile(r"letter-spacing\s*:\s*([^;\"']+)", re.IGNORECASE)

        offenders = []
        for path in searchable_files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in spacing_pattern.finditer(text):
                value = match.group(1).strip()
                if value.startswith("-"):
                    offenders.append(f"{path}: {value}")

        self.assertEqual(offenders, [])

    def test_sidebar_set_active_index_does_not_reemit_navigation(self):
        app = QApplication.instance() or QApplication([])
        sidebar = Sidebar()
        emitted = []

        def mirror_main_window_switch(index):
            emitted.append(index)
            sidebar.set_active_index(index)

        sidebar.nav_changed.connect(mirror_main_window_switch)
        sidebar.on_nav_clicked(2)

        self.assertEqual(emitted, [2])
        self.assertTrue(sidebar.button_group[1].isChecked())
        self.assertFalse(sidebar.button_group[0].isChecked())

        emitted.clear()
        sidebar.on_nav_clicked(1)

        self.assertEqual(emitted, [1])
        self.assertTrue(sidebar.button_group[0].isChecked())
        self.assertFalse(sidebar.button_group[1].isChecked())

    def test_apply_preferences_updates_scan_action_toggles(self):
        settings = QSettings("wavvie", "SpotifyPlaylistCreator")
        original_auto_export = settings.value("auto_export_json", None)
        original_auto_create = settings.value("auto_create_playlist", None)

        def restore_settings():
            if original_auto_export is None:
                settings.remove("auto_export_json")
            else:
                settings.setValue("auto_export_json", original_auto_export)
            if original_auto_create is None:
                settings.remove("auto_create_playlist")
            else:
                settings.setValue("auto_create_playlist", original_auto_create)

        self.addCleanup(restore_settings)
        settings.setValue("auto_export_json", False)
        settings.setValue("auto_create_playlist", False)

        window = MainWindow.__new__(MainWindow)
        window.scan_page = MagicMock()

        MainWindow.apply_preferences(window)

        window.scan_page.chk_export.setChecked.assert_called_once_with(False)
        window.scan_page.chk_create_playlist.setChecked.assert_called_once_with(False)

    def test_scan_completion_runs_enabled_automatic_actions(self):
        window = MainWindow.__new__(MainWindow)
        window.scan_page = MagicMock()
        window.results_page = MagicMock()
        window.dashboard_page = MagicMock()
        window.set_app_status = MagicMock()
        window.show_toast = MagicMock()
        window.switch_page = MagicMock()
        window.export_json = MagicMock()
        window.create_playlist = MagicMock()
        window.active_scan_config = ScanConfiguration(export_json=True, create_playlist_auto=True)
        tracks = [Track(
            track_id="track-1",
            track_name="Song",
            album_name="Album",
            album_id="album-1",
            album_type="single",
            release_date="2026-06-27",
            artist_name="Artist",
            followed_artist_id="artist-1",
            is_collaboration=False,
            performer_role="main",
            all_artists=["Artist"],
            track_signature="song|artist",
        )]

        MainWindow.on_scan_completed(window, ScanResult(tracks=tracks))

        window.export_json.assert_called_once_with(tracks)
        window.create_playlist.assert_called_once_with(tracks)

    def test_scan_result_records_actual_artist_range(self):
        service = SpotifyReleaseService(client_id="mock_id", client_secret="mock_secret")
        service.sp = MagicMock()
        service.get_and_cache_followed_artists = MagicMock(return_value=[
            {"id": "artist-1", "name": "Alpha"},
            {"id": "artist-2", "name": "Beta"},
            {"id": "artist-3", "name": "Gamma"},
        ])
        service.get_new_tracks = MagicMock(return_value=[])

        result = service.scan_releases(ScanConfiguration(
            start_index=2,
            end_index=9999,
            cutoff_date_str="2026-06-01",
            worker_count=1,
        ))

        self.assertEqual(result.start_index, 2)
        self.assertEqual(result.end_index, 3)
        self.assertEqual(result.total_artists, 2)

    def test_scan_completion_persists_actual_artist_range_for_exports(self):
        settings = QSettings("wavvie", "SpotifyPlaylistCreator")
        original_start = settings.value("last_scan_start_idx", None)
        original_end = settings.value("last_scan_end_idx", None)

        def restore_settings():
            if original_start is None:
                settings.remove("last_scan_start_idx")
            else:
                settings.setValue("last_scan_start_idx", original_start)
            if original_end is None:
                settings.remove("last_scan_end_idx")
            else:
                settings.setValue("last_scan_end_idx", original_end)

        self.addCleanup(restore_settings)
        settings.setValue("last_scan_start_idx", 50)
        settings.setValue("last_scan_end_idx", 9999)

        window = MainWindow.__new__(MainWindow)
        window.scan_page = MagicMock()
        window.results_page = MagicMock()
        window.dashboard_page = MagicMock()
        window.set_app_status = MagicMock()
        window.show_toast = MagicMock()
        window.switch_page = MagicMock()
        window.export_json = MagicMock()
        window.create_playlist = MagicMock()
        window.active_scan_config = ScanConfiguration(
            start_index=50,
            end_index=9999,
            export_json=False,
            create_playlist_auto=False,
        )

        MainWindow.on_scan_completed(window, ScanResult(tracks=[], total_artists=51))

        self.assertEqual(settings.value("last_scan_start_idx", type=int), 50)
        self.assertEqual(settings.value("last_scan_end_idx", type=int), 100)

    def test_quick_start_stays_on_home_and_marks_origin(self):
        window = MainWindow.__new__(MainWindow)
        window.scan_origin = None
        window.switch_page = MagicMock()
        window.apply_preferences = MagicMock()
        window.scan_page = MagicMock()

        MainWindow.quick_start_scan(window)

        window.switch_page.assert_called_once_with(1)
        self.assertEqual(window.scan_origin, "home")
        window.scan_page.on_start_clicked.assert_called_once()

    def test_dashboard_running_state_updates_button_and_waveform(self):
        app = QApplication.instance() or QApplication([])
        dashboard = DashboardPage()

        dashboard.show_scan_running(ScanConfiguration(cutoff_date_str="2026-06-01"))

        self.assertEqual(dashboard.btn_quick.text(), "Running")
        self.assertFalse(dashboard.btn_quick.isEnabled())
        self.assertEqual(dashboard.pulse_subtitle.text(), "Running")
        self.assertNotEqual(dashboard.pulse_subtitle.text(), "Idle Waveform")
        self.assertEqual(dashboard.visualizer.state, "scanning")

    def test_scan_page_does_not_reset_current_artist_to_none(self):
        app = QApplication.instance() or QApplication([])
        scan_page = ScanPage()

        scan_page.show_active()

        self.assertNotEqual(scan_page.lbl_current_artist.text(), "Current Artist: None")
        self.assertEqual(scan_page.lbl_current_artist.text(), "")

    def test_scan_progress_updates_home_and_scan_pages(self):
        window = MainWindow.__new__(MainWindow)
        window.scan_page = MagicMock()
        window.dashboard_page = MagicMock()
        progress = ScanProgress(
            processed_artists=4,
            total_artists=312,
            tracks_found=1,
            collaborations_found=0,
            elapsed_time=55,
        )

        MainWindow.on_scan_progress(window, ("progress", progress))

        window.scan_page.update_scan_progress.assert_called_once_with(progress)
        window.dashboard_page.update_scan_progress.assert_called_once_with(progress)

    @patch("ui.main_window.ScanWorker")
    def test_home_started_scan_marks_dashboard_running(self, mock_scan_worker):
        worker = MagicMock()
        worker.signals = SimpleNamespace(
            started=MagicMock(),
            artist_started=MagicMock(),
            artist_scanned=MagicMock(),
            track_discovered=MagicMock(),
            duplicate_prevented=MagicMock(),
            rate_limit=MagicMock(),
            warning=MagicMock(),
            progress=MagicMock(),
            finished=MagicMock(),
            error=MagicMock(),
        )
        mock_scan_worker.return_value = worker
        window = MainWindow.__new__(MainWindow)
        window.scan_origin = "home"
        window.scan_page = MagicMock()
        window.dashboard_page = MagicMock()
        window.service = MagicMock()
        window.thread_pool = MagicMock()
        window.set_app_status = MagicMock()
        config = ScanConfiguration(start_index=1, end_index=10, cutoff_date_str="2026-06-01")

        MainWindow.start_release_scan(window, config)

        window.dashboard_page.show_scan_running.assert_called_once_with(config)
        window.thread_pool.start.assert_called_once_with(worker)

if __name__ == '__main__':
    unittest.main()
