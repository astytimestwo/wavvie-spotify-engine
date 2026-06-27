import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class MainImportContractTests(unittest.TestCase):
    def test_importing_main_does_not_create_spotify_client(self):
        sys.modules.pop("main", None)

        with patch("spotipy.Spotify", side_effect=AssertionError("Spotify client should be lazy")):
            importlib.import_module("main")

    def test_dotenv_search_paths_include_exe_parent(self):
        main = importlib.import_module("main")

        paths = main.dotenv_search_paths(
            base_dir=Path("C:/app/bundle"),
            cwd=Path("C:/project/release"),
            executable_path=Path("C:/project/release/Wavefeed.exe"),
        )

        self.assertIn(Path("C:/project/release/.env"), paths)
        self.assertIn(Path("C:/project/.env"), paths)


class TracklistContractTests(unittest.TestCase):
    def test_tracklist_file_returns_tracks_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tracklist = root / "tracklist_1_2_20260625_101010.json"
            tracklist.write_text(
                json.dumps(
                    {
                        "metadata": {"total_tracks": 1},
                        "tracks": [
                            {
                                "track_id": "abc",
                                "track_name": "Pulse",
                                "artist_name": "Nova",
                                "release_date": "2026-06-01",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            api = importlib.import_module("api")
            self.assertEqual(
                api.load_tracklist_file("tracklist_1_2_20260625_101010.json", base_dir=root),
                [
                    {
                        "track_id": "abc",
                        "track_name": "Pulse",
                        "artist_name": "Nova",
                        "release_date": "2026-06-01",
                    }
                ],
            )

    def test_tracklist_loader_rejects_path_traversal(self):
        api = importlib.import_module("api")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                api.load_tracklist_file("../secret.json", base_dir=Path(tmp))


class StaticUiContractTests(unittest.TestCase):
    def test_resolve_ui_dist_prefers_existing_dist_folder(self):
        api = importlib.import_module("api")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("<div>Wavefeed</div>", encoding="utf-8")

            self.assertEqual(api.resolve_ui_dist(root), dist)

    def test_resolve_ui_dist_returns_none_without_index(self):
        api = importlib.import_module("api")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dist").mkdir()

            self.assertIsNone(api.resolve_ui_dist(root))


class LauncherContractTests(unittest.TestCase):
    def test_launcher_can_disable_browser_for_packaged_smoke_tests(self):
        launcher = importlib.import_module("launcher")

        with patch.dict(os.environ, {"WAVEFEED_NO_BROWSER": "1"}):
            self.assertFalse(launcher.should_open_browser())

        with patch.dict(os.environ, {"WAVEFEED_NO_BROWSER": "0"}):
            self.assertTrue(launcher.should_open_browser())


if __name__ == "__main__":
    unittest.main()
