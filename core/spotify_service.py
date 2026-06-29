import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from datetime import datetime, timedelta
import time
import logging
import json
import os
import sys
from typing import List, Dict, Callable, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.models import Artist, Album, Track, ScanConfiguration, ScanProgress, ScanResult, PlaylistResult

logger = logging.getLogger(__name__)

class SpotifyReleaseService:
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None, 
                 redirect_uri: str = 'http://127.0.0.1:8888/callback', cache_path: str = ".spotifycache"):
        self.client_id = client_id or os.getenv('SPOTIPY_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('SPOTIPY_CLIENT_SECRET')
        self.redirect_uri = redirect_uri or os.getenv('SPOTIPY_REDIRECT_URI', 'http://127.0.0.1:8888/callback')
        self.cache_path = cache_path
        
        self.sp: Optional[spotipy.Spotify] = None
        self.user_data: Optional[Dict[str, Any]] = None
        self.cancelled = False
        
        # Configuration defaults
        self.max_retries = 3
        self.sleep_between_requests = 1.2
        self.max_tracks_per_batch = 100
        
        # Callbacks registration
        self.callbacks: Dict[str, Callable[..., None]] = {}

    def register_callback(self, event_name: str, callback: Callable[..., None]):
        self.callbacks[event_name] = callback

    def trigger_callback(self, event_name: str, *args, **kwargs):
        if event_name in self.callbacks:
            try:
                self.callbacks[event_name](*args, **kwargs)
            except Exception as e:
                logger.error(f"Error executing callback '{event_name}': {e}")

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def authenticate(self) -> bool:
        self.trigger_callback("auth_started")
        if not self.is_configured():
            self.trigger_callback("auth_failed", "Spotify Client ID or Client Secret not configured.")
            return False
            
        try:
            auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope='user-follow-read playlist-modify-private',
                cache_path=self.cache_path
            )
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
            self.user_data = self.sp.current_user()
            self.trigger_callback("auth_success", self.user_data)
            return True
        except Exception as e:
            self.trigger_callback("auth_failed", str(e))
            return False

    def disconnect(self):
        self.sp = None
        self.user_data = None
        if os.path.exists(self.cache_path):
            try:
                os.remove(self.cache_path)
            except Exception as e:
                logger.warning(f"Could not delete cache file: {e}")

    def safe_api_call(self, func, *args, **kwargs):
        """Wrapper for API calls with proper error handling and rate limiting."""
        for attempt in range(self.max_retries):
            if self.cancelled:
                raise InterruptedError("Operation cancelled by user.")
                
            try:
                result = func(*args, **kwargs)
                time.sleep(self.sleep_between_requests)
                return result
            except SpotifyException as e:
                if e.http_status == 429:
                    retry_after = int(e.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limit hit. Waiting {retry_after} seconds...")
                    self.trigger_callback("rate_limit_encountered", retry_after)
                    
                    # Wake up periodically to check for cancellation
                    sleep_end = time.time() + retry_after
                    while time.time() < sleep_end:
                        if self.cancelled:
                            raise InterruptedError("Operation cancelled by user.")
                        time.sleep(1)
                    continue
                elif e.http_status >= 500:
                    wait_time = (2 ** attempt) * 2
                    logger.warning(f"Server error {e.http_status}. Retrying in {wait_time}s... (attempt {attempt + 1})")
                    self.trigger_callback("warning", f"Spotify Server Error {e.http_status}. Retrying...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"API error: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
        
        raise Exception(f"Max retries ({self.max_retries}) exceeded")

    def parse_release_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            if len(date_str) == 4:
                return datetime.strptime(date_str, "%Y")
            elif len(date_str) == 7:
                return datetime.strptime(date_str, "%Y-%m")
            else:
                return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"Invalid date format: {date_str}")
            return None

    def create_track_signature(self, track_name: str, all_artists: List[str]) -> str:
        return f"{track_name.lower()}|{'|'.join(sorted([a.lower() for a in all_artists]))}"

    def get_followed_artists(self) -> List[Dict[str, Any]]:
        artists = []
        after = None
        
        while True:
            if self.cancelled:
                break
            try:
                results = self.safe_api_call(self.sp.current_user_followed_artists, limit=50, after=after)
                if not results or 'artists' not in results or not results['artists']['items']:
                    break
                
                items = results['artists']['items']
                artists.extend(items)
                logger.info(f"Fetched {len(artists)} artists so far...")
                
                if not results['artists']['next']:
                    break
                after = items[-1]['id']
                
            except Exception as e:
                logger.error(f"Error fetching artists: {e}")
                self.trigger_callback("warning", f"Failed to fetch some followed artists: {e}")
                break
        
        return artists

    def get_and_cache_followed_artists(self, cache_file: str = "followed_artists_cache.json", refresh: bool = False) -> List[Dict[str, Any]]:
        if not refresh and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    logger.info(f"Loaded {len(cached_data)} artists from cache")
                    self.trigger_callback("artists_loaded", cached_data)
                    return cached_data
            except Exception as e:
                logger.warning(f"Cache file corrupted ({e}), fetching fresh data")
                self.trigger_callback("warning", "Cache file corrupted, fetching fresh followed artists.")
        
        artists = self.get_followed_artists()
        artists.sort(key=lambda x: x.get('name', '').lower())
        logger.info(f"Sorted {len(artists)} artists alphabetically")
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(artists, f, indent=2, ensure_ascii=False)
            logger.info(f"Cached {len(artists)} artists for future runs")
        except Exception as e:
            logger.warning(f"Could not cache artists: {e}")
            
        self.trigger_callback("artists_loaded", artists)
        return artists

    def clear_artists_cache(self, cache_file: str = "followed_artists_cache.json"):
        if os.path.exists(cache_file):
            try:
                os.remove(cache_file)
                logger.info("Cleared followed artists cache file")
            except Exception as e:
                logger.error(f"Failed to clear cache: {e}")
                raise

    def is_actual_performer(self, track_artists: List[Dict[str, Any]], followed_artist_id: str) -> bool:
        performer_ids = [a.get('id') for a in track_artists if a.get('id')]
        return followed_artist_id in performer_ids

    def prioritize_album_version(self, track_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(track_data_list) == 1:
            return track_data_list[0]
        
        priority_map = {
            'album': 1,
            'single': 2,
            'ep': 3,
            'compilation': 4,
            'unknown': 5
        }
        
        sorted_tracks = sorted(track_data_list, key=lambda x: (
            priority_map.get(x.get('album_type', 'unknown').lower(), 5),
            x.get('release_date', '9999-99-99')
        ))
        
        return sorted_tracks[0]

    def is_trashy_compilation(self, album_info: Dict[str, Any]) -> bool:
        album_type = album_info.get('album_type', '').lower()
        album_name = album_info.get('name', '').lower()
        
        skip_keywords = [
            'greatest hits', 'best of', 'hits collection', 'anthology',
            'internacionais', 'treino', 'musicas internacionais', 'malhar',
            'as melhores', 'as mais tocadas', 'melhores mÃºsicas',
            'workout', 'gym', 'fitness', 'running', 'cardio',
            'top hits', 'chart hits', 'pop hits', 'radio hits',
            'ultimate collection', 'essential', 'platinum collection',
            'gold collection', 'mega hits', 'super hits', 'hit parade',
            'para gostosas', 'para malhar', 'para treinar',
            'compilation', 'coletÃ¢nea', 'various artists'
        ]
        
        if album_type == 'compilation':
            return True
            
        if any(keyword in album_name for keyword in skip_keywords):
            return True
            
        return False

    def should_include_album_type(self, album_type: str) -> bool:
        return album_type.lower() in ['album', 'single', 'ep', 'appears_on']

    def get_album_tracks(self, album_id: str, album_info: Dict[str, Any], followed_artist_id: str) -> List[Dict[str, Any]]:
        tracks = []
        offset = 0
        album_images = album_info.get('images', [])
        album_artwork_url = album_images[0].get('url') if album_images else None
        
        while True:
            if self.cancelled:
                break
            try:
                result = self.safe_api_call(self.sp.album_tracks, album_id, limit=50, offset=offset)
                if not result:
                    break
                
                items = result.get('items', [])
                if not items:
                    break
                
                for track in items:
                    track_artists = track.get('artists', [])
                    if not self.is_actual_performer(track_artists, followed_artist_id):
                        continue
                    
                    if track.get('id'):
                        album_main_artists = album_info.get('artists', [])
                        is_followed_main_artist = any(a.get('id') == followed_artist_id for a in album_main_artists)
                        all_artists = [a.get('name', 'Unknown') for a in track_artists]
                        
                        tracks.append({
                            'track_id': track['id'],
                            'track_name': track.get('name', 'Unknown Track'),
                            'album_name': album_info.get('name', 'Unknown Album'),
                            'album_id': album_id,
                            'album_type': album_info.get('album_type', 'unknown'),
                            'album_artwork_url': album_artwork_url,
                            'release_date': album_info.get('release_date'),
                            'artist_name': album_info.get('artists', [{}])[0].get('name', 'Unknown Artist'),
                            'followed_artist_id': followed_artist_id,
                            'is_collaboration': not is_followed_main_artist,
                            'performer_role': 'main' if is_followed_main_artist else 'featured',
                            'all_artists': all_artists,
                            'track_signature': self.create_track_signature(track.get('name', 'Unknown Track'), all_artists)
                        })
                
                offset += 50
                if len(items) < 50:
                    break
                    
            except Exception as e:
                logger.warning(f"Error fetching tracks for album {album_info.get('name', 'Unknown')}: {e}")
                self.trigger_callback("warning", f"Could not fetch tracks for album '{album_info.get('name')}': {e}")
                break
        
        return tracks

    def get_artist_albums_robust(self, artist_id: str, artist_name: str, cutoff_date: datetime) -> List[Dict[str, Any]]:
        all_albums = []
        offset = 0
        consecutive_empty_pages = 0
        max_consecutive_empty = 3
        
        while consecutive_empty_pages < max_consecutive_empty:
            if self.cancelled:
                break
            try:
                result = self.safe_api_call(self.sp.artist_albums, artist_id, limit=50, offset=offset)
                
                if not result or not result.get('items'):
                    consecutive_empty_pages += 1
                    offset += 50
                    continue
                
                items = result['items']
                page_albums = []
                
                for album in items:
                    album_type = album.get('album_type', 'unknown').lower()
                    if not self.should_include_album_type(album_type):
                        continue
                    if self.is_trashy_compilation(album):
                        continue
                    if not album.get('release_date'):
                        continue
                        
                    release_date = self.parse_release_date(album['release_date'])
                    if not release_date or release_date < cutoff_date:
                        continue
                    
                    page_albums.append(album)
                
                if page_albums:
                    all_albums.extend(page_albums)
                    consecutive_empty_pages = 0
                else:
                    consecutive_empty_pages += 1
                
                if len(items) < 50:
                    break
                offset += 50
                
            except Exception as e:
                logger.error(f"Error fetching albums at offset {offset} for {artist_name}: {e}")
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= max_consecutive_empty:
                    break
                offset += 50
                continue
        
        return all_albums

    def get_artist_collaborations(self, artist_id: str, artist_name: str, cutoff_date: datetime) -> List[Dict[str, Any]]:
        collab_tracks = []
        seen_signatures = set()
        
        try:
            search_queries = [
                f'feat "{artist_name}"',
                f'featuring "{artist_name}"',
                f'ft "{artist_name}"',
                f'with "{artist_name}"',
                f'"{artist_name}" remix',
                f'"{artist_name}" mix'
            ]
            
            for query in search_queries:
                if self.cancelled:
                    break
                offset = 0
                while offset < 200:
                    if self.cancelled:
                        break
                    try:
                        result = self.safe_api_call(self.sp.search, q=query, type='track', limit=50, offset=offset)
                        if not result or not result.get('tracks'):
                            break
                        
                        tracks = result['tracks'].get('items', [])
                        if not tracks:
                            break
                        
                        for track in tracks:
                            album = track.get('album', {})
                            if self.is_trashy_compilation(album):
                                continue
                            
                            release_date = self.parse_release_date(album.get('release_date'))
                            if not release_date or release_date < cutoff_date:
                                continue
                            
                            track_artists = track.get('artists', [])
                            if not self.is_actual_performer(track_artists, artist_id):
                                continue
                            
                            track_name = track.get('name', '').lower()
                            valid_collab = any(k in track_name for k in ['feat', 'featuring', 'ft', 'with', 'remix', 'mix'])
                            if not valid_collab:
                                continue
                            
                            album_artists = album.get('artists', [])
                            is_main_artist = any(a.get('id') == artist_id for a in album_artists)
                            
                            if not is_main_artist and track.get('id'):
                                main_artist_name = album_artists[0].get('name', 'Unknown') if album_artists else 'Unknown'
                                if main_artist_name.lower() == artist_name.lower():
                                    continue
                                
                                all_artists = [a.get('name', 'Unknown') for a in track_artists]
                                track_signature = self.create_track_signature(track.get('name', 'Unknown Track'), all_artists)
                                
                                if track_signature in seen_signatures:
                                    continue
                                
                                album_images = album.get('images', [])
                                album_artwork_url = album_images[0].get('url') if album_images else None
                                
                                seen_signatures.add(track_signature)
                                collab_tracks.append({
                                    'track_id': track['id'],
                                    'track_name': track.get('name', 'Unknown Track'),
                                    'album_name': album.get('name', 'Unknown Album'),
                                    'album_id': album.get('id'),
                                    'album_type': album.get('album_type', 'unknown'),
                                    'album_artwork_url': album_artwork_url,
                                    'release_date': album.get('release_date'),
                                    'artist_name': artist_name,
                                    'followed_artist_id': artist_id,
                                    'main_artist': main_artist_name,
                                    'is_collaboration': True,
                                    'performer_role': 'featured',
                                    'all_artists': all_artists,
                                    'track_signature': track_signature
                                })
                        
                        offset += 50
                        if len(tracks) < 50:
                            break
                    except Exception as e:
                        logger.warning(f"Error in collab search: {e}")
                        break
        except Exception as e:
            logger.error(f"Error searching collaborations for {artist_name}: {e}")
            
        return collab_tracks

    def get_new_tracks(self, artist_id: str, artist_name: str, cutoff_date: datetime) -> List[Dict[str, Any]]:
        all_tracks = []
        track_versions = {}
        
        try:
            albums = self.get_artist_albums_robust(artist_id, artist_name, cutoff_date)
            for album in albums:
                if self.cancelled:
                    break
                album_tracks = self.get_album_tracks(album['id'], album, artist_id)
                for track in album_tracks:
                    sig = track['track_signature']
                    if sig not in track_versions:
                        track_versions[sig] = []
                    track_versions[sig].append(track)
        except Exception as e:
            logger.error(f"Error fetching albums for artist {artist_name}: {e}")
            self.trigger_callback("warning", f"Could not scan albums for {artist_name}: {e}")
            
        for sig, versions in track_versions.items():
            best = self.prioritize_album_version(versions)
            all_tracks.append(best)
            
        collabs = self.get_artist_collaborations(artist_id, artist_name, cutoff_date)
        collab_count = 0
        for track in collabs:
            sig = track['track_signature']
            if sig not in track_versions:
                all_tracks.append(track)
                collab_count += 1
                
        logger.info(f"Found {len(all_tracks)} unique tracks for {artist_name} ({collab_count} collaborations)")
        return all_tracks

    def scan_releases(self, config: ScanConfiguration) -> Optional[ScanResult]:
        self.cancelled = False
        self.trigger_callback("scan_started")
        
        if self.sp is None:
            if not self.authenticate():
                self.trigger_callback("fatal_error", "Not authenticated with Spotify.")
                return None
                
        try:
            cutoff_date = datetime.strptime(config.cutoff_date_str, '%Y-%m-%d')
        except ValueError:
            self.trigger_callback("fatal_error", f"Invalid cutoff date: {config.cutoff_date_str}")
            return None
            
        try:
            followed_artists = self.get_and_cache_followed_artists(refresh=config.refresh_cache)
            total_artists = len(followed_artists)
            
            if config.start_index > total_artists:
                self.trigger_callback("fatal_error", f"Start index {config.start_index} exceeds total artists ({total_artists})")
                return None
                
            actual_end = min(config.end_index, total_artists)
            artists_to_process = followed_artists[config.start_index - 1:actual_end]
            
            self.trigger_callback("scan_init_complete", len(artists_to_process), total_artists)
            
            all_tracks: List[Track] = []
            global_seen = {}
            processed_count = 0
            collaborations_count = 0
            
            start_time = time.time()
            
            def process_artist(artist_info):
                idx, artist = artist_info
                actual_idx = config.start_index + idx
                artist_name = artist.get('name', 'Unknown')
                artist_id = artist['id']
                artist_images = artist.get('images', [])
                artist_image = artist_images[0]['url'] if artist_images else None
                
                self.trigger_callback("artist_scanning_started", actual_idx, artist_name, artist_image)
                
                try:
                    tracks = self.get_new_tracks(artist_id, artist_name, cutoff_date)
                    self.trigger_callback("artist_scanning_completed", actual_idx, artist_name, len(tracks))
                    return tracks
                except Exception as e:
                    logger.error(f"Error scanning {artist_name}: {e}")
                    self.trigger_callback("warning", f"Error scanning {artist_name}: {e}")
                    return []

            # Concurrency pool
            with ThreadPoolExecutor(max_workers=config.worker_count) as executor:
                futures = {executor.submit(process_artist, (i, artist)): artist for i, artist in enumerate(artists_to_process)}
                
                for future in as_completed(futures):
                    if self.cancelled:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                        
                    artist = futures[future]
                    try:
                        new_tracks_raw = future.result()
                        processed_count += 1
                        
                        for track_raw in new_tracks_raw:
                            sig = track_raw['track_signature']
                            track = Track(
                                track_id=track_raw['track_id'],
                                track_name=track_raw['track_name'],
                                album_name=track_raw['album_name'],
                                album_id=track_raw['album_id'],
                                album_type=track_raw['album_type'],
                                release_date=track_raw['release_date'],
                                artist_name=track_raw['artist_name'],
                                followed_artist_id=track_raw['followed_artist_id'],
                                is_collaboration=track_raw['is_collaboration'],
                                performer_role=track_raw['performer_role'],
                                all_artists=track_raw['all_artists'],
                                track_signature=sig,
                                album_artwork_url=track_raw.get('album_artwork_url'),
                                main_artist=track_raw.get('main_artist')
                            )
                            
                            if sig not in global_seen:
                                global_seen[sig] = track
                                all_tracks.append(track)
                                if track.is_collaboration:
                                    collaborations_count += 1
                                    
                                self.trigger_callback("track_discovered", track)
                            else:
                                self.trigger_callback("duplicate_prevented", track.track_name, global_seen[sig].artist_name)
                                
                        # Trigger progress update
                        elapsed = time.time() - start_time
                        progress = ScanProgress(
                            processed_artists=processed_count,
                            total_artists=len(artists_to_process),
                            current_artist_name=artist.get('name', 'Unknown'),
                            current_artist_image_url=artist.get('images', [{}])[0].get('url') if artist.get('images') else None,
                            tracks_found=len(all_tracks),
                            collaborations_found=collaborations_count,
                            elapsed_time=elapsed,
                            status="Scanning..."
                        )
                        self.trigger_callback("progress_changed", progress)
                        
                    except Exception as e:
                        logger.error(f"Future execution error: {e}")
                        self.trigger_callback("warning", f"A processing worker failed: {e}")
            
            if self.cancelled:
                self.trigger_callback("scan_cancelled")
                return None
                
            # Sort tracks by release date (newest first)
            all_tracks.sort(key=lambda x: x.release_date, reverse=True)
            
            # Prepare result
            duplicates_count = len(global_seen) - len(all_tracks)
            result = ScanResult(
                tracks=all_tracks,
                duplicates_prevented=duplicates_count,
                total_artists=len(artists_to_process),
                total_tracks=len(all_tracks),
                start_index=config.start_index,
                end_index=actual_end
            )
            
            self.trigger_callback("scan_completed", result)
            return result
            
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            self.trigger_callback("fatal_error", f"Scan process encountered a fatal error: {e}")
            return None

    def dump_tracklist_to_json(self, tracks: List[Track], start_index: int, end_index: int) -> Optional[str]:
        try:
            clean_tracks = []
            missing_artwork = 0
            for t in tracks:
                if not t.album_artwork_url:
                    missing_artwork += 1
                clean_tracks.append({
                    'track_id': t.track_id,
                    'track_name': t.track_name,
                    'album_name': t.album_name,
                    'album_type': t.album_type,
                    'release_date': t.release_date,
                    'artist_name': t.artist_name,
                    'performer_role': t.performer_role,
                    'is_collaboration': t.is_collaboration,
                    'all_artists': t.all_artists,
                    'main_artist': t.main_artist,
                    'has_artwork': bool(t.album_artwork_url),
                    'track_signature': t.track_signature
                })
            
            filename = f"tracklist_{start_index}_{end_index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            export_data = {
                'metadata': {
                    'total_tracks': len(tracks),
                    'missing_artwork': missing_artwork,
                    'export_timestamp': datetime.now().isoformat()
                },
                'tracks': clean_tracks
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Tracklist exported to {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to export tracklist to JSON: {e}")
            self.trigger_callback("warning", f"Failed to export tracklist: {e}")
            return None

    def create_playlist(self, tracks: List[Track], config: ScanConfiguration, start_index: int, end_index: int) -> Optional[PlaylistResult]:
        self.trigger_callback("playlist_started")
        if not tracks:
            self.trigger_callback("warning", "No tracks to add to playlist.")
            return None
            
        try:
            range_suffix = f" (Artists {start_index}-{end_index})" if start_index != 1 or end_index != 9999 else ""
            playlist_name = config.playlist_name + range_suffix
            
            user_id = self.user_data['id'] if self.user_data else self.sp.current_user()['id']
            
            playlist = self.safe_api_call(
                self.sp.user_playlist_create,
                user=user_id,
                name=playlist_name,
                public=False,
                description=f"{config.playlist_description} - Range: {start_index}-{end_index}"
            )
            playlist_id = playlist['id']
            playlist_url = playlist['external_urls']['spotify']
            
            logger.info(f"Created playlist: {playlist_name}")
            
            track_ids = [t.track_id for t in tracks if t.track_id]
            if not track_ids:
                self.trigger_callback("warning", "No valid track IDs found for playlist.")
                return None
                
            # Add tracks in batches
            batches_completed = 0
            for i in range(0, len(track_ids), self.max_tracks_per_batch):
                if self.cancelled:
                    break
                batch = track_ids[i:i + self.max_tracks_per_batch]
                self.safe_api_call(self.sp.playlist_add_items, playlist_id, batch)
                batches_completed += 1
                self.trigger_callback("playlist_batch_completed", batches_completed, (len(track_ids) - 1) // self.max_tracks_per_batch + 1)
                
            if self.cancelled:
                self.trigger_callback("warning", "Playlist population cancelled mid-way.")
                
            result = PlaylistResult(
                playlist_name=playlist_name,
                playlist_id=playlist_id,
                playlist_url=playlist_url,
                tracks_added=len(track_ids)
            )
            self.trigger_callback("playlist_completed", result)
            return result
            
        except Exception as e:
            logger.error(f"Playlist creation failed: {e}")
            self.trigger_callback("warning", f"Playlist creation failed: {e}")
            return None

    def cancel_scan(self):
        self.cancelled = True
        logger.info("Cancellation flag set by user.")
