import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

from core.models import ScanConfiguration, ScanResult
from core.spotify_service import SpotifyReleaseService

# === LOGGING SETUP ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def dotenv_search_paths(base_dir=None, cwd=None, executable_path=None):
    """Return .env locations for source runs and packaged executable runs."""
    base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
    cwd = cwd or os.getcwd()
    executable_path = executable_path or sys.executable

    candidates = [
        os.path.join(str(cwd), ".env"),
        os.path.join(str(base_dir), ".env"),
    ]

    exe_dir = os.path.dirname(os.path.abspath(str(executable_path)))
    candidates.extend([
        os.path.join(exe_dir, ".env"),
        os.path.join(os.path.dirname(exe_dir), ".env"),
    ])

    paths = []
    seen = set()
    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if normalized not in seen:
            paths.append(type(base_dir)(normalized) if hasattr(base_dir, "__truediv__") else normalized)
            seen.add(normalized)
    return paths

def load_environment():
    for env_path in dotenv_search_paths():
        load_dotenv(env_path, override=False)

# Load env variables before importing or checking configuration
load_environment()

def run_cli(start_index: int, end_index: int, cutoff_date_str: str, refresh_cache: bool, verbose: bool):
    if verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger('core.spotify_service').setLevel(logging.DEBUG)
        
    service = SpotifyReleaseService()
    
    if not service.is_configured():
        logger.error("Spotify credentials are not configured. Please set them in your .env file.")
        sys.exit(1)
        
    # Hook up service callbacks to CLI logs
    def on_auth_started():
        logger.info("Starting Spotify authentication...")
        
    def on_auth_success(user_data):
        logger.info(f"Authentication successful for user: {user_data.get('display_name')}")
        
    def on_auth_failed(error_msg):
        logger.error(f"Authentication failed: {error_msg}")
        
    def on_artists_loaded(artists):
        logger.info(f"Total artists found: {len(artists)}")
        
    def on_scan_init(num_to_scan, total):
        logger.info(f"Processing artists {start_index} to {start_index + num_to_scan - 1} out of {total} total")
        logger.info("Using ThreadPoolExecutor for faster processing...")
        
    def on_artist_scanning(actual_idx, artist_name, image_url):
        logger.info(f"[{actual_idx}] Processing: {artist_name}")
        
    def on_artist_completed(actual_idx, artist_name, num_tracks):
        # We don't need excessive completion logs unless in debug, but logging summary is nice
        logger.debug(f"[{actual_idx}] Finished processing {artist_name} (found {num_tracks} tracks)")
        
    def on_track_discovered(track):
        # We log this as debug, or summary at the end
        role_info = ""
        if track.performer_role == 'featured':
            role_info = f" (featured on {track.main_artist}'s {track.album_type})"
        elif track.performer_role == 'main':
            role_info = f" (from {track.album_type}: {track.album_name})"
        logger.debug(f"Discovered: {track.artist_name} - {track.track_name}{role_info} ({track.release_date})")

    def on_duplicate_prevented(track_name, original_artist):
        logger.debug(f"Skipped duplicate: {track_name} (already added from {original_artist})")
        
    def on_rate_limit(retry_after):
        logger.warning(f"Rate limit hit. Waiting {retry_after} seconds...")
        
    def on_warning(msg):
        logger.warning(msg)
        
    def on_playlist_started():
        logger.info("Creating Spotify playlist...")
        
    def on_playlist_batch_completed(batch_num, total_batches):
        logger.info(f"Added batch {batch_num}/{total_batches} to playlist")

    service.register_callback("auth_started", on_auth_started)
    service.register_callback("auth_success", on_auth_success)
    service.register_callback("auth_failed", on_auth_failed)
    service.register_callback("artists_loaded", on_artists_loaded)
    service.register_callback("scan_init_complete", on_scan_init)
    service.register_callback("artist_scanning_started", on_artist_scanning)
    service.register_callback("artist_scanning_completed", on_artist_completed)
    service.register_callback("track_discovered", on_track_discovered)
    service.register_callback("duplicate_prevented", on_duplicate_prevented)
    service.register_callback("rate_limit_encountered", on_rate_limit)
    service.register_callback("warning", on_warning)
    service.register_callback("playlist_started", on_playlist_started)
    service.register_callback("playlist_batch_completed", on_playlist_batch_completed)

    # Perform authentication
    if not service.authenticate():
        sys.exit(1)

    # Create config
    config = ScanConfiguration(
        start_index=start_index,
        end_index=end_index,
        cutoff_date_str=cutoff_date_str,
        refresh_cache=refresh_cache
    )

    # Run scan
    scan_result = service.scan_releases(config)
    
    if not scan_result:
        logger.error("❌ Failed to complete release scan.")
        sys.exit(1)
        
    logger.info(f"Processing complete. Total unique tracks found: {scan_result.total_tracks}")
    if scan_result.duplicates_prevented > 0:
        logger.info(f"Duplicates prevented: {scan_result.duplicates_prevented}")
        
    # Export JSON
    json_path = service.dump_tracklist_to_json(scan_result.tracks, start_index, min(end_index, scan_result.total_artists))
    
    # Create Playlist
    playlist_result = service.create_playlist(scan_result.tracks, config, start_index, min(end_index, scan_result.total_artists))
    
    if playlist_result:
        logger.info(f"✅ Success! Playlist '{playlist_result.playlist_name}' created with {playlist_result.tracks_added} tracks")
        logger.info(f"Playlist URL: {playlist_result.playlist_url}")
        
        # Display sample tracks
        if scan_result.tracks:
            logger.info("Sample tracks added:")
            for i, track in enumerate(scan_result.tracks[:10]):
                role = track.performer_role
                album_type = track.album_type
                has_artwork = "🎨" if track.album_artwork_url else "❌"
                
                if role == 'featured':
                    role_info = f" (featured on {track.main_artist}'s {album_type})"
                elif role == 'main':
                    role_info = f" (from {album_type}: {track.album_name})"
                else:
                    role_info = f" (from {track.album_name})"
                    
                logger.info(f"  {i+1}. {has_artwork} {track.artist_name} - {track.track_name}{role_info} ({track.release_date})")
                
            if len(scan_result.tracks) > 10:
                logger.info(f"  ... and {len(scan_result.tracks) - 10} more tracks")
    else:
        logger.error("❌ Failed to create playlist")

if __name__ == "__main__":
    # Calculate default cutoff date (30 days ago)
    default_cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    parser = argparse.ArgumentParser(description="Create Spotify playlist from followed artists in specified range")
    parser.add_argument('--start', type=int, default=1, help='Start index (1-based, default: 1)')
    parser.add_argument('--end', type=int, default=9999, help='End index (1-based, default: process all)')
    parser.add_argument('--cutoff', type=str, default=default_cutoff, help='Cutoff date (YYYY-MM-DD)')
    parser.add_argument('--refresh', action='store_true', help='Force refresh the followed artists cache from Spotify')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    try:
        # Validate date format before passing
        datetime.strptime(args.cutoff, '%Y-%m-%d')
    except ValueError:
        logger.error("Invalid cutoff date format. Use YYYY-MM-DD")
        sys.exit(1)
        
    if args.start < 1:
        logger.error("Start index must be >= 1")
        sys.exit(1)
        
    if args.end < args.start:
        logger.error("End index must be >= start index")
        sys.exit(1)
        
    logger.info(f"Starting playlist creation for artists {args.start} to {args.end} (Cutoff: {args.cutoff})")
    run_cli(args.start, args.end, args.cutoff, args.refresh, args.verbose)
