"""
Downloader module, handles downloading matched audio from YouTube and
applying ID3 metadata tags (including cover art) to the resulting file.
"""

import yt_dlp
import os
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from mutagen.id3._frames import TIT2, TPE1, TALB, TRCK, TDRC, APIC
import requests
import logging

logger = logging.getLogger(__name__)


def download_audio(metadata, match_id, output_folder):
    """
    Download audio from YouTube Music using a matched video ID

    ### Arguments
    - metadata: dictionary containing:
        - 'title': song title (str)
        - 'artists': list of artists (list[str])
    - match_id: YouTube video ID of the matched song (str)
    - output_folder: directory where the audio file will be saved (str)

    ### Returns
    - file_path: path to the downloaded audio file (str)
      OR False if download fails
    """

    required_keys = {"title", "artists"}

    if not metadata or not required_keys.issubset(metadata):
        logger.error("Missing metadata. Unable to download audio.")
        return False

    clean_name = f"{metadata['artists'][0]} - {metadata['title']}"
    clean_name = "".join([c for c in clean_name if c.isalnum() or c in " -_()"])
    file_path = os.path.join(output_folder, clean_name)
    song_url = f"https://www.youtube.com/watch?v={match_id}"


    BASE_DIR = os.getenv("BASE_DIR", "./data")
    COOKIES_FILE = os.path.join(BASE_DIR, "cookies.txt")
    
    dl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{file_path}.%(ext)s',
        'quiet': False,
        'no_warnings': True,
        
        'add_metadata': False, 
        'writethumbnail': False,
        
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        "remote_components": ["ejs:github"],
    }

    if os.path.exists(COOKIES_FILE):
        dl_opts["cookiefile"] = COOKIES_FILE
        logger.info(f"Cookies file found at '{COOKIES_FILE}'")

    logger.info(f"Downloading audio file...")
    
    try:
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([song_url])
        
        logger.info("Download completed successfully")
        
        file_path = f"{file_path}.mp3"
        if not os.path.exists(file_path):
           logger.error(f"Downloaded file not found: {file_path}")
           return False

        return file_path

    except Exception as e:
        logger.error(f"Audio download failed: {e}")
        return False


def apply_tags(file_path, metadata):
    """
    Apply ID3 metadata tags and cover art to an MP3 file

    ### Arguments
    - file_path: path to the MP3 file (str)
    - metadata: dictionary containing:
        - 'title': song title (str)
        - 'artists': list of artists (list[str])
        - 'duration': song duration (int or float)
        - 'album_name': album name (str)
        - 'album_track': track number (str)
        - 'release_date': release date (str)
        - 'cover_url': url of the album cover (str)


    ### Returns
    - True if metadata applied successfully
      OR False if any error occurs
    """


    required_keys = {"title", "artists", "duration", "album_name", "album_track", "release_date", "cover_url"}

    if not metadata or not required_keys.issubset(metadata) or not file_path:
        logger.error("Missing metadata. Unable to apply tags.")
        return False

    logger.info(f"Applying metadata to file '{file_path}'...")

    try:
        try:
            audio = MP3(file_path, ID3=ID3)
        except Exception as e:
            logger.error(f"Failed to open file '{file_path}': {e}")
            logger.error(f"Failed to apply metadata")
            return False

        if audio.tags is None:
            audio.add_tags()

        # Delete all tags to start clean 
        audio.tags.clear()

        # --- TEXT-BASED TAGS ---
        
        # Song title (TIT2)
        audio.tags.add(TIT2(encoding=3, text=metadata['title']))

        # Artists (TPE1)
        audio.tags.add(TPE1(encoding=3, text=metadata['artists']))

        # Album (TALB)
        audio.tags.add(TALB(encoding=3, text=metadata['album_name']))
        
        # Track number (TRCK)
        audio.tags.add(TRCK(encoding=3, text=str(metadata['album_track'])))

        # Release date (TDRC)
        audio.tags.add(TDRC(encoding=3, text=metadata['release_date']))


        # --- COVER ART ---
        cover_url = metadata.get('cover_url')
        if cover_url:
            logger.info(f"Downloading cover from '{cover_url}'...")
            try:
                img_response = requests.get(cover_url)
                img_response.raise_for_status() # Verify that it was downloaded correctly

                # Inject the image (APIC)
                audio.tags.add(
                    APIC(
                        encoding=3,       # utf-8
                        mime='image/jpeg',
                        type=3,           # Front Cover
                        desc='Cover',
                        data=img_response.content
                    )
                )
            except Exception as e:
                logger.error(f"Failed to download cover image: {e}")
                return False

        # Save the changes
        audio.save()
        logger.info("Metadata applied successfully.")
        return True

    except Exception as e:
        logger.error(f"Failed to apply metadata: {e}")
        return False
