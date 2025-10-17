#!/usr/bin/env python3
"""
YouTube Auto Downloader - Pull Module
Downloads YouTube videos/playlists as audio files.
Uses symlinks for playlists to avoid duplicate downloads.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL


class DownloadTracker:
    """Manages download history to avoid re-downloading the same content."""

    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.downloaded_videos: dict[str, str] = self._load_history()

    def _load_history(self) -> dict[str, str]:
        """Load previously downloaded video IDs and their filenames from history file."""
        if not self.history_file.exists():
            return {}
        try:
            with open(self.history_file, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("downloaded_videos", {})
        except (json.JSONDecodeError, OSError):
            print(f"Warning: Could not load history from {self.history_file}", file=sys.stderr)
            return {}

    def _save_history(self) -> None:
        """Save downloaded video IDs and filenames to history file."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump({"downloaded_videos": self.downloaded_videos}, f, indent=2)
        except OSError as e:
            print(f"Warning: Could not save history: {e}", file=sys.stderr)

    def is_downloaded(self, video_id: str) -> bool:
        """Check if a video ID has already been downloaded."""
        return video_id in self.downloaded_videos

    def get_filename(self, video_id: str) -> str | None:
        """Get the filename for a downloaded video ID."""
        return self.downloaded_videos.get(video_id)

    def mark_downloaded(self, video_id: str, filename: str) -> None:
        """Mark a video ID as downloaded with its filename and save to history."""
        self.downloaded_videos[video_id] = filename
        self._save_history()


class YouTubePuller:
    """Handles pulling and downloading YouTube content."""

    def __init__(self, output_dir: Path, tracker: DownloadTracker, playlist_as_album: bool = False):
        self.output_dir = output_dir
        self.tracker = tracker
        self.playlist_as_album = playlist_as_album
        self.all_videos_dir = output_dir / "_all_videos"
        self.all_videos_dir.mkdir(parents=True, exist_ok=True)

    def _get_ydl_opts(self, output_dir: Path, filename_template: str, album: str | None = None) -> dict[str, Any]:
        """Build yt-dlp options for audio download with metadata."""
        opts = {
            "paths": {"home": str(output_dir)},
            "outtmpl": {"default": filename_template},
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "opus",
                    "preferredquality": "0",
                },
                {"key": "FFmpegMetadata"},
                {"key": "EmbedThumbnail"},
            ],
            "writethumbnail": True,
            "writeinfojson": False,
            "ignoreerrors": True,
            "no_warnings": False,
            "extract_flat": False,
        }

        # Add album metadata if specified
        if album:
            opts["postprocessor_args"] = {"ffmpeg": ["-metadata", f"album={album}"]}

        return opts

    def _extract_info(self, url: str, extract_flat: bool = False) -> dict[str, Any] | None:
        """Extract video/playlist information."""
        ydl_opts = {
            "quiet": True,
            "extract_flat": "in_playlist" if extract_flat else False,
            "skip_download": True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"Error extracting info from {url}: {e}", file=sys.stderr)
            return None

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for use as directory/file name."""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, "_")
        return name.strip()[:200]

    def _download_video(self, video_id: str, video_title: str = "", album: str | None = None) -> str | None:
        """
        Download a single video as audio to the _all_videos directory.
        Filename format: Title.VIDEO_ID.opus
        Returns the filename if successful, None otherwise.
        """
        if self.tracker.is_downloaded(video_id):
            print(f"  Already downloaded: {video_id}")
            return self.tracker.get_filename(video_id)

        video_url = f"https://www.youtube.com/watch?v={video_id}"

        # First extract info to get the title
        try:
            with YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                info = ydl.extract_info(video_url, download=False)
                if not info:
                    return None
                title = info.get("title", video_title or "Unknown")
        except Exception as e:
            print(f"  ✗ Error extracting info for {video_id}: {e}", file=sys.stderr)
            return None

        # Create filename: Title.VIDEO_ID.ext
        sanitized_title = self._sanitize_name(title)
        filename_template = f"{sanitized_title}.{video_id}.%(ext)s"
        ydl_opts = self._get_ydl_opts(self.all_videos_dir, filename_template, album=album)

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

                # The final filename will be Title.VIDEO_ID.opus
                final_filename = f"{sanitized_title}.{video_id}.opus"
                self.tracker.mark_downloaded(video_id, final_filename)
                print(f"  ✓ Downloaded: {final_filename}")
                return final_filename

        except Exception as e:
            print(f"  ✗ Error downloading {video_id}: {e}", file=sys.stderr)
            return None

    def pull_single_video(self, url: str) -> None:
        """Download a single video."""
        print("\n=== Processing single video ===")
        print(f"URL: {url}")

        info = self._extract_info(url)
        if not info:
            print("Could not extract video information")
            return

        video_id = info.get("id")
        if not video_id:
            print("Could not get video ID")
            return

        print(f"Video: {info.get('title', 'Unknown')}")
        self._download_video(video_id)
        print("\n✓ Finished processing video")

    def pull_playlist(self, url: str) -> None:
        """Download all videos from a playlist."""
        print("\n=== Processing playlist ===")
        print(f"URL: {url}")

        # Extract playlist info
        info = self._extract_info(url, extract_flat=True)
        if not info:
            print("Could not extract playlist information")
            return

        playlist_title = info.get("title", "Unknown Playlist")
        entries = info.get("entries", [])

        if not entries:
            print("No videos found in playlist")
            return

        print(f"Playlist: {playlist_title}")
        print(f"Found {len(entries)} videos")

        # Use playlist title as album if option is enabled
        album = playlist_title if self.playlist_as_album else None
        if album:
            print(f"Album metadata will be set to: {album}")

        # Download each video
        downloaded_count = 0
        skipped_count = 0

        for i, entry in enumerate(entries, 1):
            if not entry:
                continue

            video_id = entry.get("id")
            video_title = entry.get("title", "Unknown")

            if not video_id:
                print(f"[{i}/{len(entries)}] Skipping: no video ID")
                continue

            print(f"\n[{i}/{len(entries)}] {video_title} ({video_id})")

            # Download to _all_videos with album metadata if enabled
            was_already_downloaded = self.tracker.is_downloaded(video_id)
            filename = self._download_video(video_id, video_title, album=album)

            if filename:
                if was_already_downloaded:
                    skipped_count += 1
                else:
                    downloaded_count += 1

        print(f"\n✓ Finished processing playlist: {playlist_title}")
        print(f"  Total videos in playlist: {len(entries)}")
        print(f"  Downloaded: {downloaded_count}")
        print(f"  Skipped (already downloaded): {skipped_count}")

    def pull(self, url: str) -> None:
        """Pull content from URL (auto-detect if video or playlist)."""
        info = self._extract_info(url, extract_flat=True)
        if not info:
            print("Error: Could not extract information from URL")
            sys.exit(1)

        # Check if it's a playlist
        if info.get("_type") == "playlist" or "entries" in info:
            self.pull_playlist(url)
        else:
            self.pull_single_video(url)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Download YouTube videos/playlists as audio files")
    parser.add_argument("url", help="YouTube URL (video or playlist)")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory (root folder for downloads)")
    parser.add_argument(
        "--history-file", required=True, type=Path, help="Path to history file (JSON) for tracking downloaded videos"
    )
    parser.add_argument(
        "--playlist-as-album",
        action="store_true",
        help="Set playlist title as album metadata for all videos in the playlist",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Initialize tracker and puller
    tracker = DownloadTracker(args.history_file)
    puller = YouTubePuller(args.output_dir, tracker, playlist_as_album=args.playlist_as_album)

    # Pull content
    puller.pull(args.url)

    print("\n" + "=" * 60)
    print("Download complete!")
    print(f"Total videos in library: {len(tracker.downloaded_videos)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
