"""
Matcher module, scores and selects the best YouTube/YouTube Music result
for a given Spotify track based on title, artist, album, and duration
similarity.
"""

from math import exp
from slugify import slugify
import logging

from searcher import search_ytmusic, search_ytmusic_artist_catalog, search_youtube
from utils import ratio, split_on_commas


logger = logging.getLogger(__name__)

# from spotdl and some of my own
HIGH_FORBIDDEN_WORDS = [
    "bassboosted",
    "remix",
    "reverb",
    "bassboost",
    "live",
    "acoustic",
    "8daudio",
    "concert",
    "acapella",
    "slowed",
    "instrumental",
    "cover",
    "sing-along",
    "version",
    "ver.",
    "karaoke",
    "en-vivo",
    "acustico",
    "vocalless",
    "8-bit",
]


LOW_FORBIDDEN_WORDS = [
    "mix",
    "remaster",
    "remastered",
    "remasterizado",
]


# from spotdl
def calc_time_match(duration1, duration2):
    """
    Calculate score based on time difference between 2 durations

    ### Arguments
    - duration1: first duration (int or float)
    - duration2: second duration (int or float)

    ### Returns
    - score based on time difference (0–100)
    """

    time_diff = abs(duration1 - duration2)
    score = exp(-0.1 * time_diff)
    return score * 100


def calc_title_match(song_title, result_title):
    """
    Calculate similarity score between song titles

    ### Arguments
    - song_title: original song title (str)
    - result_title: result song title (str)

    ### Returns
    - similarity score between titles (0–100)
    """
    
    score = ratio(song_title, result_title)

    song_title = slugify(song_title)
    result_title = slugify(result_title)

    if song_title in result_title or result_title in song_title:
        score = (score + 100) / 2

    for word in HIGH_FORBIDDEN_WORDS:
        if word in result_title and word not in song_title:
            score -= 15

    for word in LOW_FORBIDDEN_WORDS:
        if word in result_title and word not in song_title:
            score -= 5

    return score


def calc_album_match(song_album, result_album):
    """
    Calculate similarity score between album names

    ### Arguments
    - song_album: original album name (str)
    - result_album: result album name (str)

    ### Returns
    - similarity score between albums (0–100)
    """

    score = ratio(song_album, result_album)
    return score


def calc_artists_match(artists, result_artists, result_title):
    """
    Calculate similarity score between artist lists

    ### Arguments
    - artists: list of original artists (list[str])
    - result_artists: list of result artists (list[str])
    - result_title: result title (used to boost matches) (str)

    ### Returns
    - weighted similarity score (0–100)
    """

    main_artist_score = ratio(artists[0], result_artists[0])

    if slugify(artists[0]) in slugify(result_title):
        main_artist_score = max(65, (main_artist_score + 100) / 2)

    if slugify(artists[0]) in slugify(result_artists[0]) or slugify(result_artists[0]) in slugify(artists[0]):
        main_artist_score = max(65, (main_artist_score + 100) / 2)

    if len(artists) == 1:
        return main_artist_score

    other_artists_score = 0
    for artist in artists[1:]:
        max_score = -1

        for res_artist in result_artists:
            temp_score = ratio(artist, res_artist)

            if slugify(artist) in slugify(res_artist) or slugify(res_artist) in slugify(artist):
                temp_score = (temp_score + 100) / 2

            if temp_score > max_score:
                max_score = temp_score

        if slugify(artist) in slugify(result_title):
            max_score = max(65, (max_score + 100) / 2)

        other_artists_score += max_score 

    other_artists_score = other_artists_score / (len(artists) - 1)

    return 0.7 * main_artist_score + 0.3 * other_artists_score


def is_valid_match(title_score, artists_score, time_score):
    """
    Validate if a match meets minimum quality thresholds

    ### Arguments
    - title_score: title similarity score (int or float)
    - artists_score: artist similarity score (int or float)
    - time_score: duration similarity score (int or float)

    ### Returns
    - True if match is valid, False otherwise
    """

    if time_score >= 90:
        return title_score >= 50 and artists_score >= 50

    return (
        title_score >= 60 and
        artists_score >= 60 and
        time_score >= 25
    )


def find_match(metadata):
    """
    Find the best matching YouTube/YouTube Music song for a given track.

    Tries three strategies in order, stopping as soon as one produces a
    valid match:
    1. Direct search on YouTube Music using title + artists.
    2. Search within the primary artist's YouTube Music catalog, for
       songs that exist but aren't well-indexed by direct search.
    3. Fallback search on general YouTube (not YT Music), used as a last
       resort since it lacks reliable album data.

    ### Arguments
    - metadata: dictionary containing:
        - 'title': song title (str)
        - 'artists': list of artists (list[str])
        - 'duration': song duration (int or float)
        - 'album_name': album name (str)

    ### Returns
    - dict with match data:
        {
            'id': video id (str),
            'title': video title (str),
            'score': match score (float)
        }
      OR False if no valid match is found
    """

    required_keys = {"title", "artists", "duration", "album_name"}

    if not metadata or not required_keys.issubset(metadata):
        logger.error("Missing metadata. Unable to verify song.")
        return False

    # Limit to 3 artists, adding more can make results worse
    artist_list = metadata['artists'][:3]
    artists_str = ", ".join(artist_list)

    query = f"{metadata['title']} - {artists_str}"

    candidates = search_ytmusic(query)
    match = find_best(metadata, candidates)


    if not match:
        logger.info("No match on direct search. Trying artist catalog.")
        candidates = search_ytmusic_artist_catalog(metadata['artists'][0])
        match = find_best(metadata, candidates)

    if not match:
        logger.info("No match was found on YTMusic. Falling back to YouTube.")
        candidates = search_youtube(query)
        match = find_best(metadata, candidates)

    if not match:
        logger.warning(f"No match was found for '{query}'.")

    return match
    

def find_best(metadata, candidates):
    """
    Score a list of candidate results against the original track metadata
    and return the best match, if any candidate is good enough.

    Each candidate is scored as a weighted combination of title, artist,
    duration, and album similarity. The top result from search gets a
    +5 bonus (since search engines tend to already rank the best match
    first), and the first and second results are exempted from the
    strict `is_valid_match` threshold check to give search ranking some
    benefit of the doubt over the raw formula alone.

    ### Arguments
    - metadata: dictionary with original track metadata (see `find_match`)
      (dict)
    - candidates: list of candidate result dicts, each with keys:
      'id', 'title', 'artists', 'duration', 'album_name' (list[dict])

    ### Returns
    - dict with the best match:
        {
            'id': video id (str),
            'title': video title (str),
            'score': match score (float)
        }
      OR False if no candidate scores above the minimum threshold (65)
    """

    match_score = 0
    match_id = ""
    match_title = ""

    for idx, candidate in enumerate(candidates):
        
        title_match = calc_title_match(metadata['title'], candidate['title'])
        time_match = calc_time_match(metadata['duration'], candidate['duration'])
        album_match = calc_album_match(metadata['album_name'], candidate['album_name'])
        artists_match = calc_artists_match(metadata['artists'], candidate['artists'], candidate['title'])

        # if the artists score is below 60, split the YouTube artists to try to improve the results
        if artists_match < 60:
            split_result_artists = [
                item
                for res_artist in candidate['artists']
                for item in split_on_commas(res_artist)
            ]
            artists_match = calc_artists_match(metadata['artists'], split_result_artists, candidate['title'])


        total_score = title_match * 0.4 + artists_match * 0.3 + time_match * 0.2 + album_match * 0.1


        if idx == 0:
            # +5 bonus points to the first result
            total_score = min(100.0, total_score + 5)
        elif idx != 1:
            # Don't validate the first and second result
            if not is_valid_match(title_match, artists_match, time_match):
                total_score = 0.0

        logger.debug("-----------------------------------")
        logger.debug(f"Candidate: '{candidate['title']}'")
        logger.debug(f"ID: '{candidate['id']}'")
        logger.debug(f"Title score: {title_match}")
        logger.debug(f"Artists score: {artists_match}")
        logger.debug(f"Album score: {album_match}")
        logger.debug(f"Time scorecore: {time_match}")
        logger.debug(f"Total Score: {total_score}")

        if total_score > match_score:
            match_score = total_score
            match_id = candidate['id']
            match_title = candidate['title']


    if match_score <= 65:
        return False

    match = {
        'id': match_id,
        'title': match_title,
        'score': match_score,
    }

    logger.info(f"Match found: '{match['title']}'")
    logger.info(f"YouTube ID: '{match['id']}'")
    logger.info(f"Score: {match['score']}")

    return match
