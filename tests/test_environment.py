"""Saving Spotify credentials from the setup screen."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dotenv import dotenv_values

import main


class SaveEnvironmentTests(unittest.TestCase):
    def test_saved_credentials_are_written_quoted_kept_beside_other_values_and_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text("OTHER='kept'\n")
            with patch.dict(os.environ, {}, clear=True), \
                 patch.object(main, '_loaded_environment', {}), \
                 patch.object(main, 'dotenv_search_paths', return_value=[str(path)]):
                written = main.save_environment({'SPOTIPY_CLIENT_ID': 'abc123', 'SPOTIPY_CLIENT_SECRET': "s'cret"})
                self.assertEqual(os.environ['SPOTIPY_CLIENT_SECRET'], "s'cret")
                self.assertEqual(os.environ['OTHER'], 'kept')
            self.assertEqual(written, str(path))
            self.assertEqual(dict(dotenv_values(path)),
                             {'OTHER': 'kept', 'SPOTIPY_CLIENT_ID': 'abc123', 'SPOTIPY_CLIENT_SECRET': "s'cret"})


if __name__ == '__main__':
    unittest.main()
