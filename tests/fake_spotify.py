"""In-memory stand-in for the Spotify Web API routes wavvie uses.

Mounted as a requests transport, so the real spotipy client and service code
run unchanged. It follows the Development Mode contract Spotify documents
after its February 2026 changes: search and artist-album pages accept at most
10 items, album-track pages at most 50, playlists are created with
POST /me/playlists, and items are added with POST /playlists/{id}/items in
batches of at most 100. Any other route answers 404.
"""
import json
import re
from urllib.parse import urlparse, parse_qs

import requests
import spotipy
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict

GROUP_ORDER = ('album', 'single', 'appears_on', 'compilation')


def artist_ref(artist_id, name):
    return {'id': artist_id, 'name': name, 'type': 'artist', 'uri': f'spotify:artist:{artist_id}',
            'href': f'https://api.spotify.com/v1/artists/{artist_id}',
            'external_urls': {'spotify': f'https://open.spotify.com/artist/{artist_id}'}}


def album(album_id, name, album_type, release_date, artists, total_tracks=1):
    precision = {4: 'year', 7: 'month'}.get(len(release_date), 'day')
    return {'id': album_id, 'name': name, 'album_type': album_type, 'total_tracks': total_tracks,
            'release_date': release_date, 'release_date_precision': precision, 'artists': artists,
            'images': [{'url': f'https://i.scdn.co/image/{album_id}', 'height': 640, 'width': 640}],
            'type': 'album', 'uri': f'spotify:album:{album_id}',
            'href': f'https://api.spotify.com/v1/albums/{album_id}',
            'external_urls': {'spotify': f'https://open.spotify.com/album/{album_id}'}}


def track(track_id, name, artists, on_album=None):
    """A simplified track; pass on_album for the full track objects search returns."""
    item = {'id': track_id, 'name': name, 'artists': artists, 'type': 'track', 'uri': f'spotify:track:{track_id}',
            'duration_ms': 180000, 'explicit': False, 'disc_number': 1, 'track_number': 1, 'is_local': False,
            'href': f'https://api.spotify.com/v1/tracks/{track_id}',
            'external_urls': {'spotify': f'https://open.spotify.com/track/{track_id}'}}
    if on_album is not None:
        item['album'] = on_album
    return item


def error(status, message):
    return status, {'error': {'status': status, 'message': message}}


class FakeSpotifyWebAPI(BaseAdapter):
    def __init__(self):
        super().__init__()
        self.requests = []          # (method, path without /v1, query dict, JSON body)
        self.artist_albums = {}     # artist id -> {group: [album, ...]} in API order
        self.album_tracks = {}      # album id -> [simplified track, ...]
        self.search_tracks = []     # full track objects, in relevance order
        self.playlists = {}         # playlist id -> {'body': create body, 'items': [uri, ...]}

    def client(self):
        session = requests.Session()
        session.mount('https://', self)
        return spotipy.Spotify(auth='test-token', requests_session=session)

    def requested(self, method, path_pattern):
        return [query for m, path, query, _ in self.requests
                if m == method and re.fullmatch(path_pattern, path)]

    def send(self, request, **kwargs):
        url = urlparse(request.url)
        path = url.path.removeprefix('/v1').rstrip('/')
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        body = json.loads(request.body) if request.body else None
        self.requests.append((request.method, path, query, body))
        status, payload = self.route(request.method, path, query, body)
        response = requests.Response()
        response.status_code = status
        response.reason = 'OK' if status < 400 else 'Error'
        response.headers = CaseInsensitiveDict({'Content-Type': 'application/json'})
        response._content = json.dumps(payload).encode()
        response.encoding = 'utf-8'
        response.url = request.url
        response.request = request
        return response

    def close(self):
        pass

    def route(self, method, path, query, body):
        parts = path.strip('/').split('/')
        if method == 'GET' and parts == ['search']:
            return self.search(query)
        if method == 'GET' and len(parts) == 3 and parts[0] == 'artists' and parts[2] == 'albums':
            groups = self.artist_albums.get(parts[1], {})
            wanted = query.get('include_groups', ','.join(GROUP_ORDER)).split(',')
            items = [item for group in GROUP_ORDER if group in wanted for item in groups.get(group, [])]
            return self.page(items, query, maximum=10, default=5)
        if method == 'GET' and len(parts) == 3 and parts[0] == 'albums' and parts[2] == 'tracks':
            return self.page(self.album_tracks.get(parts[1], []), query, maximum=50, default=20)
        if method == 'POST' and parts == ['me', 'playlists']:
            playlist_id = f'playlist{len(self.playlists) + 1}'
            self.playlists[playlist_id] = {'body': body, 'items': []}
            return 201, {'id': playlist_id, 'name': body['name'], 'public': body.get('public', True),
                         'description': body.get('description'), 'snapshot_id': 'snapshot',
                         'external_urls': {'spotify': f'https://open.spotify.com/playlist/{playlist_id}'}}
        if method == 'POST' and len(parts) == 3 and parts[0] == 'playlists' and parts[2] == 'items':
            uris = body['uris'] if isinstance(body, dict) else body
            if parts[1] not in self.playlists:
                return error(404, 'Playlist not found')
            if not 1 <= len(uris) <= 100:
                return error(400, 'You can add a maximum of 100 items per request')
            self.playlists[parts[1]]['items'].extend(uris)
            return 201, {'snapshot_id': 'snapshot'}
        return error(404, 'Service not found')

    def search(self, query):
        years = re.search(r'year:(\d{4})(?:-(\d{4}))?', query.get('q', ''))
        items = self.search_tracks
        if years:
            first, last = int(years.group(1)), int(years.group(2) or years.group(1))
            items = [item for item in items if first <= int(item['album']['release_date'][:4]) <= last]
        status, payload = self.page(items, query, maximum=10, default=5)
        return status, ({'tracks': payload} if status == 200 else payload)

    @staticmethod
    def page(items, query, maximum, default):
        limit, offset = int(query.get('limit', default)), int(query.get('offset', 0))
        if not 1 <= limit <= maximum:
            return error(400, 'Invalid limit')
        chunk = items[offset:offset + limit]
        more = offset + limit < len(items)
        return 200, {'items': chunk, 'limit': limit, 'offset': offset, 'total': len(items),
                     'next': f'https://api.spotify.com/v1/next?offset={offset + limit}' if more else None,
                     'previous': None}
