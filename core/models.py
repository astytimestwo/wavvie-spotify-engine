from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class Artist:
    id: str
    name: str
    images: List[Dict[str, any]] = field(default_factory=list)
    followers: Optional[int] = None

@dataclass
class Album:
    id: str
    name: str
    album_type: str
    release_date: str
    images: List[Dict[str, any]] = field(default_factory=list)
    artists: List[Dict[str, any]] = field(default_factory=list)

@dataclass
class Track:
    track_id: str
    track_name: str
    album_name: str
    album_id: str
    album_type: str
    release_date: str
    artist_name: str
    followed_artist_id: str
    is_collaboration: bool
    performer_role: str  # 'main' or 'featured'
    all_artists: List[str]
    track_signature: str
    album_artwork_url: Optional[str] = None
    main_artist: Optional[str] = None

@dataclass
class ScanConfiguration:
    start_index: int = 1
    end_index: int = 9999
    cutoff_date_str: str = ""
    playlist_name: str = "New Releases"
    playlist_description: str = "New tracks from followed artists"
    worker_count: int = 5
    export_json: bool = True
    create_playlist_auto: bool = True
    refresh_cache: bool = False

@dataclass
class ScanProgress:
    processed_artists: int = 0
    total_artists: int = 0
    current_artist_name: str = ""
    current_artist_image_url: Optional[str] = None
    tracks_found: int = 0
    collaborations_found: int = 0
    albums_checked: int = 0
    elapsed_time: float = 0.0
    status: str = "Idle"

@dataclass
class ScanResult:
    tracks: List[Track] = field(default_factory=list)
    duplicates_prevented: int = 0
    total_artists: int = 0
    total_tracks: int = 0

@dataclass
class PlaylistResult:
    playlist_name: str
    playlist_id: str
    playlist_url: str
    tracks_added: int
    json_path: Optional[str] = None
