"""Command-line smoke test for QueueMate's Spotify queue integration."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from .spotify_client import SpotifyClient, SpotifyClientError


def _configure_logging() -> None:
    """Write concise logs to the console and the per-user log file."""
    log_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "QueueMate"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_dir / "queuemate.log", encoding="utf-8")],
    )


def main() -> int:
    """Parse and execute the `queue` CLI command."""
    parser = argparse.ArgumentParser(prog="python -m queuemate.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    queue_parser = subparsers.add_parser("queue", help="search Spotify and queue a track")
    queue_parser.add_argument("query", nargs="+", help="track title and optional artist")
    args = parser.parse_args()

    _configure_logging()
    try:
        result = SpotifyClient().queue_track(" ".join(args.query))
    except SpotifyClientError as exc:
        print(f"QueueMate: {exc}")
        return 1
    except Exception as exc:
        logging.getLogger(__name__).exception("Unexpected Spotify client failure (%s)", type(exc).__name__)
        print("QueueMate: Something went wrong while contacting Spotify. See the log for details.")
        return 1

    print(f"Queued at the end: {result['title']} — {result['artist']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
