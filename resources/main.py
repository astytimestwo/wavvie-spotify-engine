import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from datetime import datetime, timedelta
import time
import logging
import argparse
import json
import os
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# === CONFIG ===
CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI', 'http://127.0.0.1:8888/callback')

# Default values (can be overridden by CLI args)
DEFAULT_CUTOFF_DATE = datetime.now() - timedelta(days=30)
SLEEP_BETWEEN_REQUESTS = 1.2  # Slightly lower for concurrent use
PLAYLIST_NAME = "New Releases"
PLAYLIST_DESCRIPTION = "New tracks from followed artists"
MAX_RETRIES = 3
MAX_TRACKS_PER_BATCH = 100

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === AUTH ===
scope = 'user-follow-read playlist-modify-private'
try:
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=scope,
        cache_path=".spotifycache"
    ))
    user = sp.current_user()
    logger.info(f"Authentication successful for user: {user['display_name']}")
except Exception as e:
    logger.error(f"Authentication failed: {e}")
    exit(1)

# === HELPERS ===

def safe_api_call(func, *args, **kwargs):
    """Wrapper for API calls with proper error handling and rate limiting."""
    for attempt in range(MAX_RETRIES):
        try:
            result = func(*args, **kwargs)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            return result
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get('Retry-After', 60))
                logger.warning(f"Rate limit hit. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            elif e.http_status >= 500:
                wait_time = (2 ** attempt) * 2
                logger.warning(f"Server error {e.http_status}. Retrying in {wait_time}s... (attempt {attempt + 1})")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"API error: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
    
    raise Exception(f"Max retries ({MAX_RETRIES}) exceeded")

def parse_release_date(date_str):
    """Parse Spotify release date with better error handling."""
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

def create_track_signature(track_name: str, all_artists: List[str]) -> str:
    """Create a unique signature for track deduplication."""
    return f"{track_name.lower()}|{'|'.join(sorted([a.lower() for a in all_artists]))}"

def get_followed_artists(sp):
    """Get all followed artists with proper pagination."""
    logger.info("Fetching followed artists...")
    artists = []
    after = None
    
    while True:
        try:
            results = safe_api_call(sp.current_user_followed_artists, limit=50, after=after)
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
            break
    
    return artists

def get_and_cache_followed_artists(sp, cache_file="followed_artists_cache.json"):
    """Get all followed artists and cache them for consistent ordering."""
    
    # Try to load from cache first
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
                logger.info(f"Loaded {len(cached_data)} artists from cache")
                return cached_data
        except Exception as e:
            logger.warning(f"Cache file corrupted ({e}), fetching fresh data")
    
    # Fetch all artists
    artists = get_followed_artists(sp)
    
    # Sort alphabetically for consistent ordering
    artists.sort(key=lambda x: x.get('name', '').lower())
    logger.info(f"Sorted {len(artists)} artists alphabetically")
    
    # Cache the results
    try:
        with open(cache_file, 'w') as f:
            json.dump(artists, f, indent=2)
        logger.info(f"Cached {len(artists)} artists for future runs")
    except Exception as e:
        logger.warning(f"Could not cache artists: {e}")
    
    return artists

def is_actual_performer(track_artists: List[Dict], followed_artist_id: str) -> bool:
    """
    Check if the followed artist is actually performing on the track.
    This filters out ghost credits like producers, writers, etc.
    Only includes artists listed in the main 'artists' field which indicates performance.
    """
    performer_ids = [a.get('id') for a in track_artists if a.get('id')]
    return followed_artist_id in performer_ids

def prioritize_album_version(track_data_list):
    """
    Given multiple versions of the same track, return the best one.
    Priority: Original Album > Single > EP > Compilation
    """
    if len(track_data_list) == 1:
        return track_data_list[0]
    
    # Define priority order (lower number = higher priority)
    priority_map = {
        'album': 1,
        'single': 2,
        'ep': 3,
        'compilation': 4,
        'unknown': 5
    }
    
    # Sort by priority, then by release date (prefer earlier for originals)
    sorted_tracks = sorted(track_data_list, key=lambda x: (
        priority_map.get(x.get('album_type', 'unknown').lower(), 5),
        x.get('release_date', '9999-99-99')  # Earlier dates first
    ))
    
    chosen = sorted_tracks[0]
    logger.debug(f"Chose '{chosen['album_name']}' ({chosen.get('album_type', 'unknown')}) over {len(track_data_list)-1} alternatives for '{chosen['track_name']}'")
    
    return chosen

def is_trashy_compilation(album_info: Dict) -> bool:
    """Check if an album is a trashy compilation that should be skipped."""
    album_type = album_info.get('album_type', '').lower()
    album_name = album_info.get('name', '').lower()
    
    # Expanded list of compilation keywords to skip
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
    
    # Skip if it's a compilation type OR contains trashy keywords
    if album_type == 'compilation':
        return True
    
    # Check for trashy keywords in album name
    if any(keyword in album_name for keyword in skip_keywords):
        return True
    
    return False

def should_include_album_type(album_type: str) -> bool:
    """
    Filter album types we want to include.
    This replaces the problematic include_groups parameter.
    """
    album_type = album_type.lower()
    # Include albums, singles, EPs, and appears_on (collaborations)
    # Exclude compilations (handled separately by is_trashy_compilation)
    return album_type in ['album', 'single', 'ep', 'appears_on']

def get_album_tracks(album_id: str, album_info: Dict, followed_artist_id: str) -> List[Dict]:
    """Get tracks from an album where the followed artist actually performs."""
    tracks = []
    offset = 0
    
    # Get album artwork URL
    album_images = album_info.get('images', [])
    album_artwork_url = album_images[0].get('url') if album_images else None
    
    while True:
        try:
            result = safe_api_call(sp.album_tracks, album_id, limit=50, offset=offset)
            if not result:
                break
            
            items = result.get('items', [])
            if not items:
                break
            
            for track in items:
                track_artists = track.get('artists', [])
                
                # STRICT: Only include if followed artist is in the main 'artists' field
                # This field represents actual performers (vocals, main instruments)
                # Excludes ghost credits like producers, writers, session musicians
                if not is_actual_performer(track_artists, followed_artist_id):
                    continue
                
                if track.get('id'):
                    # Determine if this is a collaboration for the followed artist
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
                        'track_signature': create_track_signature(track.get('name', 'Unknown Track'), all_artists)
                    })
            
            offset += 50
            if len(items) < 50:
                break
                
        except Exception as e:
            logger.warning(f"Error fetching tracks for album {album_info.get('name', 'Unknown')}: {e}")
            break
    
    return tracks

def get_artist_albums_robust(sp, artist_id: str, artist_name: str, cutoff_date: datetime) -> List[Dict]:
    """
    Get all albums for an artist using a more robust approach.
    This replaces the problematic include_groups parameter with client-side filtering.
    """
    all_albums = []
    offset = 0
    consecutive_empty_pages = 0
    max_consecutive_empty = 3  # Stop if we get 3 consecutive empty pages
    
    logger.debug(f"Fetching albums for {artist_name}...")
    
    while consecutive_empty_pages < max_consecutive_empty:
        try:
            # Fetch all album types without filtering (avoid include_groups)
            result = safe_api_call(sp.artist_albums, artist_id, limit=50, offset=offset)
            
            if not result or not result.get('items'):
                consecutive_empty_pages += 1
                logger.debug(f"Empty page at offset {offset} for {artist_name} (consecutive: {consecutive_empty_pages})")
                offset += 50
                continue
            
            items = result['items']
            page_albums = []
            
            for album in items:
                # Client-side filtering instead of using include_groups
                album_type = album.get('album_type', 'unknown').lower()
                
                # Skip unwanted album types
                if not should_include_album_type(album_type):
                    logger.debug(f"Skipping {album_type}: {album.get('name', 'Unknown')}")
                    continue
                
                # Skip trashy compilations
                if is_trashy_compilation(album):
                    logger.debug(f"Skipping trashy compilation: {album.get('name', 'Unknown')}")
                    continue
                
                # Check release date
                if not album.get('release_date'):
                    continue
                    
                release_date = parse_release_date(album['release_date'])
                if not release_date or release_date < cutoff_date:
                    continue
                
                page_albums.append(album)
            
            if page_albums:
                all_albums.extend(page_albums)
                consecutive_empty_pages = 0  # Reset counter if we found albums
                logger.debug(f"Found {len(page_albums)} relevant albums at offset {offset} for {artist_name}")
            else:
                consecutive_empty_pages += 1
                logger.debug(f"No relevant albums at offset {offset} for {artist_name} (consecutive: {consecutive_empty_pages})")
            
            # Check if we've reached the end
            if len(items) < 50:
                logger.debug(f"Reached end of albums for {artist_name} (got {len(items)} items)")
                break
            
            offset += 50
            
        except Exception as e:
            logger.error(f"Error fetching albums at offset {offset} for {artist_name}: {e}")
            consecutive_empty_pages += 1
            if consecutive_empty_pages >= max_consecutive_empty:
                break
            offset += 50
            continue
    
    logger.debug(f"Total albums found for {artist_name}: {len(all_albums)}")
    return all_albums

def get_artist_collaborations(artist_id: str, artist_name: str, cutoff_date: datetime) -> List[Dict]:
    """Find collaborations where the artist is featured on other artists' tracks."""
    collab_tracks = []
    seen_track_signatures = set()  # Use signature for deduplication
    
    try:
        # More targeted search - only look for explicit features
        search_queries = [
            f'feat "{artist_name}"',
            f'featuring "{artist_name}"',
            f'ft "{artist_name}"',
            f'with "{artist_name}"',
            f'"{artist_name}" remix',
            f'"{artist_name}" mix'
        ]
        
        for query in search_queries:
            offset = 0
            while offset < 200:  # Reduced search depth
                try:
                    result = safe_api_call(sp.search, q=query, type='track', limit=50, offset=offset)
                    if not result or not result.get('tracks'):
                        break
                    
                    tracks = result['tracks'].get('items', [])
                    if not tracks:
                        break
                    
                    for track in tracks:
                        album = track.get('album', {})
                        
                        # Skip trashy compilations
                        if is_trashy_compilation(album):
                            continue
                        
                        release_date = parse_release_date(album.get('release_date'))
                        if not release_date or release_date < cutoff_date:
                            continue
                        
                        track_artists = track.get('artists', [])
                        
                        # STRICT: Only include if followed artist is in the main 'artists' field
                        if not is_actual_performer(track_artists, artist_id):
                            continue
                        
                        # Additional validation: Check if track title contains keywords
                        track_name = track.get('name', '').lower()
                        valid_collab = any(keyword in track_name for keyword in ['feat', 'featuring', 'ft', 'with', 'remix', 'mix'])
                        if not valid_collab:
                            continue
                        
                        # Check if this is truly a collaboration (artist is featured, not main)
                        album_artists = album.get('artists', [])
                        is_main_artist = any(a.get('id') == artist_id for a in album_artists)
                        
                        # Only add if it's a feature/collaboration (not their own release)
                        if not is_main_artist and track.get('id'):
                            main_artist_name = album_artists[0].get('name', 'Unknown') if album_artists else 'Unknown'
                            
                            # Additional check: Make sure the main artist is different
                            if main_artist_name.lower() == artist_name.lower():
                                continue
                            
                            all_artists = [a.get('name', 'Unknown') for a in track_artists]
                            track_signature = create_track_signature(track.get('name', 'Unknown Track'), all_artists)
                            
                            # Skip if already processed using signature
                            if track_signature in seen_track_signatures:
                                continue
                            
                            # Get album artwork
                            album_images = album.get('images', [])
                            album_artwork_url = album_images[0].get('url') if album_images else None
                            
                            seen_track_signatures.add(track_signature)
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
                    logger.warning(f"Error in collaboration search: {e}")
                    break
                    
    except Exception as e:
        logger.error(f"Error searching collaborations for {artist_name}: {e}")
    
    return collab_tracks

def get_new_tracks(sp, artist_id, artist_name, cutoff_date):
    """Get new tracks for an artist including collaborations, with smart deduplication."""
    all_tracks = []
    track_versions = {}  # track_signature -> list of track data from different albums
    
    # Get albums using the robust method (without include_groups)
    try:
        albums = get_artist_albums_robust(sp, artist_id, artist_name, cutoff_date)
        logger.debug(f"Found {len(albums)} relevant albums for {artist_name}")
        
        for album in albums:
            # Get tracks from this album
            album_tracks = get_album_tracks(album['id'], album, artist_id)
            
            # Group tracks by signature for smart deduplication
            for track in album_tracks:
                track_signature = track['track_signature']
                if track_signature not in track_versions:
                    track_versions[track_signature] = []
                track_versions[track_signature].append(track)
        
    except Exception as e:
        logger.error(f"Error fetching albums for artist {artist_name}: {e}")
    
    # Choose the best version of each track
    for track_signature, versions in track_versions.items():
        best_version = prioritize_album_version(versions)
        all_tracks.append(best_version)
    
    # Get collaboration tracks
    logger.debug(f"Searching for collaborations for {artist_name}...")
    collaboration_tracks = get_artist_collaborations(artist_id, artist_name, cutoff_date)
    
    # Add collaborations (check against signatures to avoid duplicates)
    collab_count = 0
    for track in collaboration_tracks:
        track_signature = track['track_signature']
        # Check if we already have this track from the artist's own releases
        if track_signature not in track_versions:
            all_tracks.append(track)
            collab_count += 1
        else:
            logger.debug(f"Skipping collaboration '{track['track_name']}' - already have from artist's own releases")
    
    logger.info(f"Found {len(all_tracks)} unique tracks for {artist_name} ({collab_count} collaborations)")
    
    # Log album type breakdown
    album_counts = {}
    for track in all_tracks:
        album_type = track.get('album_type', 'unknown')
        album_counts[album_type] = album_counts.get(album_type, 0) + 1
    
    if album_counts:
        breakdown = ', '.join([f"{count} {type_}" for type_, count in album_counts.items()])
        logger.info(f"  └── Album types: {breakdown}")
    
    return all_tracks


def dump_tracklist_to_json(tracks, filename):
    """Dump the tracklist to a JSON file for analysis."""
    try:
        # Create a clean version for JSON export
        clean_tracks = []
        missing_artwork_count = 0
        
        for track in tracks:
            if not track.get('album_artwork_url'):
                missing_artwork_count += 1
                logger.debug(f"Missing artwork: {track.get('track_name', 'Unknown')} - {track.get('album_name', 'Unknown')}")
            
            clean_track = {
                'track_id': track.get('track_id'),
                'track_name': track.get('track_name'),
                'album_name': track.get('album_name'),
                'album_type': track.get('album_type'),
                'release_date': track.get('release_date'),
                'artist_name': track.get('artist_name'),
                'performer_role': track.get('performer_role'),
                'is_collaboration': track.get('is_collaboration', False),
                'all_artists': track.get('all_artists', []),
                'main_artist': track.get('main_artist'),
                'has_artwork': bool(track.get('album_artwork_url')),
                'track_signature': track.get('track_signature')
            }
            clean_tracks.append(clean_track)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'total_tracks': len(tracks),
                    'missing_artwork': missing_artwork_count,
                    'export_timestamp': datetime.now().isoformat()
                },
                'tracks': clean_tracks
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Tracklist exported to {filename}")
        if missing_artwork_count > 0:
            logger.warning(f"Missing artwork for {missing_artwork_count} tracks")
        
    except Exception as e:
        logger.error(f"Failed to export tracklist: {e}")

def create_playlist_with_tracks(sp, tracks, start_index, end_index):
    """Create playlist and add tracks in batches."""
    if not tracks:
        logger.info("No tracks to add to playlist.")
        return None
    
    try:
        range_suffix = f" (Artists {start_index}-{end_index})" if start_index != 1 or end_index != 9999 else ""
        playlist_name = PLAYLIST_NAME + range_suffix
        
        user_id = sp.current_user()['id']
        playlist = safe_api_call(sp.user_playlist_create,
            user=user_id,
            name=playlist_name,
            public=False,
            description=f"{PLAYLIST_DESCRIPTION} - Range: {start_index}-{end_index}"
        )
        playlist_id = playlist['id']
        logger.info(f"Created playlist: {playlist_name}")


        track_ids = [track['track_id'] for track in tracks if track.get('track_id')]
        if not track_ids:
            logger.warning("No valid track IDs to add to playlist.")
            return playlist
        
        # Add tracks in batches
        for i in range(0, len(track_ids), MAX_TRACKS_PER_BATCH):
            batch = track_ids[i:i + MAX_TRACKS_PER_BATCH]
            safe_api_call(sp.playlist_add_items, playlist_id, batch)
            logger.info(f"Added batch {i//MAX_TRACKS_PER_BATCH + 1}: {len(batch)} tracks")
        
        logger.info(f"Successfully added {len(track_ids)} tracks to playlist: {playlist['name']}")
        return playlist
        
    except Exception as e:
        logger.error(f"Error creating or populating playlist: {e}")
        return None

# === MAIN ===

def main(start_index, end_index, cutoff_date):
    all_tracks = []
    # Global deduplication using track signature (name + artists)
    global_seen = {}

    try:
        followed_artists = get_and_cache_followed_artists(sp)
        logger.info(f"Total artists found: {len(followed_artists)}")
        
        if start_index > len(followed_artists):
            logger.error(f"Start index {start_index} is greater than total artists ({len(followed_artists)})")
            return
        
        actual_end = min(end_index, len(followed_artists))
        logger.info(f"Processing artists {start_index} to {actual_end} out of {len(followed_artists)} total")
        
    except Exception as e:
        logger.error(f"Failed to fetch artists: {e}")
        return

    artists_to_process = followed_artists[start_index-1:actual_end]
    
    def process_artist(artist_info):
        artist_idx, artist = artist_info
        actual_index = start_index + artist_idx
        artist_name = artist.get('name', 'Unknown Artist')
        logger.info(f"[{actual_index}/{actual_end}] Processing: {artist_name}")
        try:
            return get_new_tracks(sp, artist['id'], artist_name, cutoff_date)
        except Exception as e:
            logger.error(f"Error processing {artist_name}: {e}")
            return []

    # Process artists in parallel
    logger.info(f"Using ThreadPoolExecutor for faster processing...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Use list of tuples (index, artist) to keep track of progress
        futures = {executor.submit(process_artist, (i, artist)): artist for i, artist in enumerate(artists_to_process)}
        
        for future in as_completed(futures):
            try:
                new_tracks = future.result()
                for track in new_tracks:
                    track_signature = track['track_signature']
                    # Global deduplication using track signature
                    if track_signature not in global_seen:
                        global_seen[track_signature] = {
                            'track_id': track['track_id'],
                            'artist_name': track['artist_name'],
                            'track_name': track['track_name'],
                            'album_name': track.get('album_name', 'Unknown Album'),
                            'added_from': track.get('performer_role', 'unknown')
                        }
                        all_tracks.append(track)
                    else:
                        original = global_seen[track_signature]
                        logger.debug(f"Skipped duplicate: {track['track_name']} (already added from {original['artist_name']})")
            except Exception as e:
                artist = futures[future]
                logger.error(f"Future failed for artist {artist.get('name')}: {e}")

    logger.info(f"Processing complete. Total unique tracks found: {len(all_tracks)}")
    
    # Show statistics about duplicates prevented
    duplicates_prevented = len(global_seen) - len(all_tracks)
    if duplicates_prevented > 0:
        logger.info(f"Duplicates prevented: {duplicates_prevented}")
    
    # Sort tracks by release date (newest first)
    all_tracks.sort(key=lambda x: x['release_date'], reverse=True)
    
    # Export tracklist to JSON
    json_filename = f"tracklist_{start_index}_{actual_end}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    dump_tracklist_to_json(all_tracks, json_filename)
    
    # Create playlist with all tracks
    playlist = create_playlist_with_tracks(sp, all_tracks, start_index, actual_end)
    
    if playlist:
        logger.info(f"✅ Success! Playlist '{playlist['name']}' created with {len(all_tracks)} tracks")
        logger.info(f"Playlist URL: {playlist['external_urls']['spotify']}")
        
        # Show some sample tracks with better info including album art
        if all_tracks:
            logger.info("Sample tracks added:")
            for i, track in enumerate(all_tracks[:10]):  # Show more samples
                role = track.get('performer_role', 'unknown')
                album_type = track.get('album_type', 'unknown')
                has_artwork = "🎨" if track.get('album_artwork_url') else "❌"
                
                if role == 'featured':
                    role_info = f" (featured on {track.get('main_artist', 'Unknown')}'s {album_type})"
                elif role == 'main':
                    role_info = f" (from {album_type}: {track.get('album_name', 'Unknown Album')})"
                else:
                    role_info = f" (from {track.get('album_name', 'Unknown Album')})"
                
                logger.info(f"  {i+1}. {has_artwork} {track.get('artist_name', 'Unknown')} - {track.get('track_name', 'Unknown')}{role_info} ({track['release_date']})")
            
            if len(all_tracks) > 10:
                logger.info(f"  ... and {len(all_tracks) - 10} more tracks")
    else:
        logger.error("❌ Failed to create playlist")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create Spotify playlist from followed artists in specified range")
    parser.add_argument('--start', type=int, default=1, help='Start index (1-based, default: 1)')
    parser.add_argument('--end', type=int, default=9999, help='End index (1-based, default: process all)')
    parser.add_argument('--cutoff', type=str, default=DEFAULT_CUTOFF_DATE.strftime('%Y-%m-%d'), help='Cutoff date (YYYY-MM-DD, default: 2025-10-12)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    try:
        cutoff_date = datetime.strptime(args.cutoff, '%Y-%m-%d')
    except ValueError:
        logger.error("Invalid cutoff date format. Use YYYY-MM-DD")
        exit(1)
    
    if args.start < 1:
        logger.error("Start index must be >= 1")
        exit(1)
    
    if args.end < args.start:
        logger.error("End index must be >= start index")
        exit(1)
    
    logger.info(f"Starting playlist creation for artists {args.start} to {args.end} (Cutoff: {args.cutoff})")
    main(args.start, args.end, cutoff_date)