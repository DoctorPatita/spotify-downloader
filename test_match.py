import logging

from old_scraper import obtain_spotify_metadata
from matcher import find_match

def setup_logger(debug):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger

def main():
    SONG_URL = "https://open.spotify.com/track/6Fw6xUStR2gs4gmO4tTexr"
    DEBUG  = True

    logger = setup_logger(DEBUG)

     
    metadata = obtain_spotify_metadata(SONG_URL)

    logger.info("============================================================")
    logger.info(f"Processing: {SONG_URL}")

    logger.debug("=== Metadata Found ===")
    logger.debug(f"   Song: {metadata['title']}")
    logger.debug(f"   Artists: {metadata['artists']}")
    logger.debug(f"   Cover: {metadata['cover_url']}")
    logger.debug(f"   Album: {metadata['album_name']}")
    logger.debug(f"   Track Number: {metadata['album_track']}")
    logger.debug(f"   Release Date: {metadata['release_date']}")
    logger.debug(f"   Duration: {metadata['duration']}")

    match = find_match(metadata)

    if not match:
        logger.warning(f"Failed to find a match for '{SONG_URL}'.")

if __name__ == "__main__":
    main()
