# Spotify Downloader
Automatically downloads Spotify playlists by finding and fetching matching audio from YouTube, with smart matching and full metadata tagging (title, artists, album, cover art, release date). Playlist data is scraped directly from the Spotify web player — no Spotify API or API key required.

## Installation

Build from source
```bash
git clone https://github.com/DoctorPatita/spotify-downloader.git
cd spotify-downloader
```
I recommend using a venv.
```bash
python -m venv venv
```
Windows:
```powershell
venv\Scripts\Activate.ps1
```
Linux/macOS:
```bash
source venv/bin/activate
```
then
```bash
pip install -r requirements.txt
playwright install --with-deps chromium
```

### Installing FFmpeg

FFmpeg is required (because of yt-dlp).
To install FFmpeg system-wide follow these instructions
- [Windows Tutorial](https://windowsloop.com/install-ffmpeg-windows-10/)
- OSX - `brew install ffmpeg`
- Linux - `sudo apt install ffmpeg` or use your distro's package manager

### Installing Deno

Deno is required for yt-dlp to solve YouTube's JS signature challenges.
- [Official install instructions](https://docs.deno.com/runtime/getting_started/installation/)
- OSX/Linux:
```bash
curl -fsSL https://deno.land/install.sh | sh
```

## Configuration

Copy `.env.example` to `.env` and fill in your playlist URL:
```bash
cp .env.example .env
```
| Variable | Description | Default |
|---|---|---|
| `PLAYLIST_URL` | Spotify playlist URL to download | *(required)* |
| `BASE_DIR` | Base directory for downloads, logs and cookies | `./data` |
| `DEBUG` | Enables debug-level console logging (`true`/`false`) | `false` |
| `START_SHORT_RANDOM_WAIT` / `END_SHORT_RANDOM_WAIT` | Range in seconds for the wait between tracks | `5` / `20` |
| `START_LONG_RANDOM_WAIT` / `END_LONG_RANDOM_WAIT` | Range in seconds for the longer periodic wait | `60` / `300` |
| `SONGS_FOR_LONG_WAIT` | How many tracks between long waits | `50` |

### Cookies (optional)

Downloading works without cookies, but providing them can help avoid YouTube bot checks and improve reliability. To use them, place a `cookies.txt` file at `<BASE_DIR>/cookies.txt`.

You can generate this file directly with `yt-dlp` while logged into YouTube in your browser:

```bash
yt-dlp --cookies-from-browser firefox --cookies cookies.txt || true
```

Replace `firefox` with your browser if you're using a different one (e.g. `chrome`, `edge`, `brave`). See the [yt-dlp cookies documentation](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp) for more details and supported browsers.

Alternatively, you can export cookies manually using a browser extension like [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).

## Usage

Put your playlist URL in the `.env` file, then run one of the following modes:

```bash
# Download the full playlist (default pipeline)
python main.py playlist

# Manually resolve tracks that failed to auto-match, reading them from
# <BASE_DIR>/unmatched.txt and prompting for a YouTube URL for each one
python main.py unmatched

# Manually match a single Spotify track to a specific YouTube video,
# useful for fixing an incorrect auto-match
python main.py manual "<spotify_track_url>" "<youtube_video_url>"
```
## Running with Docker

Visit the [Docker Hub Page](https://hub.docker.com/r/doctorpatita/spotify-downloader)

A `Dockerfile` and `docker-compose.yml` are included, so you don't need to install FFmpeg, Deno, or Playwright browsers manually — they're already set up in the image.

Default behavior (`docker compose up` runs the `playlist` mode):
```bash
docker compose up -d
```

Other modes can be run as one-off, interactive commands, overriding the default:
```bash
# Manually resolve unmatched tracks
docker compose run --rm -it spotify-downloader unmatched

# Manually match a single track
docker compose run --rm -it spotify-downloader manual "https://open.spotify.com/track/XXXX" "https://www.youtube.com/watch?v=YYYY"
```
Configuration is passed the same way, via environment variables in `docker-compose.yml` or an `.env` file referenced by it.
## Credits
This project is inspired by [spotDL/spotify-downloader](https://github.com/spotDL/spotify-downloader), under the MIT license.
## License
This project is licensed under the [MIT License](LICENSE).
