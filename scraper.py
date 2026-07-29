"""
Scraper module, handles extracting playlist and track metadata from Spotify
by intercepting network requests via a headless browser.
"""

from playwright.sync_api import sync_playwright
import re
import logging

logger = logging.getLogger(__name__)


def extract_metadata(captured_responses):
    """
    Parse captured Spotify GraphQL (pathfinder) responses into track metadata.

    Spotify's web player loads playlist tracks via paginated GraphQL requests
    as the user scrolls. This walks through all captured response payloads,
    deduplicates tracks by Spotify track ID, and pulls out the fields needed
    for matching and tagging (title, artists, album, cover, duration, etc.).

    ### Arguments
    - captured_responses: list of parsed JSON response bodies captured from
      network traffic, each expected to contain a `playlistV2` payload
      (list[dict])

    ### Returns
    - list of metadata dicts, one per track, with keys:
      title, artists, cover_url, song_url, album_name, album_track,
      release_date, duration (list[dict]).
      Tracks with any missing required field are logged and skipped.
    """

    songs_metadata = []
    seen = set()
    for response in captured_responses:
        entries = response if isinstance(response, list) else [response]
        for entry in entries:
            playlist = entry.get("data", {}).get("playlistV2")
            if not playlist or playlist.get("__typename") == "NotFound":
                continue
            items = playlist.get("content", {}).get("items", [])
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

    return songs_metadata


def get_total_count(captured_responses):
    """
    Extract the playlist's total track count from captured GraphQL responses.

    Used to know when scrolling/scraping has reached the end of the playlist,
    since Spotify loads tracks lazily in pages.

    ### Arguments
    - captured_responses: list of parsed JSON response bodies captured from
      network traffic (list[dict])

    ### Returns
    - total number of tracks in the playlist (int), or None if not found
      in any captured response
    """

    for response in captured_responses:
        entries = response if isinstance(response, list) else [response]
        for entry in entries:
            playlist = entry.get("data", {}).get("playlistV2")
            if playlist and playlist.get("__typename") != "NotFound":
                content = playlist.get("content", {})
                if "totalCount" in content:
                    return content["totalCount"]
    return None


def scrape_playlist_via_network(playlist_url, max_idle_scrolls=8):
    """
    Load a Spotify playlist page in a headless browser and capture its
    track data by intercepting GraphQL (pathfinder) network responses.

    This drives a real browser, scrolls the playlist to
    trigger lazy-loaded pagination requests, and collects the raw JSON
    responses as they come in. Scrolling stops once the known total track
    count is reached, or after `max_idle_scrolls` consecutive scrolls
    produce no new tracks (e.g. end of playlist, or a stalled/blocked load).

    ### Arguments
    - playlist_url: URL of the Spotify playlist to scrape (str)
    - max_idle_scrolls: number of consecutive scrolls with no new tracks
      found before giving up and stopping (int, default 8)

    ### Returns
    - list of raw captured GraphQL response payloads (list[dict]),
      to be parsed later via `extract_metadata`
    """

    logger.info(f"Scraping songs metadata from playlist: {playlist_url}")
    captured_tracks = []

    def handle_response(response):
        if "pathfinder" in response.url and response.request.method == "POST":
            try:
                data = response.json()
                captured_tracks.append(data)
            except Exception:
                pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("response", handle_response)
        page.goto(playlist_url, wait_until="networkidle")
        page.wait_for_timeout(1500)

        page.mouse.move(700, 500)

        expected_total = None
        idle_count = 0
        prev_track_count = 0

        while idle_count < max_idle_scrolls:
            page.mouse.wheel(0, 2500)
            page.wait_for_timeout(1000)

            current_metadata = extract_metadata(captured_tracks)
            current_track_count = len(current_metadata)

            if expected_total is None:
                expected_total = get_total_count(captured_tracks)

            logger.info(f"Progress: {current_track_count}/{expected_total} | requests: {len(captured_tracks)}")

            if expected_total and current_track_count >= expected_total:
                break

            if current_track_count == prev_track_count:
                idle_count += 1
            else:
                idle_count = 0

            prev_track_count = current_track_count

        browser.close()

    return captured_tracks


def obtain_spotify_metadata(playlist_url):
    """
    Full pipeline to scrape and extract metadata for all tracks in a
    Spotify playlist.

    ### Arguments
    - playlist_url: URL of the Spotify playlist to scrape (str)

    ### Returns
    - list of metadata dicts, one per successfully parsed track
      (see `extract_metadata` for the dict shape) (list[dict])
    """

    scrape = scrape_playlist_via_network(playlist_url)
    songs_metadata = extract_metadata(scrape)
    total = get_total_count(scrape)
    logger.info(f"Extracted metadata for {len(songs_metadata)} of {total} expected songs.")
    return songs_metadata
