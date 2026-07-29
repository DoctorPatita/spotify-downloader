"""
Utils module, general-purpose helpers used across the project: fuzzy
text matching (with Japanese transliteration support), URL list handling,
and string splitting.
"""

from rapidfuzz import fuzz
from pykakasi import kakasi
from slugify import slugify
import re
import os
import logging


logger = logging.getLogger(__name__)

# Matches Japanese script characters (hiragana, katakana, kanji, full-width
# forms), used to detect strings that need romaji transliteration before
# fuzzy comparison.
JAP_REGEX = re.compile(
    "[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]"
)

# Characters allowed to survive slugify()'s cleanup during ratio() comparisons
DISALLOWED_REGEX = re.compile(r"[^-a-zA-Z0-9\!\@\$]+")


# kakasi instance reused across calls to convert_japanese, since creating
# it has some overhead and it holds no per-call state
kks = kakasi()
def convert_japanese(string):
    """
    Convert Japanese text to romaji (Hepburn transcription)

    ### Arguments
    - string: input string containing Japanese characters (str)

    ### Returns
    - romaji-transliterated string (str)
    """
    results = kks.convert(string)
    romaji_parts = [item["hepburn"] for item in results if item["hepburn"]]
    string = " ".join(romaji_parts)
    return string


def ratio(string1, string2):
    """
    Calculate similarity ratio between two strings

    ### Arguments
    - string1: first string (str)
    - string2: second string (str)

    ### Returns
    - similarity score between strings (float, 0–100)
    """

    japanese = False

    if JAP_REGEX.search(string1):
        string1 = convert_japanese(string1)
        japanese = True

    if JAP_REGEX.search(string2):
        string2 = convert_japanese(string2)
        japanese = True

    # Sort alphabetically strings to solve things like: string1 = Wada Naoya, string2 = Naoya Wada
    if japanese:
        string1 = " ".join(sorted(string1.split()))
        string2 = " ".join(sorted(string2.split()))

    string1 = slugify(string1, regex_pattern=DISALLOWED_REGEX.pattern)
    string2 = slugify(string2, regex_pattern=DISALLOWED_REGEX.pattern)

    return fuzz.ratio(string1, string2)


def get_urls_from_txt(file_path):
    """
    Read a plain text file where each line is a Spotify URL.
    Returns a set of clean, unique URLs.

    ### Arguments
    - file_path: path to the input text file (str)

    ### Returns
    - set of unique URLs (set[str])
      OR empty list if file does not exist
    """

    urls = set()
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # .strip() removes whitespace and newline characters from start/end
                    clean_url = line.strip()
                    if clean_url:  # Only if the line is not empty
                        if clean_url not in urls:
                            urls.add(clean_url)
                        else:
                            logger.warning(f"Duplicate song detected: {clean_url}. Skipping...")

            logger.info(f"Loaded {len(urls)} songs from '{file_path}'.")
            return urls
        else:
            return []
    except Exception as e:
        logger.error(f"[ERROR] Failed to read '{file_path}': {e}")
        raise FileNotFoundError(e)


def split_on_commas(text):
    """
    Split a string by Japanese and standard commas

    ### Arguments
    - text: input string (str)

    ### Returns
    - list of cleaned substrings (list[str])
    """

    parts = re.split(r'[、,]', text)
    return [p.strip() for p in parts if p.strip()]
