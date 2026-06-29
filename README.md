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

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
