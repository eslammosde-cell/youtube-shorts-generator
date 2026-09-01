import os
import requests
import asyncio
import random
import time
import math
import edge_tts
from groq import Groq
from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

try:
    from moviepy.editor import (
        AudioFileClip, CompositeVideoClip, ImageClip, ColorClip, VideoFileClip, VideoClip
    )
except ImportError:
    from moviepy.video.io.VideoFileClip import VideoFileClip
    from moviepy.video.VideoClip import ImageClip, ColorClip, VideoClip
    from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
    from moviepy.audio.io.AudioFileClip import AudioFileClip

# API Keys
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
PEXELS_KEY = os.getenv("PEXELS_API_KEY", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

VOICE = "en-US-AndrewNeural"
client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

def set_clip_duration(clip, duration):
    if hasattr(clip, 'with_duration'):
        return clip.with_duration(duration)
    return clip.set_duration(duration)

def set_clip_audio(clip, audio):
    if hasattr(clip, 'with_audio'):
        return clip.with_audio(audio)
    return clip.set_audio(audio)

def get_realtime_trending_topic():
    trending_topics = [
        "AI Breakthroughs Changing the World", 
        "Deep Space Cosmic Mysteries", 
        "Psychology Secrets of Successful People",
        "Ancient Historical Discoveries",
        "Unbelievable Technology Facts"
    ]
    topic = random.choice(trending_topics)
    print(f"🔥 Selected Trending Topic: {topic}")
    return topic

def generate_ai_content(topic, is_short=True):
    content_type = "YouTube Short (max 25 words script, fast-paced, highly engaging)" if is_short else "Full Video (detailed 60-word script)"
    
    prompt = f"""You are an elite viral content creator. Topic: '{topic}'.
Create content for a {content_type}:

SCRIPT: Write an amazing viral voiceover text.
TITLE: Write a high CTR title with 2 hashtags.
DESCRIPTION: Write 2 descriptive sentences.
TAGS: Write 8 comma-separated tags.
SEARCH_QUERY: 1 english word for video search (e.g. galaxy, technology, nature).
THUMBNAIL_PROMPT: Visual prompt for thumbnail.
"""
    models_to_try = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    text = ""
    for model_name in models_to_try:
        if not client:
            break
        try:
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
            )
            text = response.choices[0].message.content
            print(f"✅ Generated script using Groq model: {model_name}")
            break
        except Exception as e:
            print(f"Groq model {model_name} failed: {e}")

    try:
        script, title, desc, tags, query, thumb_prompt = "", "", "", "", "abstract", f"{topic} futuristic visual"
        
        for line in text.split("\n"):
            line_str = line.strip()
            if line_str.startswith("SCRIPT:"):
                script = line_str.replace("SCRIPT:", "").strip()
            elif line_str.startswith("TITLE:"):
                title = line_str.replace("TITLE:", "").strip()
            elif line_str.startswith("DESCRIPTION:"):
                desc = line_str.replace("DESCRIPTION:", "").strip()
            elif line_str.startswith("TAGS:"):
                tags = line_str.replace("TAGS:", "").strip()
            elif line_str.startswith("SEARCH_QUERY:"):
                query = line_str.replace("SEARCH_QUERY:", "").strip()
            elif line_str.startswith("THUMBNAIL_PROMPT:"):
                thumb_prompt = line_str.replace("THUMBNAIL_PROMPT:", "").strip()

        if script and title:
            return script, title, desc, tags, query, thumb_prompt
    except Exception as e:
        print(f"Parsing error: {e}")

    # fallback
    return (
        f"Unbelievable facts about {topic}! Scientists were completely shocked by this discovery.",
        f"The Untold Secrets of {topic}! 😱 #viral #shorts",
        f"Explore the amazing mysteries behind {topic} in this quick viral breakdown.",
        f"shorts, trending, viral, {topic}",
        "space",
        f"Abstract cosmic visualization of {topic}"
    )

def fetch_pexels_video(query, is_short=True):
    if not PEXELS_KEY:
        print("⚠️ No PEXELS_API_KEY found in secrets!")
        return None
    headers = {"Authorization": PEXELS_KEY}
    orientation = "portrait" if is_short else "landscape"
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=5&orientation={orientation}"
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            videos = res.json().get("videos", [])
            if videos:
                selected_video = random.choice(videos)
                video_files = selected_video.get("video_files", [])
                hd_file = next((f for f in video_files if f.get("quality") == "hd"), video_files[0])
                download_url = hd_file.get("link")
                
                v_res = requests.get(download_url, stream=True, timeout=15)
                v_path = "bg_video.mp4"
                with open(v_path, 'wb') as f:
                    for chunk in v_res.iter_content(chunk_size=1024*1024):
                        f.write(chunk)
                print("✅ Downloaded HD Background Video from Pexels!")
                return v_path
    except Exception as e:
        print(f"Pexels fetch error: {e}")
    return None

def make_dynamic_background(width, height, duration):
    """توليد خلفية متحركة جذابة بحركات ألوان وتأثير حركي تلقائي"""
    def make_frame(t):
        import numpy as np
        # خلط درجات الألوان ديناميكياً بناءً على الزمن t
        r = int(127 + 127 * math.sin(t * 1.5))
        g = int(127 + 127 * math.cos(t * 1.2))
        b = int(180 + 75 * math.sin(t * 2.0))
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :] = [r, g, b]
        return frame

    clip = VideoClip(make_frame, duration=duration)
    return clip

async def text_to_speech_async(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)

def create_text_overlay(text, width, height):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 55 if width < height else 45)
    except:
        font = ImageFont.load_default()

    words = text.split()
    lines, current = [], ""
    limit = 12 if width < height else 22
    for w in words:
        if len(current + " " + w) < limit:
            current += " " + w if current else w
        else:
            lines.append(current)
            current = w
    if current: lines.append(current)

    total_h = len(lines) * 80
    start_y = (height - total_h) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w_len = bbox[2] - bbox[0]
        x = (width - w_len) // 2
        y = start_y + (i * 80)
        draw.rectangle([x - 15, y - 5, x + w_len + 15, y + 65], fill=(0, 0, 0, 180))
        draw.text((x, y), line, fill="#FFD700" if i % 2 == 0 else "#FFFFFF", font=font)

    img.save("overlay.png")
    return "overlay.png"

def build_video(script, query, is_short=True):
    audio_path = "voice.mp3"
    asyncio.run(text_to_speech_async(script, audio_path))
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    target_w, target_h = (1080, 1920) if is_short else (1920, 1080)
    bg_video_path = fetch_pexels_video(query, is_short)

    if bg_video_path and os.path.exists(bg_video_path):
        try:
            v_clip = VideoFileClip(bg_video_path).resize(height=target_h)
            w, h = v_clip.size
            if w > target_w:
                v_clip = v_clip.crop(x1=(w - target_w)//2, y1=0, width=target_w, height=target_h)
            base_video = v_clip.loop(duration=duration) if v_clip.duration < duration else v_clip.subclip(0, duration)
        except Exception as e:
            base_video = make_dynamic_background(target_w, target_h, duration)
    else:
        base_video = make_dynamic_background(target_w, target_h, duration)

    overlay_path = create_text_overlay(script, target_w, target_h)
    overlay_clip = ImageClip(overlay_path)
    overlay_clip = set_clip_duration(overlay_clip, duration)

    final_video = CompositeVideoClip([base_video, overlay_clip])
    final_video = set_clip_audio(final_video, audio_clip)

    out_file = "final_video.mp4"
    final_video.write_videofile(out_file, fps=24, codec="libx264", audio_codec="aac", preset="ultrafast", threads=4)
    return out_file

def upload_to_youtube(video_path, title, desc, tags, thumb_path=None):
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': REFRESH_TOKEN,
        'grant_type': 'refresh_token',
    }
    response = requests.post(token_url, data=data).json()
    creds = Credentials(
        token=response.get('access_token'),
        refresh_token=REFRESH_TOKEN,
        token_uri=token_url,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )

    youtube = build('youtube', 'v3', credentials=creds)

    body = {
        'snippet': {
            'title': title,
            'description': f"{desc}\n\n#trending #viral #shorts",
            'tags': [t.strip() for t in tags.split(',')] if tags else [],
            'categoryId': '28'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
    res = request.execute()
    video_id = res['id']
    print(f"🎉 Video Uploaded Successfully! Video ID: {video_id}")

if __name__ == "__main__":
    import sys
    is_short = True if len(sys.argv) < 2 or sys.argv[1] == "short" else False
    
    print(f"🚀 Starting Automated Content Engine (Type: {'Short' if is_short else 'Long Video'})...")
    trending_topic = get_realtime_trending_topic()
    script, title, desc, tags, query, thumb_prompt = generate_ai_content(trending_topic, is_short)
    
    video_path = build_video(script, query, is_short)
    upload_to_youtube(video_path, title, desc, tags)
    print("✅ Process Completed Successfully!")
