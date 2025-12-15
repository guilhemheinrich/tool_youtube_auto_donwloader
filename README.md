# YouTube Auto Downloader

Download YouTube videos or playlists as audio (.opus) with automatic library organization and a simple history to avoid duplicates.

## Requirements

- Python >= 3.10
- FFmpeg installed and available on PATH (required by yt-dlp for audio extraction)
- **JavaScript runtime (recommended)**: Node.js or Deno for better YouTube extraction support
  - The tool will automatically detect and use Node.js or Deno if installed
  - Without a JS runtime, some videos may fail to download (especially newer content)
  - Install Node.js: https://nodejs.org/ (or via package manager: `choco install nodejs` on Windows, `brew install node` on macOS)
  - Install Deno: https://deno.com/ (or via package manager)

## Installation

Using Poetry (recommended for local usage):

```bash
poetry install
```

Activate the environment when needed:

```bash
poetry shell
```

Alternatively, run commands without activating the shell:

```bash
poetry run yt-pull --help
poetry run yt-batch --help
```

## Quick Start

1) Copy and edit the example configuration:

```bash
cp config.example.yaml config.yaml
# set output_dir and history_file to your preferred locations
```

2) (Optional) Prepare a URLs list file, one URL per line. You can start from the example:

```bash
cp urls.example.txt urls.txt
```

## Commands

Two CLI entry points are provided:

- yt-pull: Download a single URL (video or playlist)
- yt-batch: Process multiple URLs from a file

### yt-pull

```bash
yt-pull URL --output-dir <DIR> --history-file <FILE> [--flat-import]
```

- URL: YouTube video or playlist URL
- --output-dir: Root folder where audio files will be saved
- --history-file: JSON file tracking downloaded videos (prevents duplicates)
- --flat-import: Disable directory organization; place files at the root of output_dir

Examples:

```bash
# Video
poetry run yt-pull "https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  --output-dir ./downloads \
  --history-file ./downloads/history.json

# Playlist
poetry run yt-pull "https://www.youtube.com/playlist?list=PLxxxxx" \
  --output-dir ./downloads \
  --history-file ./downloads/history.json
```

### yt-batch

Use a YAML config and a text file containing one URL per line.

```bash
yt-batch --urls-file <PATH_TO_TXT> --config <PATH_TO_YAML> [--flat-import]
```

Config file (YAML):

```yaml
output_dir: ./downloads
history_file: ./downloads/history.json
```

Example:

```bash
poetry run yt-batch \
  --urls-file ./urls.txt \
  --config ./config.yaml
```

## File Organization

By default, files are organized under output_dir using metadata:

- Artist/Album/Title.opus when artist and album are known
- Artist/singles/Title.opus when only artist is known
- _singles/Title.opus when no metadata is available

Use --flat-import to store everything directly under output_dir.

## Troubleshooting

### JavaScript Runtime Warnings

If you see warnings about missing JavaScript runtime:
- **Solution**: Install Node.js or Deno (see Requirements above)
- The tool will automatically detect and use an installed runtime
- Some videos may still work without a JS runtime, but newer content often requires it

### Download Errors

- Ensure FFmpeg is installed and visible on PATH
- Check that you have a JavaScript runtime installed (Node.js or Deno)
- Some videos may be unavailable due to YouTube restrictions or removal

### Other Tips

- The history file prevents re-downloading the same video ID; you can delete specific entries from the JSON if needed
- If metadata extraction fails, the tool will still attempt to download the video with available information

## License

MIT
