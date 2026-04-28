# Reddit Shorts Maker 

An automated pipeline to transform Reddit stories into high-quality YouTube Shorts with AI-generated metadata, TTS, and automatic scheduling.

##  Features
- **AI Summary**: Uses Gemini to generate catchy folder names and YouTube metadata.
- **Dynamic Captions**: Absolute word-level sync using OpenAI Whisper.
- **Natural Voice**: High-quality TTS via Edge-TTS.
- **Smart Splitting**: Automatically splits long stories into Part 1, Part 2, etc.
- **Auto-Upload**: Genuine YouTube API integration with automatic 6-hour scheduling.

##  Quick Start

### 1. Prerequisites
- Python 3.10+
- FFmpeg installed on your system.
- A Gemini API Key (Free tier works great).
- Google Cloud Project for YouTube API (optional).

### 2. Installation
```bash
git clone https://github.com/yourusername/redditmaker.git
cd redditmaker
python run.py
```

### 3. Configuration
1. Rename `.env.example` to `.env` and add your `GEMINI_API_KEY`.
2. If using YouTube upload, place your `client_secrets.json` in the root folder.

### 4. Usage
Place your story in the `input/` folder (requires a `.txt` file and an image) and run:
```bash
python run.py --upload --part-duration 58
```

##  Tech Stack
- **MoviePy**: Video compositing.
- **OpenAI Whisper**: Transcription.
- **Edge-TTS**: Voice generation.
- **Google Gemini**: AI logic.
- **Google API**: YouTube automation.

##  License
MIT
