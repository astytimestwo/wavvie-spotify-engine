import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
from pathlib import Path
import re

from core.models import ScanConfiguration, Track
from core.spotify_service import SpotifyReleaseService
from ui.theme import Theme

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
        self.assertEqual(Theme.FONT_BODY, "Futura PT")
        self.assertEqual(Theme.FONT_MONO, "Agrandir")

        forbidden_font_patterns = {
            "Space Grotesk": re.compile(r"\bSpace\s+Grotesk\b", re.IGNORECASE),
            "Inter": re.compile(r"\bInter\b", re.IGNORECASE),
            "JetBrains Mono": re.compile(r"\bJetBrains\s+Mono\b", re.IGNORECASE),
            "Segoe UI": re.compile(r"\bSegoe\s+UI\b", re.IGNORECASE),
            "Arial": re.compile(r"\bArial\b", re.IGNORECASE),
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

    def test_all_explicit_letter_spacing_is_negative_three_px(self):
        searchable_files = list(Path("ui").rglob("*.py"))
        spacing_pattern = re.compile(r"letter-spacing\s*:\s*([^;\"']+)", re.IGNORECASE)

        offenders = []
        for path in searchable_files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in spacing_pattern.finditer(text):
                value = match.group(1).strip()
                if value != "-3px":
                    offenders.append(f"{path}: {value}")

        self.assertEqual(offenders, [])

if __name__ == '__main__':
    unittest.main()
