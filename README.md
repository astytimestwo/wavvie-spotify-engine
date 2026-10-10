# wavvie

wavvie is a desktop and CLI tool for discovering new Spotify releases from followed artists, filtering out noisy compilations, and optionally exporting JSON or creating a private Spotify playlist.

## Features

- **Desktop dashboard**: PySide6 app with live scan progress, release pulse visualization, results, activity, and settings.
- **Multi-threaded discovery**: Processes followed artists concurrently.
- **Collaboration-aware scanning**: Finds featured/remix/with credits while filtering ghost credits.
- **Smart filtering**: Skips greatest-hits collections, workout mixes, and low-quality compilations.
- **Private playlists**: Creates private Spotify playlists in API-safe batches.
- **Local credentials**: Reads Spotify credentials from `.env`; secrets are not committed.

## Platform Support

- **Windows desktop app**: Supported through the packaged `wavvie.exe` build.
- **Windows CLI**: Supported through `run.bat` or direct Python commands.
- **macOS and Linux CLI**: Supported from source with Python. Install the dependencies, create a `.env`, then run `python main.py`.

## Setup

1. **Spotify API Setup**:
   - Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
   - Create an app to get your `Client ID` and `Client Secret`.
   - Set the Redirect URI to `http://127.0.0.1:8888/callback`.

2. **Environment Variables**:
   - Copy `.env.example` to `.env`.
   - Fill in your `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, and `SPOTIPY_REDIRECT_URI`.

3. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Desktop App

Windows packaged app:

Download `wavvie.exe` from the latest GitHub Release when available.

Run from source:

```bash
python app.py
```

Build a Windows executable:

```bash
python -m PyInstaller --clean --noconfirm Wavefeed.spec
```

The built app appears at `dist/wavvie.exe`. Treat `dist/` as a local build output, not source code for commits.

### CLI / Automator

Cross-platform CLI:

```bash
python main.py --start 1 --end 50 --cutoff 2026-06-01
```

This works on Windows, macOS, and Linux after installing `requirements.txt` and creating a local `.env` file.

Windows helper:

Double-click **`run.bat`**. This will:
- Help you set up your `.env` file if it's missing.
- Ask for your start/end range and cutoff date.
- Run the script automatically.

### Arguments

- `--start`: Start index of your followed artists (default: 1).
- `--end`: End index of your followed artists (default: all).
- `--cutoff`: Only include tracks released after this date (YYYY-MM-DD).
- `--refresh`: Refresh the local followed-artist cache.
- `--verbose`: Enable detailed logging.

## Repository Hygiene

Do not commit `.env`, `.spotifycache`, `followed_artists_cache.json`, `tracklist_*.json`, `build/`, `dist/`, or `__pycache__/`.

## Desktop behavior

- Quick Scan uses your saved date and output preferences for all followed artists. Custom scans let you choose an alphabetical artist range.
- Only one Spotify operation runs at a time. You can navigate while scanning; cancellation waits for current requests to finish.
- Results explain empty scans and unmatched searches. Selection counts, export, and playlist creation use checked tracks visible under the current filters.
- Manual export opens a save dialog. Completed exports and playlists have persistent links on Results. Partial playlist failures show the confirmed count and a link to check Spotify before retrying.
- Settings save automatically, and reduced motion disables the release animation and rotating tips. Ctrl+F opens Results search; Ctrl+L opens Activity.
- Large result sets load in small batches. Artwork loads for visible rows, keeping background work and image caches bounded.

## Development checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q app.py main.py core ui tests
git diff --check
```

The UI regression suite uses Qt's offscreen platform, bundled fonts, temporary INI preferences, and mocked Spotify responses. It covers real widget interactions, worker completion, cancellation, shutdown, settings, outputs, long text, large results, and layouts at 1000×640, 1280×820, and 1600×1000. No account credentials or real playlists are needed. Temporary-file creation and cleanup must be permitted by the execution environment.

Validation on 2026-09-06: **50 tests passed**, plus the layout test at **150% display scaling**. The 1,000-track check produced its first 50 rows in 0.10 seconds and finished loading in 2.33 seconds while yielding between batches. These timings describe the local test machine, not a universal performance guarantee. Live Spotify integration and packaged executable behavior were not revalidated in this UI pass.

See [mindmap.md](mindmap.md) for the implementation map, data flow, and remaining integration boundaries. The legacy web UI prompt is separate from this native desktop implementation.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
