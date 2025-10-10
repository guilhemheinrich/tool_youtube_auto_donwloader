# YouTube Auto Downloader

Download YouTube videos and playlists as audio files with metadata. Automatically tracks downloads to avoid duplicates and uses symlinks for efficient storage.

## Features

- **Audio-only downloads**: Downloads only the audio track (Opus format by default)
- **Metadata preservation**: Embeds title, artist, thumbnails, and other metadata in audio files
- **Intelligent deduplication**: Tracks downloaded videos to avoid re-downloading
- **Symlink-based playlists**: Videos are stored once, playlists use symlinks to avoid duplicates
- **Batch processing**: Process multiple URLs from a file
- **Organized storage**: Each video gets its own folder with audio, metadata, and thumbnail

## Installation

This project uses Poetry for dependency management:

```bash
# Install dependencies
poetry install
```

## Dependencies

- **yt-dlp**: YouTube video downloader
- **mutagen**: Audio metadata handling
- **pyyaml**: Configuration file parsing
- **ffmpeg**: Required for audio extraction (must be installed separately)

## Usage

### Single URL Download

Download a single video or playlist:

```bash
poetry run yt-pull "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output-dir ./downloads \
  --history-file ./history.json
```

Or for a playlist:

```bash
poetry run yt-pull "https://www.youtube.com/playlist?list=PLAYLIST_ID" \
  --output-dir ./downloads \
  --history-file ./history.json
```

### Batch Download

Process multiple URLs from a file:

```bash
poetry run yt-batch \
  --urls-file urls.txt \
  --config config.yaml
```

## Configuration

### Configuration File (YAML)

Create a `config.yaml` file:

```yaml
# Output directory (root folder for all downloads)
output_dir: ./downloads

# History file (tracks downloaded videos to avoid duplicates)
history_file: ./history.json
```

See `config.example.yaml` for a template.

### URLs File

Create a text file with one URL per line:

```txt
# Comments start with #
https://www.youtube.com/watch?v=VIDEO_ID
https://www.youtube.com/playlist?list=PLAYLIST_ID

# Empty lines are ignored
```

See `urls.example.txt` for a template.

## Output Structure

Downloaded files are organized as follows:

```
downloads/
├── _all_videos/
│   ├── VIDEO_ID - Title/
│   │   ├── VIDEO_ID - Title.opus      # Audio file
│   │   ├── VIDEO_ID - Title.info.json # Metadata
│   │   └── VIDEO_ID - Title.jpg       # Thumbnail
│   └── ...
├── Playlist Name/
│   ├── VIDEO_ID - Title/  -> ../_all_videos/VIDEO_ID - Title/  (symlink)
│   └── ...
└── ...
```

- **`_all_videos/`**: Contains the actual audio files, each in its own folder
- **Playlist folders**: Contain symlinks to videos in `_all_videos/`
- **Single videos**: Stored directly in `_all_videos/`

This structure ensures:
- Each video is downloaded only once
- Playlists can share videos without duplication
- All files related to a video (audio, metadata, thumbnail) are kept together

## Commands Reference

### `yt-pull`

Download a single URL (video or playlist).

**Arguments:**
- `url`: YouTube URL (required)
- `--output-dir`: Output directory (required)
- `--history-file`: History file path (required)

### `yt-batch`

Download multiple URLs from a file using configuration.

**Arguments:**
- `--urls-file`: Path to file with URLs (required)
- `--config`: Path to YAML configuration file (required)

## Examples

### Download a single video

```bash
poetry run yt-pull "https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  --output-dir ./music \
  --history-file ./history.json
```

### Download a playlist

```bash
poetry run yt-pull "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf" \
  --output-dir ./music \
  --history-file ./history.json
```

### Batch download

```bash
# 1. Create config.yaml
cat > config.yaml << EOF
output_dir: ./music
history_file: ./history.json
EOF

# 2. Create urls.txt with your URLs
cat > urls.txt << EOF
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf
EOF

# 3. Run batch download
poetry run yt-batch --urls-file urls.txt --config config.yaml
```

## How It Works

1. **Download tracking**: The history file stores video IDs and folder names
2. **Duplicate detection**: Before downloading, checks if video ID exists in history
3. **Folder creation**: Each video gets a folder named `VIDEO_ID - Title`
4. **Symlink creation**: For playlists, symlinks point to the actual video folders
5. **Metadata embedding**: Uses mutagen to embed metadata and thumbnails in audio files

## Requirements

- Python 3.10+
- ffmpeg (must be installed separately)
- Poetry

### Installing ffmpeg

**Windows:**
```bash
# Using chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

**Linux:**
```bash
sudo apt-get install ffmpeg  # Debian/Ubuntu
sudo yum install ffmpeg      # CentOS/RHEL
```

**macOS:**
```bash
brew install ffmpeg
```

## Troubleshooting

### "module mutagen was not found"

Run `poetry install` to ensure all dependencies are installed.

### Symlinks not working on Windows

You may need to enable Developer Mode or run as Administrator to create symlinks on Windows.

### "ffmpeg not found"

Install ffmpeg separately (see Requirements section).

## Development

### Project Structure

```
tool-youtube-auto-downloader/
├── src/
│   └── tool_youtube_auto_downloader/
│       ├── __init__.py
│       ├── pull_yt.py    # Single URL download logic
│       ├── main.py       # Batch processing logic
│       └── old.py        # Legacy code
├── pyproject.toml        # Poetry configuration
├── config.example.yaml   # Example configuration
├── urls.example.txt      # Example URLs file
└── README.md
```

### Running Tests

```bash
# Lint code
poetry run ruff check .

# Format code
poetry run ruff format .
```

## License

See LICENSE file.
