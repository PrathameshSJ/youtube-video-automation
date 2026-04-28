# Reddit Video Maker Context

## Overview
Automated pipeline for generating high-quality Reddit-style YouTube Shorts with AI-generated metadata, text-to-speech, and automatic video splitting.

## Project Structure
- `generate_v2.py`: Main execution script (Async, Parallel).
- `input/`: Folder for new video tasks.
- `output/`: Finished videos organized by catchy names.
- `output_cache/`: Temporary audio and intermediate files.
- `yt-ref/`: Background gameplay footage (.mp4).
- `fonts/`: Typography assets.

## Features
- **AI Integration**: Uses Gemini (gemini-3.1-flash-lite-preview) for catchy folder naming and YouTube metadata generation.
- **Naming Convention**:
    - Single video (<= PART_DURATION): `0.mp4` and `description.txt`.
    - Multi-part video (> PART_DURATION): `1.mp4`, `2.mp4`... and `d1.txt`, `d2.txt`...
- **Auto-Splitting**: Configurable `PART_DURATION` (default 58s, adjustable via `--part-duration`).
- **Sync Engine**: OpenAI Whisper (Base) for word-level subtitle synchronization.
- **TTS**: Microsoft Edge TTS for natural-sounding voiceovers.
- **Cleanup**: Automatic `output_cache` cleanup after execution, with unique temp files.

## Usage
- Put a folder in `input/` containing a `.txt` (with `TITLE:` and `TEXT:`) and an image.
- Run `python generate_v2.py --parallel 4 --duration 180 --part-duration 58`.
- For 10-second parts (testing): `python generate_v2.py --part-duration 10`.
