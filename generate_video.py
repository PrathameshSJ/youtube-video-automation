import os
import random
import asyncio
import argparse
import edge_tts
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_audioclips
)
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Configuration
INPUT_DIR = "1"
YT_REF_DIR = "yt-ref"
VOICE = "en-US-ChristopherNeural"
VOICE_RATE = "+50%" 
TARGET_RES = (1080, 1920)
FPS = 30
FONT_PATH = "theboldfont.ttf"
FONT_SIZE = 110 

async def generate_tts(text, output_audio_path):
    communicate = edge_tts.Communicate(text, VOICE, rate=VOICE_RATE)
    subs = []
    if os.path.exists(output_audio_path): os.remove(output_audio_path)
    
    with open(output_audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                subs.append({
                    "word": chunk["text"],
                    "start": chunk["offset"] / 10**7, 
                    "duration": chunk["duration"] / 10**7
                })
    
    # Smart Fallback
    if not subs and os.path.exists(output_audio_path):
        try:
            temp_clip = AudioFileClip(output_audio_path)
            total_dur = temp_clip.duration
            temp_clip.close()
            words = text.split()
            if words:
                total_chars = sum(len(w) for w in words)
                current_time = 0
                for word in words:
                    w_dur = (len(word) / total_chars) * total_dur
                    subs.append({"word": word, "start": current_time, "duration": w_dur})
                    current_time += w_dur
        except: pass
            
    return subs

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
    
    # Thick Outline
    for dx in range(-8, 9):
        for dy in range(-8, 9):
            if dx*dx + dy*dy <= 64:
                draw.text((pos[0]+dx, pos[1]+dy), text, font=font, fill='black')
    
    draw.text(pos, text, font=font, fill='white')
    clip = ImageClip(np.array(img)).with_start(start_time).with_duration(duration)
    
    def anim_size(t):
        if t < 0.07: return 0.8 + 3 * t
        if t < 0.15: return 1.1 - 1.25 * (t - 0.07)
        return 1.0
    clip = clip.resized(anim_size).with_position(('center', 'center'))
    return clip

def generate_video(max_duration, version_name):
    output_file = f"{version_name}.mp4"
    print(f"--- Generating {output_file} (GPU Accelerated) ---")
    
    with open(os.path.join(INPUT_DIR, "1.txt"), 'r', encoding='utf-8') as f:
        content = f.read()
    
    parts = content.split("TEXT:")
    title = parts[0].replace("TITLE:", "").strip()
    text_content = parts[1].strip() if len(parts) > 1 else ""
    
    title_audio_path = "temp_title.mp3"
    text_audio_path = "temp_text.mp3"
    
    title_subs = asyncio.run(generate_tts(title, title_audio_path))
    text_subs = asyncio.run(generate_tts(text_content, text_audio_path))
    
    title_audio = AudioFileClip(title_audio_path)
    text_audio = AudioFileClip(text_audio_path)
    full_audio = concatenate_audioclips([title_audio, text_audio])
    
    duration = min(max_duration, full_audio.duration)
    
    bg_files = [f for f in os.listdir(YT_REF_DIR) if f.endswith(".mp4")]
    bg_path = os.path.join(YT_REF_DIR, random.choice(bg_files))
    bg_full = VideoFileClip(bg_path).without_audio()
    
    start_bg = random.uniform(0, max(0, bg_full.duration - duration - 1))
    bg_clip = bg_full.subclipped(start_bg, start_bg + duration)
    bg_clip = bg_clip.resized(height=TARGET_RES[1])
    left = (bg_clip.w - TARGET_RES[0]) / 2
    bg_clip = bg_clip.cropped(x1=left, y1=0, x2=left + TARGET_RES[0], y2=TARGET_RES[1])
    
    img_path = os.path.join(INPUT_DIR, "1.png")
    img_clip = ImageClip(img_path).with_duration(title_audio.duration)
    img_clip = img_clip.resized(width=TARGET_RES[0] * 0.9)
    target_y = (TARGET_RES[1] - img_clip.h) // 2
    def slide_pos(t):
        if t < 0.5: return ('center', 1920 - (1920 - target_y) * (t / 0.5))
        return ('center', target_y)
    img_clip = img_clip.with_position(slide_pos)
    
    sub_clips = []
    offset = title_audio.duration - 0.2
    
    for word_info in text_subs:
        start = max(0, word_info['start'] + offset)
        if start >= duration: break
        dur = word_info['duration']
        if dur > 0.02:
            sub_clips.append(create_text_clip(word_info['word'], start, dur))
    
    final_video = CompositeVideoClip([bg_clip, img_clip] + sub_clips, size=TARGET_RES)
    final_video = final_video.with_audio(full_audio.subclipped(0, duration))
    
    # GPU ACCELERATED EXPORT
    print(f"Exporting using h264_nvenc (NVIDIA GPU)...")
    final_video.write_videofile(
        output_file, 
        fps=FPS, 
        codec="h264_nvenc", # Use NVIDIA GPU Encoder
        audio_codec="aac",
        bitrate="8000k",
        threads=8
    )
    
    title_audio.close()
    text_audio.close()
    bg_full.close()
    if os.path.exists(title_audio_path): os.remove(title_audio_path)
    if os.path.exists(text_audio_path): os.remove(text_audio_path)
    print(f"Success! {output_file} is ready.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=60, help="Max duration in seconds")
    parser.add_argument("--version", type=str, default="final_output", help="Output filename (without .mp4)")
    args = parser.parse_args()
    generate_video(args.duration, args.version)
