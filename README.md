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
   - New Spotify apps run in Development Mode. Since February 2026 the app owner needs Spotify Premium and at most five users can use the app. Spotify also documents a maximum of 10 search results or artist albums per page for these apps; wavvie asks for 50 and switches to 10 if Spotify refuses.

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
- `--cutoff`: Only include tracks released on or after this date (YYYY-MM-DD, default: 30 days ago).
- `--refresh`: Refresh the local followed-artist cache.
- `--verbose`: Enable detailed logging.

## Repository Hygiene

Do not commit `.env`, `.spotifycache`, `followed_artists_cache.json`, `tracklist_*.json`, `build/`, `dist/`, or `__pycache__/`.

## Desktop behavior

- Quick Scan uses your saved date and output preferences for all followed artists. Custom scans let you choose an alphabetical artist range.
- Only one Spotify operation runs at a time. You can navigate while scanning; cancellation waits for current requests to finish.
- While connecting, **Cancel sign-in** stops waiting for the browser (for example after closing the tab or seeing a redirect URI error). Closing the window does the same.
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

Service tests run the real spotipy client against `tests/fake_spotify.py`, an in-memory transport for the Development Mode playlist routes that can refuse, silently cap or accept 50-item pages. Sign-in tests start spotipy's real local redirect server with the browser launch patched out.

Validation on 2026-10-10: **77 tests passed** in three consecutive full runs, plus the layout test at **150% display scaling**. The 1,000-track check showed its first 50 rows in 0.18–0.46 seconds and finished loading in 3.6–7.6 seconds; that test's 8-second limit can be exceeded when the machine is busy. Most of that time is spent building row widgets.

Live check on 2026-10-10 with a Development Mode app and the CLI: sign-in, 325 followed artists, a five-artist scan (5 tracks in 22 seconds, 50-item pages accepted), JSON export and one private playlist (5 tracks) all worked. The desktop window and the packaged executable were not run against Spotify; they share the same service code.

See [mindmap.md](mindmap.md) for the implementation map, data flow, Spotify API constraints, and remaining integration boundaries.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
