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
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from yt_dlp import YoutubeDL


class DownloadedVideo(BaseModel):
    """Represents a successfully downloaded video with metadata."""

    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Original video title")
    filename: str = Field(..., description="Downloaded filename")
    download_date: datetime = Field(default_factory=datetime.now, description="Date when the video was downloaded")
    album: str | None = Field(None, description="Album name if available")
    artist: str | None = Field(None, description="Artist name if available")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DownloadTracker:
    """Manages download history to avoid re-downloading the same content."""

    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.downloaded_videos: list[DownloadedVideo] = self._load_history()

    def _load_history(self) -> list[DownloadedVideo]:
        """Load previously downloaded videos from history file."""
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, encoding="utf-8") as f:
                data = json.load(f)
                if "downloaded_videos" in data and isinstance(data["downloaded_videos"], list):
                    # Convert ISO date strings back to datetime objects
                    videos = []
                    for video_data in data["downloaded_videos"]:
                        # Convert ISO date string back to datetime if it's a string
                        if isinstance(video_data.get("download_date"), str):
                            try:
                                video_data["download_date"] = datetime.fromisoformat(video_data["download_date"])
                            except ValueError:
                                # If parsing fails, use current time
                                video_data["download_date"] = datetime.now()
                        videos.append(DownloadedVideo(**video_data))
                    return videos
                return []
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not load history from {self.history_file}: {e}", file=sys.stderr)
            return []

    def _save_history(self) -> None:
        """Save downloaded videos to history file."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w", encoding="utf-8") as f:
                # Convert datetime objects to ISO strings for JSON serialization
                videos_data = []
                for video in self.downloaded_videos:
                    video_dict = video.model_dump()
                    # Convert datetime to ISO string
                    if "download_date" in video_dict:
                        video_dict["download_date"] = video_dict["download_date"].isoformat()
                    videos_data.append(video_dict)

                json.dump({"downloaded_videos": videos_data}, f, indent=2)
        except OSError as e:
            print(f"Warning: Could not save history: {e}", file=sys.stderr)

    def is_downloaded(self, video_id: str) -> bool:
        """Check if a video ID has already been downloaded."""
        return any(video.video_id == video_id for video in self.downloaded_videos)

    def get_filename(self, video_id: str) -> str | None:
        """Get the filename for a downloaded video ID."""
        for video in self.downloaded_videos:
            if video.video_id == video_id:
                return video.filename
        return None

    def mark_downloaded(
        self, video_id: str, title: str, filename: str, album: str | None = None, artist: str | None = None
    ) -> None:
        """Mark a video ID as downloaded with its metadata and save to history."""
        # Remove any existing entry for this video_id
        self.downloaded_videos = [v for v in self.downloaded_videos if v.video_id != video_id]

        # Add new entry
        new_video = DownloadedVideo(video_id=video_id, title=title, filename=filename, album=album, artist=artist)
        self.downloaded_videos.append(new_video)
        self._save_history()

    def get_downloaded_videos(self) -> list[DownloadedVideo]:
        """Get all downloaded videos."""
        return self.downloaded_videos.copy()

    def get_video_by_id(self, video_id: str) -> DownloadedVideo | None:
        """Get a specific downloaded video by ID."""
        for video in self.downloaded_videos:
            if video.video_id == video_id:
                return video
        return None

    def print_history(self) -> None:
        """Print a formatted history of downloaded videos."""
        if not self.downloaded_videos:
            print("No videos downloaded yet.")
            return

        print(f"\nDownload History ({len(self.downloaded_videos)} videos):")
        print("-" * 80)
        for video in sorted(self.downloaded_videos, key=lambda v: v.download_date, reverse=True):
            print(f"ID: {video.video_id}")
            print(f"Title: {video.title}")
            print(f"Filename: {video.filename}")
            print(f"Download Date: {video.download_date.strftime('%Y-%m-%d %H:%M:%S')}")
            if video.album:
                print(f"Album: {video.album}")
            if video.artist:
                print(f"Artist: {video.artist}")
            print("-" * 80)


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
            # Anti-detection options to avoid 403 errors
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "referer": "https://www.youtube.com/",
            "sleep_interval": 1,
            "max_sleep_interval": 5,
            "sleep_interval_requests": 1,
            "sleep_interval_subtitles": 1,
        }

    def _extract_info(self, url: str, extract_flat: bool = False) -> dict[str, Any] | None:
        """Extract video/playlist information."""
        ydl_opts = {
            "quiet": True,
            "extract_flat": "in_playlist" if extract_flat else False,
            "skip_download": True,
            # Anti-detection options to avoid 403 errors
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "referer": "https://www.youtube.com/",
            "sleep_interval": 1,
            "max_sleep_interval": 5,
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

    def _extract_metadata(self, video_id: str) -> dict[str, Any] | None:
        """Extract video metadata including title, album, and artist."""
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            ydl_opts = {
                "quiet": True,
                "skip_download": True,
                # Anti-detection options to avoid 403 errors
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "referer": "https://www.youtube.com/",
                "sleep_interval": 1,
                "max_sleep_interval": 5,
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                if not info:
                    return None

                # Extract metadata
                metadata = {"title": info.get("title", "Unknown"), "album": None, "artist": None}

                # Try to extract album and artist from various sources
                if "album" in info:
                    metadata["album"] = info["album"]
                elif "album" in info.get("tags", []):
                    metadata["album"] = info["tags"]["album"]

                if "artist" in info:
                    metadata["artist"] = info["artist"]
                elif "uploader" in info:
                    metadata["artist"] = info["uploader"]
                elif "creator" in info:
                    metadata["artist"] = info["creator"]
                elif "artist" in info.get("tags", []):
                    metadata["artist"] = info["tags"]["artist"]

                return metadata
        except Exception as e:
            print(f"  ✗ Error extracting metadata for {video_id}: {e}", file=sys.stderr)
            return None

    def _download_video(self, video_id: str) -> str | None:
        """
        Download a single video as audio to the output directory.
        Returns the filename if successful, None otherwise.
        """
        if self.tracker.is_downloaded(video_id):
            print(f"  Already downloaded: {video_id}")
            return self.tracker.get_filename(video_id)

        # Extract video metadata
        metadata = self._extract_metadata(video_id)
        if not metadata:
            return None

        title = metadata["title"]
        album = metadata["album"]
        artist = metadata["artist"]

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
            self.tracker.mark_downloaded(video_id, title, filename, album, artist)
            print(f"  [OK] Downloaded: {filename}")
            if album:
                print(f"    Album: {album}")
            if artist:
                print(f"    Artist: {artist}")
            return filename

        except Exception as e:
            print(f"  [ERROR] Error downloading {video_id}: {e}", file=sys.stderr)
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
        print("\n[OK] Finished processing video")

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
            self._download_video(video_id)

        print(f"\n[OK] Finished processing playlist: {playlist_title}")
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
    print("[OK] Download complete!")
    print(f"Total videos in library: {len(tracker.downloaded_videos)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
