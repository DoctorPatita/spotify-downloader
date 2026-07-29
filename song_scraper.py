import requests
from bs4 import BeautifulSoup
import json
import logging

logger = logging.getLogger(__name__)


def obtain_song_metadata(url):
    """
    Extract song metadata from a Spotify page using web scraping (Open Graph tags)

    ### Arguments
    - url: Spotify track URL (str)

    ### Returns
    - metadata: dictionary containing:
        - 'title': song title (str)
        - 'artists': list of artists (list[str])
        - 'duration': song duration (int)
        - 'album_name': album name (str)
        - 'album_url': album page URL (str)
        - 'album_track': track number within the album (str)
        - 'release_date': release date (str)
        - 'cover_url': URL of the album cover image (str)
        - 'song_url': original Spotify track URL (str)
      OR False if extraction fails or data is incomplete
    """
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    
    logger.info(f"Scraping metadata from '{url}'")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Raises an error if url is broken (404, etc.)

        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')

    except Exception as e:
        logger.error(f"Failed to process '{url}': {e}")
        return False


    # Extract data using Open Graph tags (og:)
    
    # Song title
    title_tag = soup.find("meta", property="og:title")
    track_name = title_tag["content"] if title_tag else False

    # Cover
    image_tag = soup.find("meta", property="og:image")
    cover_url = image_tag["content"] if image_tag else False

    # Artists
    musician_tag = soup.find("meta", attrs={"name": "music:musician_description"})
    artists_names = [artist.strip() for artist in musician_tag["content"].split(",")] if musician_tag else False

    # Album url
    album_tag = soup.find("meta", attrs={"name": "music:album"})
    album_url = album_tag["content"] if album_tag else False

    # Track number
    album_track_tag = soup.find("meta", attrs={"name": "music:album:track"})
    album_track = album_track_tag["content"] if album_track_tag else False

    # Release date
    release_tag = soup.find("meta", attrs={"name": "music:release_date"})
    release_date = release_tag["content"] if release_tag else False

    # Duration
    duration_tag = soup.find("meta", attrs={"name": "music:duration"})
    duration = duration_tag["content"] if duration_tag else False

    # Album name
    album_name = obtain_album_name(album_url)

    metadata = {
        "title": track_name,
        "artists": artists_names,
        "cover_url": cover_url,
        "song_url": url,
        "album_name": album_name,
        "album_url": album_url,
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
        logger.error(f"Could not retrieve metadata for {url}.")
        return False

    return metadata


def obtain_album_name(url):
    """
    Extract album name from a Spotify album page using JSON-LD script

    ### Arguments
    - url: Spotify album URL (str)

    ### Returns
    - album_name: name of the album (str)
      OR False if extraction fails
    """
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    logger.info(f"Scraping album name from '{url}'")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Raises an error if url is broken (404, etc.)

        #Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        script_json = soup.find('script', {'type': 'application/ld+json'})


        if script_json is None or script_json.string is None:
            logger.error("JSON script tag not found or empty")
            return False

        try:
            data = json.loads(script_json.string)
            album_name = data.get('name')
        except Exception as e:
            logger.error(f"Failed to parse JSON: {e}")
            return False

        return album_name

    except Exception as e:
        logger.error(f"Failed to process '{url}': {e}")
        return False
