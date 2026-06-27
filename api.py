import asyncio
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import main as playlist_core
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
ARTIST_CACHE_FILE = BASE_DIR / "followed_artists_cache.json"
RUNS_LOG_FILE = BASE_DIR / "runs.json"


class RunRequest(BaseModel):
    start: int = Field(default=1, ge=1)
    end: int = Field(default=9999, ge=1)
    cutoff: str
    verbose: bool = False


@dataclass
class RunState:
    id: str
    config: Dict[str, Any]
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "running"
    tracks_found: int = 0
    duplicates_blocked: int = 0
    artists_processed: int = 0
    total_artists: int = 0
    playlist_url: Optional[str] = None
    error_count: int = 0


RUNS: Dict[str, RunState] = {}

app = FastAPI(title="Wavefeed Spotify Dashboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def resolve_ui_dist(base_dir: Path = BASE_DIR) -> Optional[Path]:
    """Return the built React UI directory when it is available."""
    candidates = [base_dir / "dist"]
    bundle_root = getattr(__import__("sys"), "_MEIPASS", None)
    if bundle_root:
        candidates.insert(0, Path(bundle_root) / "dist")

    for candidate in candidates:
        if (candidate / "index.html").exists():
            return candidate
    return None


def mount_static_ui() -> None:
    ui_dist = resolve_ui_dist()
    if ui_dist is not None:
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")


def serialize_run(run: RunState) -> Dict[str, Any]:
    return {
        "id": run.id,
        "started_at": run.started_at,
        "config": run.config,
        "events": run.events[-500:],
        "status": run.status,
        "tracks_found": run.tracks_found,
        "duplicates_blocked": run.duplicates_blocked,
        "artists_processed": run.artists_processed,
        "total_artists": run.total_artists,
        "playlist_url": run.playlist_url,
        "error_count": run.error_count,
    }


def emit(run: RunState, event: Dict[str, Any]) -> None:
    event = {"run_id": run.id, **event}
    run.events.append(event)
    run.loop.call_soon_threadsafe(run.queue.put_nowait, event)


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    if name != filename or not name.startswith("tracklist_") or not name.endswith(".json"):
        raise ValueError("Invalid tracklist filename")
    return name


def list_tracklist_files(base_dir: Path = BASE_DIR) -> List[Dict[str, Any]]:
    files = []
    for path in sorted(base_dir.glob("tracklist_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        metadata = {}
        try:
            metadata = json.loads(path.read_text(encoding="utf-8")).get("metadata", {})
        except Exception:
            metadata = {"error": "Could not read metadata"}
        files.append(
            {
                "filename": path.name,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                "size": path.stat().st_size,
                "metadata": metadata,
            }
        )
    return files


def load_tracklist_file(filename: str, base_dir: Path = BASE_DIR) -> List[Dict[str, Any]]:
    path = base_dir / safe_filename(filename)
    if not path.exists():
        raise FileNotFoundError(filename)
    data = json.loads(path.read_text(encoding="utf-8"))
    tracks = data.get("tracks", [])
    if not isinstance(tracks, list):
        raise ValueError("Tracklist does not contain a tracks array")
    return tracks


def append_run_log(entry: Dict[str, Any]) -> None:
    existing = []
    if RUNS_LOG_FILE.exists():
        try:
            existing = json.loads(RUNS_LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.insert(0, entry)
    RUNS_LOG_FILE.write_text(json.dumps(existing[:50], indent=2), encoding="utf-8")


def read_run_log() -> List[Dict[str, Any]]:
    if not RUNS_LOG_FILE.exists():
        return []
    try:
        data = json.loads(RUNS_LOG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def playlist_artwork_preview(tracks: List[Dict[str, Any]]) -> List[str]:
    urls = []
    seen = set()
    for track in tracks:
        url = track.get("album_artwork_url")
        if url and url not in seen:
            urls.append(url)
            seen.add(url)
        if len(urls) == 8:
            break
    return urls


def run_pipeline(run: RunState) -> None:
    all_tracks = []
    global_seen: Dict[str, Dict[str, Any]] = {}

    try:
        cutoff_date = datetime.strptime(run.config["cutoff"], "%Y-%m-%d")
        spotify = playlist_core.get_spotify_client()
        followed_artists = playlist_core.get_and_cache_followed_artists(spotify)

        if run.config["start"] > len(followed_artists):
            raise ValueError(f"Start index {run.config['start']} is greater than total artists ({len(followed_artists)})")

        actual_end = min(run.config["end"], len(followed_artists))
        artists_to_process = followed_artists[run.config["start"] - 1:actual_end]
        run.total_artists = len(artists_to_process)
        emit(run, {"type": "start", "total_artists": run.total_artists})

        for offset, artist in enumerate(artists_to_process, start=run.config["start"]):
            artist_name = artist.get("name", "Unknown Artist")
            emit(run, {"type": "artist", "index": offset, "name": artist_name, "status": "processing"})

            try:
                new_tracks = playlist_core.get_new_tracks(spotify, artist["id"], artist_name, cutoff_date)
            except Exception as exc:
                run.error_count += 1
                emit(run, {"type": "error", "message": f"{artist_name}: {exc}"})
                new_tracks = []

            found_for_artist = 0
            for track in new_tracks:
                signature = track["track_signature"]
                if signature in global_seen:
                    run.duplicates_blocked += 1
                    emit(
                        run,
                        {
                            "type": "duplicate",
                            "track_name": track.get("track_name", "Unknown Track"),
                            "skipped_from": global_seen[signature].get("artist_name", "Unknown Artist"),
                        },
                    )
                    continue

                global_seen[signature] = track
                all_tracks.append(track)
                found_for_artist += 1
                run.tracks_found += 1
                emit(
                    run,
                    {
                        "type": "track",
                        "artist": artist_name,
                        "track_name": track.get("track_name", "Unknown Track"),
                        "album_type": track.get("album_type", "unknown"),
                        "performer_role": track.get("performer_role", "unknown"),
                        "is_collaboration": track.get("is_collaboration", False),
                    },
                )

            run.artists_processed += 1
            emit(run, {"type": "artist_done", "index": offset, "name": artist_name, "tracks_found": found_for_artist})

        all_tracks.sort(key=lambda item: item.get("release_date", ""), reverse=True)
        tracklist_name = f"tracklist_{run.config['start']}_{actual_end}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        playlist_core.dump_tracklist_to_json(all_tracks, str(BASE_DIR / tracklist_name))
        playlist = playlist_core.create_playlist_with_tracks(spotify, all_tracks, run.config["start"], actual_end)

        playlist_url = None
        playlist_name = None
        if playlist:
            playlist_url = playlist.get("external_urls", {}).get("spotify")
            playlist_name = playlist.get("name")
        run.playlist_url = playlist_url
        run.status = "done"
        append_run_log(
            {
                "run_id": run.id,
                "created_at": datetime.now().isoformat(),
                "playlist_name": playlist_name or "New Releases",
                "playlist_url": playlist_url,
                "artist_range": [run.config["start"], actual_end],
                "track_count": len(all_tracks),
                "duplicates_blocked": run.duplicates_blocked,
                "tracklist": tracklist_name,
                "artwork": playlist_artwork_preview(all_tracks),
            }
        )
        emit(
            run,
            {
                "type": "done",
                "total_tracks": len(all_tracks),
                "duplicates_prevented": run.duplicates_blocked,
                "playlist_url": playlist_url,
                "tracklist": tracklist_name,
            },
        )
    except Exception as exc:
        run.status = "error"
        run.error_count += 1
        emit(run, {"type": "error", "message": str(exc)})
        run.loop.call_soon_threadsafe(run.queue.put_nowait, None)


@app.get("/api/status")
def status():
    try:
        spotify = playlist_core.get_spotify_client()
        current_user = spotify.current_user()
        return {"authenticated": True, "user": current_user}
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@app.get("/api/artists")
def artists():
    try:
        cached = ARTIST_CACHE_FILE.exists()
        spotify = playlist_core.get_spotify_client()
        raw_artists = playlist_core.get_and_cache_followed_artists(spotify, str(ARTIST_CACHE_FILE))
        return {
            "cached": cached,
            "artists": [
                {
                    "id": artist.get("id"),
                    "name": artist.get("name"),
                    "images": artist.get("images", []),
                    "followers": artist.get("followers", {"total": 0}),
                }
                for artist in raw_artists
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/artists/cache")
def clear_artist_cache():
    if ARTIST_CACHE_FILE.exists():
        ARTIST_CACHE_FILE.unlink()
    return {"cleared": True}


@app.post("/api/run")
async def start_run(request: RunRequest):
    run_id = uuid.uuid4().hex[:12]
    run = RunState(
        id=run_id,
        config={"start": request.start, "end": request.end, "cutoff": request.cutoff, "verbose": request.verbose},
        loop=asyncio.get_running_loop(),
    )
    RUNS[run_id] = run
    thread = threading.Thread(target=run_pipeline, args=(run,), daemon=True)
    thread.start()
    return serialize_run(run)


@app.get("/api/runs/{run_id}")
async def stream_run(run_id: str):
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_stream():
        for event in run.events:
            yield f"data: {json.dumps(event)}\n\n"

        while run.status == "running":
            event = await run.queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

        for event in run.events:
            if event.get("type") in {"done", "error"}:
                yield f"data: {json.dumps(event)}\n\n"
                break

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/runs/{run_id}/state")
def run_state(run_id: str):
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return serialize_run(run)


@app.get("/api/tracklists")
def tracklists():
    return {"tracklists": list_tracklist_files()}


@app.get("/api/tracklists/{filename}")
def tracklist(filename: str):
    try:
        return {"tracks": load_tracklist_file(filename)}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Tracklist not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/playlists")
def playlists():
    return {"playlists": read_run_log()}


mount_static_ui()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=False)
