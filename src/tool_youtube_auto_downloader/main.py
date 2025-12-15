#!/usr/bin/env python3
"""
YouTube Auto Downloader - Main Module
Processes multiple YouTube URLs from a file using configuration.
"""

import argparse
import sys
from pathlib import Path

import yaml

from tool_youtube_auto_downloader.pull_yt import DownloadTracker, YouTubePuller


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config or {}
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML configuration: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error: Could not read configuration file: {e}", file=sys.stderr)
        sys.exit(1)


def read_urls_file(urls_file: Path) -> list[str]:
    """Read URLs from file, one per line. Skip empty lines and comments."""
    if not urls_file.exists():
        print(f"Error: URLs file not found: {urls_file}", file=sys.stderr)
        sys.exit(1)

    urls = []
    try:
        with open(urls_file, encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Basic validation
                if not (line.startswith("http://") or line.startswith("https://")):
                    print(f"Warning: Line {line_num} does not look like a URL: {line}", file=sys.stderr)
                    continue
                urls.append(line)
        return urls
    except OSError as e:
        print(f"Error: Could not read URLs file: {e}", file=sys.stderr)
        sys.exit(1)


def validate_config(config: dict) -> None:
    """Validate that required configuration keys are present."""
    required_keys = ["output_dir", "history_file"]
    missing_keys = [key for key in required_keys if key not in config]

    if missing_keys:
        print(f"Error: Missing required configuration keys: {', '.join(missing_keys)}", file=sys.stderr)
        print("Required keys: output_dir, history_file", file=sys.stderr)
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Download multiple YouTube videos/playlists from a file")
    parser.add_argument(
        "--urls-file", required=True, type=Path, help="Path to file containing YouTube URLs (one per line)"
    )
    parser.add_argument("--config", required=True, type=Path, help="Path to configuration file (YAML)")
    parser.add_argument(
        "--flat-import",
        action="store_true",
        help="Disable automatic file organization (store all files in root directory)",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Load configuration
    print(f"Loading configuration from: {args.config}")
    config = load_config(args.config)
    validate_config(config)

    output_dir = Path(config["output_dir"]).expanduser().resolve()
    history_file = Path(config["history_file"]).expanduser().resolve()

    print(f"Output directory: {output_dir}")
    print(f"History file: {history_file}")

    # Read URLs
    print(f"\nReading URLs from: {args.urls_file}")
    urls = read_urls_file(args.urls_file)

    if not urls:
        print("No URLs found in file")
        sys.exit(0)

    print(f"Found {len(urls)} URL(s) to process\n")

    # Initialize tracker and puller
    tracker = DownloadTracker(history_file)
    puller = YouTubePuller(output_dir, tracker, flat_import=args.flat_import)

    # Process each URL
    for i, url in enumerate(urls, 1):
        print("\n" + "=" * 70)
        print(f"Processing URL {i}/{len(urls)}")
        print("=" * 70)

        try:
            puller.pull(url)
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            sys.exit(1)
        except Exception as e:
            # Handle encoding errors for error messages
            try:
                error_msg = str(e)
                print(f"\nError processing {url}: {error_msg}", file=sys.stderr)
            except UnicodeEncodeError:
                # Fallback for Windows console encoding issues
                error_msg = str(e).encode("ascii", "replace").decode("ascii")
                print(f"\nError processing {url}: {error_msg}", file=sys.stderr)
            print("Continuing to next URL...\n")
            continue

    # Final summary
    print("\n" + "=" * 70)
    print("All URLs processed!")
    print(f"Total videos in library: {len(tracker.downloaded_videos)}")
    print(f"Output directory: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
