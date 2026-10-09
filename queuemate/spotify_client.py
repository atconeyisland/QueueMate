"""Spotify Web API integration for QueueMate's first CLI milestone."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import spotipy
from dotenv import load_dotenv
from spotipy.cache_handler import CacheFileHandler
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

LOGGER = logging.getLogger(__name__)
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = " ".join(
    (
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "user-library-read",
        "playlist-read-private",
        "playlist-read-collaborative",
    )
)


class SpotifyClientError(RuntimeError):
    """A safe, user-facing Spotify or configuration error."""


def _data_dir() -> Path:
    """Return a per-user directory for Spotify's OAuth token cache."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    path = Path(base) / "QueueMate"
    path.mkdir(parents=True, exist_ok=True)
    return path


class SpotifyClient:
    """Small wrapper that keeps Spotify API calls inside this module."""

    def __init__(self) -> None:
        """Load credentials and initialize Spotipy's Authorization Code flow."""
        load_dotenv()
        client_id = os.getenv("SPOTIPY_CLIENT_ID", "").strip()
        client_secret = os.getenv("SPOTIPY_CLIENT_SECRET", "").strip()
        redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI", REDIRECT_URI).strip()
        if not client_id or not client_secret:
            raise SpotifyClientError(
                "Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET in .env first."
            )
        if redirect_uri != REDIRECT_URI:
            raise SpotifyClientError(
                f"SPOTIPY_REDIRECT_URI must be exactly {REDIRECT_URI}."
            )

        auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=REDIRECT_URI,
            scope=SCOPES,
            cache_handler=CacheFileHandler(cache_path=str(_data_dir() / ".token-cache")),
            open_browser=True,
        )
        # Spotipy retries 429/5xx responses and honors Retry-After for 429s.
        self._spotify = spotipy.Spotify(
            auth_manager=auth_manager,
            requests_timeout=15,
            retries=3,
            status_forcelist=(429, 500, 502, 503, 504),
            backoff_factor=0.5,
        )

    def queue_track(self, query: str) -> dict[str, str]:
        """Find the best catalog result for *query* and append it to the queue.

        Returns a small track description for the CLI/UI. Spotify only permits
        appending to the end of the queue; this method does not imply reordering.
        """
        query = query.strip()
        if not query:
            raise SpotifyClientError("Give me a song title to queue.")
        try:
            response = self._spotify.search(q=query, type="track", limit=5)
            tracks = response.get("tracks", {}).get("items", [])
            if not tracks:
                raise SpotifyClientError(f"No Spotify track found for ‘{query}’.")
            track: dict[str, Any] = tracks[0]
            self._spotify.add_to_queue(track["uri"])
            artists = ", ".join(artist["name"] for artist in track.get("artists", []))
            return {
                "title": track.get("name", "Unknown title"),
                "artist": artists or "Unknown artist",
                "uri": track["uri"],
            }
        except SpotifyClientError:
            raise
        except SpotifyException as exc:
            LOGGER.warning("Spotify request failed with HTTP status %s", exc.http_status)
            if exc.http_status == 401:
                raise SpotifyClientError(
                    "Spotify authorization expired. Run the command again to sign in."
                ) from None
            if exc.http_status == 403:
                raise SpotifyClientError(
                    "Spotify denied queue access. Check Premium and the app's allowed users."
                ) from None
            if exc.http_status == 404:
                raise SpotifyClientError(
                    "No active Spotify device. Open Spotify on any device and try again."
                ) from None
            if exc.http_status == 429:
                raise SpotifyClientError(
                    "Spotify is rate limiting requests. Wait a moment and try again."
                ) from None
            raise SpotifyClientError(
                "Spotify could not complete that request. Check your connection and try again."
            ) from None
        except (OSError, TimeoutError) as exc:
            LOGGER.warning("Spotify network request failed: %s", type(exc).__name__)
            raise SpotifyClientError(
                "Could not reach Spotify. Check your internet connection and try again."
            ) from None


def queue_track(query: str) -> dict[str, str]:
    """Authenticate and queue a track matching *query*."""
    return SpotifyClient().queue_track(query)
