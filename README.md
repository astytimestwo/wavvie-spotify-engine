# wavvie

wavvie is a desktop and CLI tool for discovering new Spotify releases from followed artists, filtering out noisy compilations, and optionally exporting JSON or creating a private Spotify playlist.

## Features

- **Desktop helper**: a one-window PySide6 app. One button checks the artists you follow for songs released since your last check and saves them to a new, dated private playlist.
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
   - Or start the desktop app: its first run asks for the Client ID and secret and writes `.env` for you.

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

- The first run walks you through connecting a Spotify app: open the dashboard, copy the redirect URI, then paste the Client ID and secret. wavvie writes `.env` for you.
- One button checks every artist you follow and saves new songs to a private playlist named after the dates it covered, such as "wavvie · New releases 10 Oct – 17 Oct".
- wavvie remembers each check. The next check starts on the day the last one ran, skips songs it already saved, and goes back over dates a check couldn't finish. "Change dates" picks a different start for one check.
- Only one Spotify operation runs at a time. Stop ends a check without saving. Closing the window waits for current requests and releases a pending browser sign-in.
- Settings has your account, how far the first check looks back, and advanced options:
  - check only some artists;
  - parallel checks;
  - a JSON copy of each check;
  - reduced motion;
  - refresh your artist list;
  - the activity log (Ctrl+L).

  Ctrl+, opens Settings and Esc closes it.

## Development checks

```bash
python -m unittest discover -s tests -v
python -m compileall -q app.py main.py core ui tests
git diff --check
```

The UI regression suite uses Qt's offscreen platform, bundled fonts, temporary INI preferences, and mocked Spotify responses. It drives the real window through every state, clicks every visible button and checks its effect, tabs through the controls, and checks layouts at 720×560, 900×680 and 1600×1000, including that the header stays over the content column. No account credentials or real playlists are needed. Temporary-file creation and cleanup must be permitted by the execution environment.

Service tests run the real spotipy client against `tests/fake_spotify.py`, an in-memory transport for the Development Mode playlist routes that can refuse, silently cap or accept 50-item pages. Sign-in tests start spotipy's real local redirect server with the browser launch patched out.

Validation on 2026-10-10: **126 tests passed** in three consecutive full runs, plus the layout test at **150% display scaling**. Every window state was also rendered at 900×680 and 720×560 and reviewed by eye, and keyboard focus was checked by tabbing through Home and Settings on the native Windows platform.

Live check on 2026-10-10 with a Development Mode app and the CLI: sign-in, 325 followed artists, a five-artist scan (5 tracks in 22 seconds, 50-item pages accepted), JSON export and one private playlist (5 tracks) all worked. The desktop window and the packaged executable were not run against Spotify; they share the same service code.

See [mindmap.md](mindmap.md) for the implementation map, data flow, Spotify API constraints, and remaining integration boundaries.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
