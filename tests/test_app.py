"""The entry point and the packaged app: where it keeps files, its icon, and what each build bundles."""
import ast
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import app
from ui.resources import ICON_SIZES, app_icon

REPO = Path(__file__).resolve().parents[1]


class PackagedAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_a_packaged_app_keeps_its_files_beside_the_executable(self):
        folder = str(Path(tempfile.gettempdir()) / 'wavvie-download')
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, 'executable', str(Path(folder) / 'wavvie.exe')), \
             patch('os.chdir') as chdir:
            app.use_app_folder()
        chdir.assert_called_once_with(folder)

    def test_running_from_source_keeps_the_current_folder(self):
        with patch('os.chdir') as chdir:
            app.use_app_folder()
        chdir.assert_not_called()

    def test_the_window_icon_has_sharp_sizes_for_every_platform(self):
        icon = app_icon()
        self.assertFalse(icon.isNull())
        self.assertTrue({16, 32, 256} <= {size.width() for size in icon.availableSizes()})

    def test_every_resource_the_app_loads_is_bundled_into_the_build(self):
        spec = (REPO / 'Wavefeed.spec').read_text(encoding='utf-8')
        datas = ast.literal_eval(re.search(r'datas=(\[.*?\])', spec, re.S).group(1))
        bundled = {Path(source).name for source, _ in datas}
        for source, _ in datas:
            self.assertTrue((REPO / source).exists(), source)
        code = '\n'.join(path.read_text(encoding='utf-8') for path in [REPO / 'app.py', *REPO.glob('ui/**/*.py')])
        loaded = set(re.findall(r'resource_path\(["\']([^"\']+)["\']\)', code))
        loaded |= {f'wavvie_mark_{size}.png' for size in ICON_SIZES}
        self.assertEqual(loaded - bundled, set())


class EntryPointTests(unittest.TestCase):
    def test_the_app_starts_shows_its_window_and_quits_in_smoke_test_mode(self):
        # Blank credentials keep it on the setup page: no sign-in, no network.
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', WAVVIE_SMOKE_TEST='1',
                   SPOTIPY_CLIENT_ID='', SPOTIPY_CLIENT_SECRET='')
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, str(REPO / 'app.py')], cwd=folder, env=env,
                                    capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])


if __name__ == '__main__':
    unittest.main()
