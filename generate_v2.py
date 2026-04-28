import os
import random
import asyncio
import argparse
import edge_tts
import whisper
import torch
import warnings
import imageio_ffmpeg
import shutil
import json
import requests
from dotenv import load_dotenv
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_audioclips
)
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Load environment variables from .env file
load_dotenv()

# Optional YouTube Uploader
YOUTUBE_AVAILABLE = False
try:
    from youtube_uploader import upload_video
    YOUTUBE_AVAILABLE = True
    print("YouTube Uploader module loaded successfully.")
except ImportError as e:
    print(f"YouTube Uploader module failed to load: {e}")
except Exception as e:
    print(f"Unexpected error loading YouTube Uploader: {e}")

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning, module="whisper")

# Set FFMPEG path for Whisper and other tools
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

# Configuration
INPUT_BASE_DIR = "input"
OUTPUT_BASE_DIR = "output"
CACHE_DIR = "output_cache"
YT_REF_DIR = "yt-ref"
VOICE = "en-US-ChristopherNeural"
VOICE_RATE = "+10%"
TARGET_RES = (1080, 1920)
FPS = 30
FONT_PATH = "fonts/theboldfont.ttf"
FONT_SIZE = 110

# AI Configuration (Gemini API) loaded from .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Load Whisper model on CPU
print("Loading Whisper Model on CPU...")
model = whisper.load_model("base", device="cpu")

async def generate_audio(text, output_path):
    communicate = edge_tts.Communicate(text, VOICE, rate=VOICE_RATE)
    await communicate.save(output_path)

def get_word_timestamps(audio_path):
    print(f"Transcribing {audio_path} for absolute sync...")
    result = model.transcribe(audio_path, word_timestamps=True, fp16=False)
    words_data = []
    for segment in result['segments']:
        for word in segment['words']:
            words_data.append({
                "word": word['word'].strip(),
                "start": word['start'],
                "end": word['end'],
                "duration": word['end'] - word['start']
            })
    return words_data

def create_text_clip(text, start_time, duration):
    w, h = 1080, 400
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE) if os.path.exists(FONT_PATH) else ImageFont.load_default()
    except:
        font = ImageFont.load_default()
        
    text = text.upper()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((w-tw)//2, (h-th)//2)
    
    outline_color = (0, 0, 0, 255)
    outline_width = 8
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx*dx + dy*dy <= outline_width*outline_width:
                draw.text((pos[0]+dx, pos[1]+dy), text, font=font, fill=outline_color)
    
    draw.text(pos, text, font=font, fill='white')
    clip = ImageClip(np.array(img)).with_start(start_time).with_duration(duration)
    
    def anim_size(t):
        if t < 0.07: return 0.8 + 3 * t
        if t < 0.15: return 1.1 - 1.25 * (t - 0.07)
        return 1.0
    clip = clip.resized(anim_size).with_position(('center', 'center'))
    return clip

def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        if 'candidates' in result and result['candidates']:
            return result['candidates'][0]['content']['parts'][0]['text'].strip()
        return None
    except Exception as e:
        print(f"AI Error: {e}")
        return None

def get_summarized_name(text):
    prompt = f"Summarize this text into a 3-5 word catchy folder name (lowercase, underscores instead of spaces, no special characters): {text[:500]}"
    name = call_gemini(prompt)
    if not name: return "video_" + str(random.randint(1000, 9999))
    clean_name = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
    return clean_name if (clean_name and clean_name.replace("_", "")) else "video_" + str(random.randint(1000, 9999))

def get_youtube_metadata(text):
    prompt = f"Generate YouTube Shorts metadata. Format EXACTLY as:\nTITLE: ...\nDESCRIPTION: ...\nTAGS: ...\nContent: {text[:1000]}"
    metadata = call_gemini(prompt)
    if not metadata:
        return "TITLE: Amazing Reddit Story\nDESCRIPTION: Check out this story!\nTAGS: #reddit #story #shorts"
    return metadata

def save_video_parts(final_video, output_dir, metadata, folder_name, part_duration):
    duration = final_video.duration
    output_files = []
    if duration <= part_duration + 1:
        v_path = os.path.join(output_dir, "0.mp4")
        m_path = os.path.join(output_dir, "description.txt")
        temp_audio = os.path.join(CACHE_DIR, f"{folder_name}_temp_0.mp4")
        final_video.write_videofile(v_path, fps=FPS, codec="h264_nvenc", audio_codec="aac", bitrate="20000k", temp_audiofile=temp_audio)
        with open(m_path, "w", encoding="utf-8") as f:
            f.write(metadata)
        output_files.append((v_path, m_path))
    else:
        num_parts = int(np.ceil(duration / part_duration))
        for i in range(num_parts):
            start = i * part_duration
            end = min((i + 1) * part_duration, duration)
            if end - start < 2: continue
            part_clip = final_video.subclipped(start, end)
            v_path = os.path.join(output_dir, f"{i+1}.mp4")
            m_path = os.path.join(output_dir, f"d{i+1}.txt")
            temp_audio = os.path.join(CACHE_DIR, f"{folder_name}_temp_{i+1}.mp4")
            part_clip.write_videofile(v_path, fps=FPS, codec="h264_nvenc", audio_codec="aac", bitrate="20000k", temp_audiofile=temp_audio)
            part_meta = metadata.replace("TITLE:", f"TITLE: (Part {i+1})")
            with open(m_path, "w", encoding="utf-8") as f:
                f.write(part_meta)
            output_files.append((v_path, m_path))
    return output_files

async def process_folder(folder_path, max_duration, part_duration, semaphore, upload_enabled):
    async with semaphore:
        folder_name = os.path.basename(folder_path)
        print(f"\n--- Processing Folder: {folder_name} (Parallel) ---")
        
        txt_file = next((f for f in os.listdir(folder_path) if f.endswith(".txt")), None)
        img_file = next((f for f in os.listdir(folder_path) if f.endswith(".png") or f.endswith(".jpg")), None)
        if not txt_file or not img_file: return

        with open(os.path.join(folder_path, txt_file), 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"[{folder_name}] Consulting AI...")
        summarized_name = get_summarized_name(content)
        metadata = get_youtube_metadata(content)
        
        final_output_dir = os.path.join(OUTPUT_BASE_DIR, summarized_name)
        os.makedirs(final_output_dir, exist_ok=True)
        
        generated_files = []
        # Check if an .mp4 already exists in input
        existing_video = next((f for f in os.listdir(folder_path) if f.endswith(".mp4")), None)
        if existing_video:
            print(f"[{folder_name}] Using existing video...")
            video_path = os.path.join(folder_path, existing_video)
            clip = VideoFileClip(video_path)
            generated_files = save_video_parts(clip, final_output_dir, metadata, folder_name, part_duration)
            clip.close()
            os.remove(video_path)
        else:
            parts = content.split("TEXT:")
            title_text = parts[0].replace("TITLE:", "").strip()
            body_text = parts[1].strip() if len(parts) > 1 else ""
            title_audio, body_audio = os.path.join(CACHE_DIR, f"{folder_name}_t.mp3"), os.path.join(CACHE_DIR, f"{folder_name}_b.mp3")
            
            await generate_audio(title_text, title_audio)
            await generate_audio(body_text, body_audio)
            
            t_audio, b_audio = AudioFileClip(title_audio), AudioFileClip(body_audio)
            words = get_word_timestamps(body_audio)
            full_audio = concatenate_audioclips([t_audio, b_audio])
            duration = min(max_duration, full_audio.duration)
            
            bg_files = [f for f in os.listdir(YT_REF_DIR) if f.endswith(".mp4")]
            bg_path = os.path.join(YT_REF_DIR, random.choice(bg_files))
            bg_full = VideoFileClip(bg_path).without_audio()
            start_bg = random.uniform(0, max(0, bg_full.duration - duration - 1))
            bg_clip = bg_full.subclipped(start_bg, start_bg + duration).resized(height=TARGET_RES[1])
            left = (bg_clip.w - TARGET_RES[0]) / 2
            bg_clip = bg_clip.cropped(x1=left, y1=0, x2=left + TARGET_RES[0], y2=TARGET_RES[1])
            
            img_clip = ImageClip(os.path.join(folder_path, img_file)).with_duration(t_audio.duration).resized(width=TARGET_RES[0] * 0.9)
            target_y = (TARGET_RES[1] - img_clip.h) // 2
            img_clip = img_clip.with_position(lambda t: ('center', 1920 - (1920 - target_y) * (t / 0.5)) if t < 0.5 else ('center', target_y))
            
            sub_clips = [create_text_clip(w['word'], max(0, w['start'] + t_audio.duration - 0.1), min(w['duration'], duration - (w['start'] + t_audio.duration - 0.1))) for w in words if max(0, w['start'] + t_audio.duration - 0.1) < duration]
            final_video = CompositeVideoClip([bg_clip, img_clip] + sub_clips, size=TARGET_RES).with_audio(full_audio.subclipped(0, duration))
            
            loop = asyncio.get_event_loop()
            generated_files = await loop.run_in_executor(None, lambda: save_video_parts(final_video, final_output_dir, metadata, folder_name, part_duration))
            t_audio.close(); b_audio.close(); bg_full.close()

        for item in os.listdir(folder_path):
            if not item.endswith(".mp4"): shutil.move(os.path.join(folder_path, item), os.path.join(final_output_dir, item))
        if os.path.exists(folder_path) and not os.listdir(folder_path): os.rmdir(folder_path)
        print(f"Finished {folder_name} -> {final_output_dir}")

        # Handle Uploads
        if upload_enabled and YOUTUBE_AVAILABLE:
            print(f"[{folder_name}] Starting YouTube uploads...")
            for i, (v_path, m_path) in enumerate(generated_files):
                # Spread parts out by 6 hours + 30 mins per part to keep order
                offset = 6 + (i * 0.5)
                try:
                    upload_video(v_path, m_path, schedule_hours=offset)
                except Exception as e:
                    print(f"Upload failed for {v_path}: {e}")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=180)
    parser.add_argument("--parallel", type=int, default=4)
    parser.add_argument("--part-duration", type=int, default=58)
    parser.add_argument("--upload", action="store_true", help="Enable automatic YouTube upload")
    args = parser.parse_args()
    
    if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
    if not os.path.exists(OUTPUT_BASE_DIR): os.makedirs(OUTPUT_BASE_DIR)
    
    input_folders = [os.path.join(INPUT_BASE_DIR, d) for d in os.listdir(INPUT_BASE_DIR) if os.path.isdir(os.path.join(INPUT_BASE_DIR, d))]
    if not input_folders: return
    
    semaphore = asyncio.Semaphore(args.parallel)
    await asyncio.gather(*[process_folder(f, args.duration, args.part_duration, semaphore, args.upload) for f in input_folders])
    
    print("Cleaning up cache...")
    for f in os.listdir(CACHE_DIR):
        try: os.remove(os.path.join(CACHE_DIR, f))
        except: pass

if __name__ == "__main__":
    asyncio.run(main())
