"""
Scraper module, handles extracting playlist and track metadata from Spotify
using spotAPI
"""

import re
import logging

from spotapi import PublicPlaylist

logger = logging.getLogger(__name__)


def obtain_spotify_metadata(playlist_id):
    """
    Fetch and extract metadata for all tracks in a Spotify playlist.

    Paginates through the playlist via spotAPI's public GraphQL endpoint,
    deduplicating tracks by Spotify track ID, and pulls out the fields
    needed for matching and tagging (title, artists, album, cover,
    duration, etc.).

    ### Arguments
    - playlist_id: Spotify playlist URL or ID (str)

    ### Returns
    - list of metadata dicts, one per successfully parsed track, with keys:
      title, artists, cover_url, song_url, album_name, album_track,
      release_date, duration (list[dict]).
      Tracks with any missing required field are logged and skipped.
    """

    songs_metadata = []
    seen = set()
    total = 0

    playlist = PublicPlaylist(playlist_id)

    for playlist_data in playlist.paginate_playlist():
            items = playlist_data.get("items", [])
            total = playlist_data.get("totalCount")
            for item in items:
                track_data = item.get("itemV3", {}).get("data", {})

                uri = track_data.get("uri", "")
                match = re.match(r"spotify:track:(\w+)", uri)
                track_id = match.group(1)
                if track_id in seen:
                    continue

                duration = track_data.get("consumptionExperienceTrait", {}).get("duration", {}).get("seconds")

                identity = track_data.get("identityTrait", {})
                parent = identity.get("contentHierarchyParent", {})

                album_name = parent.get("identityTrait", {}).get("name", "")
                release_date = parent.get("publishingMetadataTrait", {}).get("firstPublishedAt", "").get("isoString", "")

                artists = identity.get("contributors", {}).get("items", [])
                artists_names = []
                for artist in artists:
                    artists_names.append(artist.get("name", ""))

                track_name = identity.get("name", "")

                cover_url = None
                covers = item.get("itemV2", {}).get("data", {}).get("albumOfTrack").get("coverArt", {}).get("sources", [])
                for cover in covers:
                    if cover.get("height") == 640:
                        cover_url = cover.get("url", "")

                album_track = item.get("itemV2", {}).get("data", {}).get("trackNumber")

                seen.add(track_id)
                metadata = {
                    "title": track_name,
                    "artists": artists_names,
                    "cover_url": cover_url,
                    "song_url": f"https://open.spotify.com/track/{track_id}",
                    "album_name": album_name,
                    "album_track": album_track,
                    "release_date": release_date,
                    "duration": int(duration)
                }

                metadata_missing = False
                for key, value in metadata.items():
                    if not value:
                        logger.error(f"Failed to get {key}")
                        metadata_missing = True

                if metadata_missing: 
                    logger.error(f"Could not retrieve metadata for https://open.spotify.com/track/{track_id}.")
                    continue

                songs_metadata.append(metadata)

    logger.info(f"Extracted metadata for {len(songs_metadata)} of {total} expected songs.")
    return songs_metadata
