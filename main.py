"""
Main module, this is where the playlist download pipeline runs.
"""

import os
import random
from time import sleep
import logging
import argparse
import re
from dotenv import load_dotenv

from scraper import obtain_spotify_metadata
from matcher import find_match
from downloader import download_audio, apply_tags
from utils import get_urls_from_txt

from song_scraper import obtain_song_metadata


load_dotenv()

def setup_logger(error_file, debug):
    """
    Configure and return the root logger for the application.

    Sets up two handlers:
    - A console handler that prints logs to stdout (level depends on `debug`).
    - A file handler that writes only WARNING+ level logs to `error_file`,
      so errors can be reviewed later without scrolling through console output.

    ### Arguments
    - error_file: path to the file where warnings/errors will be logged (str)
    - debug: if True, sets console logging level to DEBUG instead of INFO (bool)

    ### Returns
    - configured root logger (logging.Logger)
    """

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    formatter = logging.Formatter("[%(levelname)s] %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(formatter)

    # Error file
    file_handler = logging.FileHandler(error_file, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def run_playlist_mode():
    """
    Main execution pipeline for downloading and processing a Spotify playlist.

    This function:
    - Loads configuration paths from environment variables
    - Reads playlist URL and previously downloaded songs
    - Scrapes Spotify metadata for each track
    - Finds the best matching YouTube Music result
    - Downloads the audio file
    - Applies ID3 metadata tags
    - Logs progress, errors, and completed downloads

    A randomized sleep is inserted between newly processed tracks (skipped
    tracks don't count towards this), and a longer break is taken every
    `SONGS_FOR_LONG_WAIT` tracks, to reduce the chance of rate limiting or
    an IP ban from YouTube/YouTube Music. All wait timings are configurable
    via environment variables.

    ### Environment Variables
    - BASE_DIR: base directory for all input/output files (default: "./data")
    - DEBUG: if set to "true"/"1" (case-insensitive), enables debug-level
      console logging (default: false)
    - PLAYLIST_URL: the Spotify playlist URL to download
    - START_SHORT_RANDOM_WAIT / END_SHORT_RANDOM_WAIT: range in seconds for
      the short wait between tracks (default: 5 / 20)
    - START_LONG_RANDOM_WAIT / END_LONG_RANDOM_WAIT: range in seconds for
      the long wait taken every `SONGS_FOR_LONG_WAIT` tracks (default: 60 / 300)
    - SONGS_FOR_LONG_WAIT: how many processed tracks between long waits (default: 50)

    ### Files used
    - downloaded.txt: list of already processed track URLs, used to skip
      tracks on subsequent runs
    - download folder: where MP3 files are saved
    - error.txt: log file for warnings and errors

    ### Returns
    - None
    """

    BASE_DIR = os.getenv("BASE_DIR", "./data")
    PLAYLIST_URL = os.getenv("PLAYLIST_URL")

    START_SHORT_RANDOM_WAIT = float(os.getenv("START_SHORT_RANDOM_WAIT", 5))
    END_SHORT_RANDOM_WAIT = float(os.getenv("END_SHORT_RANDOM_WAIT", 20))
    START_LONG_RANDOM_WAIT = float(os.getenv("START_LONG_RANDOM_WAIT", 60))
    END_LONG_RANDOM_WAIT = float(os.getenv("END_LONG_RANDOM_WAIT", 300))
    SONGS_FOR_LONG_WAIT = int(os.getenv("SONGS_FOR_LONG_WAIT", 50))

    DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "downloads")
    DOWNLOADED_FILE = os.path.join(BASE_DIR, "downloaded.txt")
    UNMATCHED_FILE = os.path.join(BASE_DIR, "unmatched.txt")

    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


    logger = logging.getLogger(__name__)

    logger.info(f"Downloading: {PLAYLIST_URL}")

    # Scrape all track metadata from the playlist and load the list of
    # tracks already downloaded in previous runs, to avoid duplicate work.
    playlist = obtain_spotify_metadata(PLAYLIST_URL)
    downloaded = get_urls_from_txt(DOWNLOADED_FILE)

    song_count = 0
    errors = 0

    i = 1

    with open(UNMATCHED_FILE, "w", encoding="utf-8") as unmatched_file:
        for metadata in playlist:

            logger.info("============================================================")
            logger.info(f"Processing: {metadata['song_url']}")

            if metadata['song_url'] in downloaded:
                logger.info(f"{metadata['song_url']} already downloaded. Skipping.")
                continue

            logger.debug("=== Metadata Found ===")
            logger.debug(f"   Song: {metadata['title']}")
            logger.debug(f"   Artists: {metadata['artists']}")
            logger.debug(f"   Cover: {metadata['cover_url']}")
            logger.debug(f"   Album: {metadata['album_name']}")
            logger.debug(f"   Track Number: {metadata['album_track']}")
            logger.debug(f"   Release Date: {metadata['release_date']}")
            logger.debug(f"   Duration: {metadata['duration']}")

            # Randomized delay between tracks to avoid triggering rate limits
            # or an IP ban. Every SONGS_FOR_LONG_WAIT tracks, take a longer break.
            if i % SONGS_FOR_LONG_WAIT == 0:
                wait_time = random.uniform(START_LONG_RANDOM_WAIT, END_LONG_RANDOM_WAIT)
            else:
                wait_time = random.uniform(START_SHORT_RANDOM_WAIT, END_SHORT_RANDOM_WAIT)

            logger.info(f"Sleeping {wait_time:.1f}s to avoid IP ban.")
            sleep(wait_time)

            i += 1

            # Find the best matching audio source on YouTube Music (or YouTube
            # as a fallback) based on the Spotify metadata.
            match = find_match(metadata)

            if not match:
                logger.warning(f"Failed to find a match for '{metadata['song_url']}'.")
                errors += 1

                unmatched_file.write(f"{metadata['song_url']},{metadata['title']} - {metadata['artists'][0]}\n")
                
                continue

            # Download the matched audio and tag it with the original
            # Spotify metadata (title, artists, album, cover, etc.).
            file_path = download_audio(metadata, match['id'], DOWNLOAD_FOLDER)

            if not file_path:
                logger.error(f"Failed to download audio for '{metadata['song_url']}'")
                errors += 1
                continue

            if not apply_tags(file_path, metadata):
                logger.error(f"Failed to apply metadata for '{metadata['song_url']}'")
                errors += 1
                continue

            # Record this track as downloaded so future runs can skip it.
            with open(DOWNLOADED_FILE, "a", encoding="utf-8") as f:
                f.write(metadata['song_url'] + "\n")

            song_count += 1

        logger.info(f"Playlist download completed! Downloaded {song_count} new songs.")

        if errors:
            logger.warning(f"Process completed with {errors} errors.")


def run_unmatched_mode():
    """
    Manual resolution mode: reads Spotify tracks that failed to auto-match
    from <BASE_DIR>/unmatched.txt, prompts the user for a YouTube URL for
    each one, downloads and tags the audio, and rewrites the file keeping
    only the tracks that are still unresolved (skipped or failed).
    """

    logger = logging.getLogger(__name__)

    BASE_DIR = os.getenv("BASE_DIR", "./data")
    DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "downloads")
    DOWNLOADED_FILE = os.path.join(BASE_DIR, "downloaded.txt")
    UNMATCHED_FILE = os.path.join(BASE_DIR, "unmatched.txt")

    if not os.path.exists(UNMATCHED_FILE):
        print(f"No unmatched file found at '{UNMATCHED_FILE}'.")
        return

    with open(UNMATCHED_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    still_unmatched = []

    for line in lines:
        spotify_url, query = line.split(",", 1)
        print(f"\n{query}")
        print(spotify_url)
        youtube_url = input("YouTube URL (leave empty to skip): ").strip()

        if not youtube_url:
            still_unmatched.append(line)
            continue

        video_id_match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", youtube_url)
        if not video_id_match:
            print("Invalid YouTube URL, skipped.")
            still_unmatched.append(line)
            continue
        video_id = video_id_match.group(1)

        metadata = obtain_song_metadata(spotify_url)
        if not metadata:
            logger.error(f"Failed to scrape metadata for '{spotify_url}'")
            still_unmatched.append(line)
            continue

        file_path = download_audio(metadata, video_id, DOWNLOAD_FOLDER)
        if not file_path:
            logger.error(f"Failed to download audio for '{spotify_url}'")
            still_unmatched.append(line)
            continue

        if not apply_tags(file_path, metadata):
            logger.error(f"Failed to apply metadata for '{spotify_url}'")
            still_unmatched.append(line)
            continue

        with open(DOWNLOADED_FILE, "a", encoding="utf-8") as f:
            f.write(metadata['song_url'] + "\n")

        print(f"Done: {file_path}")

    # Rewrite the file with only the tracks still pending resolution
    with open(UNMATCHED_FILE, "w", encoding="utf-8") as f:
        for line in still_unmatched:
            f.write(line + "\n")

    logger.info(f"Resolved {len(lines) - len(still_unmatched)} of {len(lines)} unmatched tracks.")


def run_manual_mode(spotify_url, youtube_url):
    """
    Manual mode: match a specific Spotify track to a specific YouTube video,
    bypassing the automatic matcher entirely. Useful for fixing an
    incorrect auto-match or resolving a track by hand outside the
    unmatched.txt workflow.

    ### Arguments
    - spotify_url: Spotify track URL (str)
    - youtube_url: YouTube video URL to use as the audio source (str)

    ### Returns
    - None
    """

    logger = logging.getLogger(__name__)

    BASE_DIR = os.getenv("BASE_DIR", "./data")
    DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "downloads")
    DOWNLOADED_FILE = os.path.join(BASE_DIR, "downloaded.txt")

    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    video_id_match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", youtube_url)
    if not video_id_match:
        logger.error(f"Invalid YouTube URL: '{youtube_url}'")
        return
    video_id = video_id_match.group(1)

    metadata = obtain_song_metadata(spotify_url)
    if not metadata:
        logger.error(f"Failed to scrape metadata for '{spotify_url}'")
        return

    file_path = download_audio(metadata, video_id, DOWNLOAD_FOLDER)
    if not file_path:
        logger.error(f"Failed to download audio for '{spotify_url}'")
        return

    if not apply_tags(file_path, metadata):
        logger.error(f"Failed to apply metadata for '{spotify_url}'")
        return

    with open(DOWNLOADED_FILE, "a", encoding="utf-8") as f:
        f.write(metadata['song_url'] + "\n")

    logger.info(f"Done: {file_path}")


def build_parser():
    parser = argparse.ArgumentParser(description="Spotify Downloader")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    subparsers.add_parser("playlist", help="Download a full playlist (default pipeline)")
    subparsers.add_parser("unmatched", help="Manually resolve unmatched tracks from a file")

    manual_parser = subparsers.add_parser("manual", help="Manually match a single Spotify track to a YouTube video")
    manual_parser.add_argument("spotify_url", help="Spotify track URL")
    manual_parser.add_argument("youtube_url", help="YouTube video URL to use as the audio source")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    BASE_DIR = os.getenv("BASE_DIR", "./data")
    DEBUG = os.getenv("DEBUG", "false").strip().lower() in ("1", "true", "yes")
    ERROR_FILE = os.path.join(BASE_DIR, "error.txt")
    os.makedirs(BASE_DIR, exist_ok=True)

    setup_logger(ERROR_FILE, DEBUG)

    if args.mode == "playlist":
        run_playlist_mode()
    elif args.mode == "unmatched":
        run_unmatched_mode()
    elif args.mode == "manual":
        run_manual_mode(args.spotify_url, args.youtube_url)


if __name__ == "__main__":
    main()
