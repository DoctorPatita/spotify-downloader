"""
Searcher module, queries YouTube Music and YouTube for candidate results
to be scored and matched against a Spotify track's metadata.
"""

from ytmusicapi import YTMusic 
import yt_dlp

import logging

from utils import ratio


logger = logging.getLogger(__name__)


def search_youtube(query, limit=5):
    """
    Fallback search on general YouTube (not just YT Music).
    No album data available; channel name is used as the artist.

    ### Arguments
    - query: search query, typically "title - artists" (str)
    - limit: max number of results to fetch (int, default 5)

    ### Returns
    - list of candidate dicts, each with keys:
      'id', 'title', 'artists', 'duration', 'album_name' (list[dict]).
      'album_name' is always an empty string, since general YouTube
      results have no reliable album data.
    """

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
    }

    candidates = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        entries = info.get('entries', []) if info else []

    for entry in entries:
        video_id = entry.get('id')
        title = entry.get('title')
        duration = entry.get('duration')
        channel = entry.get('channel') or entry.get('uploader')

        if not video_id or not title or duration is None or not channel:
            continue

        candidates.append({
            'id': video_id,
            'title': title,
            'artists': [channel],
            'duration': duration,
            'album_name': "",
        })

    return candidates


def search_ytmusic(query, limit=1):
    """
    Search YouTube Music directly for songs matching the given query.

    This is the primary/first-choice search strategy, since YT Music
    results include reliable artist and album metadata unlike general
    YouTube search.

    ### Arguments
    - query: search query, typically "title - artists" (str)
    - limit: max number of results to fetch (int, default 1)

    ### Returns
    - list of candidate dicts, each with keys:
      'id', 'title', 'artists', 'duration', 'album_name' (list[dict]).
      Results with no listed artists are skipped, since they can't be
      meaningfully scored against the original track's artists.
    """

    logger.info(f"Searching audio for '{query}'...")
    
    ytmusic = YTMusic() 
    results = ytmusic.search(query, filter="songs", limit=limit)

    candidates = []

    for result in results:
        # ytmusicapi returns duration in string format: "3:45"
        duration_str = result.get('duration')
        parts = duration_str.split(':')

        if len(parts) == 2:
            result_duration = int(parts[0]) * 60 + int(parts[1])
        else:  # H:MM:SS
            result_duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

        video_id = result.get('videoId')
        result_title = result.get('title')
        result_artists = [artist.get('name') for artist in result.get('artists', [])]

        if not result_artists:
            continue

        result_album_data = result.get('album')
        result_album_name = result_album_data.get('name') if result_album_data else ""

        candidates.append({
            'id': video_id,
            'title': result_title,
            'artists': result_artists,
            'duration': result_duration,
            'album_name': result_album_name,
        })

    return candidates

def search_ytmusic_artist_catalog(artist_name):
    """
    Fallback search: look up an artist directly and scan their full song
    catalog for candidates, instead of relying on YT Music's general
    search ranking.

    This exists because YT Music's direct song search can fail to surface
    songs that clearly exist and match (sometimes specific to certain
    artists/languages, e.g. Japanese), likely due to how it ranks results
    internally. Going through the artist's own "top songs" catalog avoids
    that ranking issue entirely.

    Artist name matching for candidate artist search results is skipped
    for the first result (assumed to be the most relevant), but checked
    for subsequent results to avoid pulling songs from unrelated artists.

    ### Arguments
    - artist_name: name of the primary artist to look up (str)

    ### Returns
    - list of candidate dicts, each with keys:
      'id', 'title', 'artists', 'duration', 'album_name' (list[dict])
    """

    # Cuz ytmusic search sometimes sucks (maybe it's only with japanese)
    ytmusic = YTMusic()

    artist_results = ytmusic.search(artist_name, filter="artists", limit=1)
    if not artist_results:
        return []

    candidates = []

    for idx, artist_result in enumerate(artist_results):
        # the 'artist' field can contain multiple names separated by '、'
        # (YT Music sometimes returns a "similar artists" grouping instead
        # of a single artist), so only the first name is used for matching
        artist_result_name = [n.strip() for n in artist_result.get('artist', '').split('、') if n.strip()][0]
        # Don't check first result
        if idx != 0 and ratio(artist_name, artist_result_name) < 60:
                    continue

        browse_id = artist_result.get('browseId')
        if not browse_id:
            continue

        try:
            artist_data = ytmusic.get_artist(browse_id)
        except Exception as e:
            logger.warning(f"Failed to fetch artist data for '{artist_name}' ({browse_id}): {e}")
            continue

        songs_data = artist_data.get('songs', {})
        songs_browse_id = songs_data.get('browseId')

        full_songs = []
        if songs_browse_id:
            try:
                # songs_browse_id is a playlist id ("top songs" auto playlist)
                playlist = ytmusic.get_playlist(songs_browse_id, limit=None)
                full_songs = playlist.get('tracks', [])
            except Exception as e:
                logger.debug(f"Failed to fetch full song catalog: {e}")
                full_songs = songs_data.get('results', [])
        else:
            full_songs = songs_data.get('results', [])

        for song in full_songs:
            video_id = song.get('videoId')
            result_title = song.get('title')
            duration = song.get('duration_seconds')

            if not video_id or not result_title:
                continue

            candidates.append({
                'id': video_id,
                'title': result_title,
                'artists': [a.get('name') for a in song.get('artists', [])] or [artist_name],
                'duration': duration or 0,
                'album_name': song.get('album', {}).get('name', "") if song.get('album') else "",
            })

    return candidates
