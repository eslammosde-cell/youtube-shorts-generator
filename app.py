import os
import requests
import asyncio
import random
import time
import edge_tts
from groq import Groq
from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

try:
    from moviepy.editor import (
        AudioFileClip, CompositeVideoClip, ImageClip, ColorClip, VideoFileClip
    )
except ImportError:
    from moviepy.video.io.VideoFileClip import VideoFileClip
    from moviepy.video.VideoClip import ImageClip, ColorClip
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

# -------------------------------------------------------------
# دوال التوافقية مع إصدارات MoviePy المختلفة (v1 & v2)
# -------------------------------------------------------------
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
    content_type = "YouTube Short (max 20 words script, high energy)" if is_short else "Full Video (detailed 50-word script)"
    
    prompt = f"""You are an elite viral content creator. Topic: '{topic}'.
Create content for a {content_type}:

1. SCRIPT: Engaging voiceover script.
2. TITLE: High CTR viral title with 2 hashtags.
3. DESCRIPTION: High-SEO 2-sentence description.
4. TAGS: 8 comma-separated viral tags.
5. SEARCH_QUERY: 1-2 english words for background video (e.g. space, city, technology).
6. THUMBNAIL_PROMPT: A vivid prompt for thumbnail visual.

Format strictly as:
SCRIPT: <script text>
TITLE: <title text>
DESCRIPTION: <description text>
TAGS: <tags>
SEARCH_QUERY: <search query>
THUMBNAIL_PROMPT: <thumbnail prompt>
"""
    # محاولة استخدام الموديلات المتاحة في Groq
    models_to_try = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
    text = ""
    for model_name in models_to_try:
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
        script = text.split("SCRIPT:")[1].split("TITLE:")[0].strip()
        title = text.split("TITLE:")[1].split("DESCRIPTION:")[0].strip()
        desc = text.split("DESCRIPTION:")[1].split("TAGS:")[0].strip()
        tags = text.split("TAGS:")[1].split("SEARCH_QUERY:")[0].strip()
        query = text.split("SEARCH_QUERY:")[1].split("THUMBNAIL_PROMPT:")[0].strip()
        thumb_prompt = text.split("THUMBNAIL_PROMPT:")[1].strip()
        return script, title, desc, tags, query, thumb_prompt
    except Exception as e:
        print(f"Parsing Error, fallback used: {e}")
        return (
            f"Did you know about {topic}? This changes everything we knew!",
            f"The Truth About {topic}! 🚀 #viral #shorts",
            f"Discover the latest insights about {topic} in this quick breakdown.",
            f"shorts, trending, {topic}",
            "technology",
            f"Futuristic background of {topic}, 8k resolution"
        )

def fetch_pexels_video(query, is_short=True):
    if not PEXELS_KEY:
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
                return v_path
    except Exception as e:
        print(f"Pexels fetch error: {e}")
    return None

def generate_ai_thumbnail(prompt_text, title):
    try:
        clean_prompt = requests.utils.quote(prompt_text)
        url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width=1280&height=720&nologo=true"
        img_data = requests.get(url, timeout=20).content
        
        thumb_path = "thumbnail.jpg"
        with open(thumb_path, 'wb') as f:
            f.write(img_data)
            
        img = Image.open(thumb_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 55)
        except:
            font = ImageFont.load_default()
            
        draw.rectangle([0, 550, 1280, 720], fill=(0, 0, 0, 180))
        draw.text((50, 600), title[:40] + "...", fill="#FFD700", font=font)
        
        final_thumb = img.convert("RGB")
        final_thumb.save(thumb_path)
        return thumb_path
    except Exception as e:
        print(f"Thumbnail generation error: {e}")
        return None

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
        draw.rectangle([x - 15, y - 5, x + w_len + 15, y + 65], fill=(0, 0, 0, 170))
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
            base_video = ColorClip(size=(target_w, target_h), color=(15, 20, 30), duration=duration)
    else:
        base_video = ColorClip(size=(target_w, target_h), color=(15, 20, 30), duration=duration)

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
            'description': f"{desc}\n\n#trending #viral",
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

    if thumb_path and os.path.exists(thumb_path):
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(thumb_path)).execute()
            print("🖼️ Custom Thumbnail Uploaded Successfully!")
        except Exception as e:
            print(f"Thumbnail upload error: {e}")

if __name__ == "__main__":
    import sys
    is_short = True if len(sys.argv) < 2 or sys.argv[1] == "short" else False
    
    print(f"🚀 Starting Automated Content Engine (Type: {'Short' if is_short else 'Long Video'})...")
    trending_topic = get_realtime_trending_topic()
    script, title, desc, tags, query, thumb_prompt = generate_ai_content(trending_topic, is_short)
    
    video_path = build_video(script, query, is_short)
    thumb_path = generate_ai_thumbnail(thumb_prompt, title) if not is_short else None
    
    upload_to_youtube(video_path, title, desc, tags, thumb_path)
    print("✅ Process Completed Successfully!")
