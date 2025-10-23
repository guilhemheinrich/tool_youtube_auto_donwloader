#!/usr/bin/env python3
"""
YouTube Auto Downloader - Pull Module
Downloads YouTube videos/playlists as audio files.
All .opus files are stored directly in the output directory.
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL


class DownloadTracker:
    """Manages download history to avoid re-downloading the same content."""

    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.downloaded_videos: dict[str, str] = self._load_history()

    def _load_history(self) -> dict[str, str]:
        """Load previously downloaded video IDs and their directory names from history file."""
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
        """Save downloaded video IDs and directory names to history file."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump({"downloaded_videos": self.downloaded_videos}, f, indent=2)
        except OSError as e:
            print(f"Warning: Could not save history: {e}", file=sys.stderr)

    def is_downloaded(self, video_id: str) -> bool:
        """Check if a video ID has already been downloaded."""
        return video_id in self.downloaded_videos

    def get_dirname(self, video_id: str) -> str | None:
        """Get the directory name for a downloaded video ID."""
        return self.downloaded_videos.get(video_id)

    def mark_downloaded(self, video_id: str, dirname: str) -> None:
        """Mark a video ID as downloaded with its directory name and save to history."""
        self.downloaded_videos[video_id] = dirname
        self._save_history()


class YouTubePuller:
    """Handles pulling and downloading YouTube content."""

    def __init__(self, output_dir: Path, tracker: DownloadTracker):
        self.output_dir = output_dir
        self.tracker = tracker
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = None

    def _create_temp_dir(self) -> Path:
        """Create a temporary directory for downloads."""
        if self.temp_dir is None:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="yt_download_"))
        return self.temp_dir

    def _cleanup_temp_dir(self) -> None:
        """Clean up the temporary directory."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
            except OSError as e:
                print(f"Warning: Could not clean up temp directory {self.temp_dir}: {e}", file=sys.stderr)

    def _get_ydl_opts(self, output_dir: Path, video_folder: str) -> dict[str, Any]:
        """Build yt-dlp options for audio download with metadata."""
        return {
            "paths": {"home": str(output_dir / video_folder)},
            "outtmpl": {"default": "%(id)s - %(title)s.%(ext)s"},
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
            "writeinfojson": True,
            "ignoreerrors": True,
            "no_warnings": False,
            "extract_flat": False,
        }

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

    def _extract_video_title(self, video_id: str, video_title: str = "") -> str | None:
        """Extract video title from YouTube."""
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            with YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                info = ydl.extract_info(video_url, download=False)
                if not info:
                    return None
                return info.get("title", video_title or "Unknown")
        except Exception as e:
            print(f"  ✗ Error extracting info for {video_id}: {e}", file=sys.stderr)
            return None

    def _download_to_temp(self, video_url: str, temp_video_dir: Path, folder_name: str) -> bool:
        """Download video to temporary directory."""
        ydl_opts = self._get_ydl_opts(temp_video_dir.parent, folder_name)
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            return True
        except Exception as e:
            print(f"  ✗ Error downloading: {e}", file=sys.stderr)
            return False

    def _verify_and_move_files(self, video_id: str, temp_video_dir: Path, final_file: Path) -> bool:
        """Verify .opus file exists and move to final location."""
        # Check if .opus file was created successfully
        opus_files = list(temp_video_dir.glob("*.opus"))
        if not opus_files:
            print(f"  ✗ No .opus file created for {video_id}", file=sys.stderr)
            return False

        # Move the .opus file to final location
        opus_file = opus_files[0]  # Take the first (and should be only) .opus file
        if final_file.exists():
            final_file.unlink()
        shutil.move(str(opus_file), str(final_file))

        # Verify the .opus file exists in the final location
        if not final_file.exists():
            print(f"  ✗ .opus file not found in final location for {video_id}", file=sys.stderr)
            return False

        return True

    def _download_video(self, video_id: str, video_title: str = "") -> str | None:
        """
        Download a single video as audio to the output directory.
        Returns the filename if successful, None otherwise.
        """
        if self.tracker.is_downloaded(video_id):
            print(f"  Already downloaded: {video_id}")
            return self.tracker.get_dirname(video_id)

        # Extract video title
        title = self._extract_video_title(video_id, video_title)
        if not title:
            return None

        # Create filename
        filename = f"{self._sanitize_name(title)}.{video_id}.opus"
        final_file = self.output_dir / filename
        temp_dir = self._create_temp_dir()
        temp_video_dir = temp_dir / f"{self._sanitize_name(title)}.{video_id}"

        video_url = f"https://www.youtube.com/watch?v={video_id}"

        try:
            # Download to temporary directory
            if not self._download_to_temp(video_url, temp_video_dir, f"{self._sanitize_name(title)}.{video_id}"):
                return None

            # Verify and move files
            if not self._verify_and_move_files(video_id, temp_video_dir, final_file):
                return None

            # Only mark as downloaded if everything succeeded
            self.tracker.mark_downloaded(video_id, filename)
            print(f"  ✓ Downloaded: {filename}")
            return filename

        except Exception as e:
            print(f"  ✗ Error downloading {video_id}: {e}", file=sys.stderr)
            # Clean up any partial files
            if final_file.exists():
                final_file.unlink()
            return None
        finally:
            # Clean up temporary directory for this video
            if temp_video_dir.exists():
                shutil.rmtree(temp_video_dir)

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
        print(f"Output directory: {self.output_dir}")

        # Download each video
        for i, entry in enumerate(entries, 1):
            if not entry:
                continue

            video_id = entry.get("id")
            video_title = entry.get("title", "Unknown")

            if not video_id:
                print(f"[{i}/{len(entries)}] Skipping: no video ID")
                continue

            print(f"\n[{i}/{len(entries)}] {video_title} ({video_id})")

            # Download video
            self._download_video(video_id, video_title)

        print(f"\n✓ Finished processing playlist: {playlist_title}")
        print(f"  Total videos in playlist: {len(entries)}")

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
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Initialize tracker and puller
    tracker = DownloadTracker(args.history_file)
    puller = YouTubePuller(args.output_dir, tracker)

    try:
        # Pull content
        puller.pull(args.url)
    finally:
        # Clean up temporary directory at the end of the run
        puller._cleanup_temp_dir()

    print("\n" + "=" * 60)
    print("Download complete!")
    print(f"Total videos in library: {len(tracker.downloaded_videos)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
