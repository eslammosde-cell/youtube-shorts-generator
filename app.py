import os
import requests
import asyncio
import random
import time
import re
import edge_tts

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from PIL import Image, ImageDraw, ImageFont
from groq import Groq
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from moviepy.editor import (
    AudioFileClip, CompositeVideoClip, ImageClip, ColorClip, VideoFileClip
)

# API Keys
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
PEXELS_KEY = os.getenv("PEXELS_API_KEY", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

VOICE = "en-US-AndrewNeural"
client_groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
client_gemini = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

def set_clip_duration(clip, duration):
    return clip.set_duration(duration)

def set_clip_audio(clip, audio):
    return clip.set_audio(audio)

def get_realtime_trending_topic():
    trending_topics = [
        "Unexplained Space Mysteries That Terrify Scientists", 
        "Mind-Blowing Artificial Intelligence Facts", 
        "Psychological Tricks That Always Work",
        "Ancient Ruins Scientists Still Cannot Explain",
        "Secrets of the Deep Ocean"
    ]
    topic = random.choice(trending_topics)
    print(f"🔥 Selected Trending Topic: {topic}")
    return topic

def generate_ai_content(topic, is_short=True):
    prompt = f"""You are a professional YouTube Shorts creator. Topic: '{topic}'.
Write an engaging, high-retention script for a 35 to 50 seconds viral video.

You MUST follow this EXACT format:

SCRIPT: Write 80 to 110 words of voiceover text. High hook, strong viral facts, captivating tone.
TITLE: Write a viral title with emojis and 2 hashtags.
DESCRIPTION: Write 3 full sentences describing the content with a strong call to action.
TAGS: 10 relevant keywords separated by commas.
SEARCH_QUERY: 1 english search word for background video (e.g. galaxy, ocean, technology).
"""
    text = ""

    # 1. التجربة مع Groq
    if client_groq:
        groq_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
        for model_name in groq_models:
            try:
                response = client_groq.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_name,
                )
                text = response.choices[0].message.content
                print(f"✅ Generated script using Groq model: {model_name}")
                break
            except Exception as e:
                print(f"⚠️ Groq model {model_name} failed: {e}")

    # 2. التجربة مع Gemini
    if not text and client_gemini:
        print("🔄 Switching to Google Gemini AI...")
        gemini_models = ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
        for g_model in gemini_models:
            try:
                response = client_gemini.models.generate_content(
                    model=g_model,
                    contents=prompt,
                )
                text = response.text
                print(f"✅ Generated script using Google Gemini ({g_model})!")
                break
            except Exception as e:
                print(f"⚠️ Google Gemini model {g_model} failed: {e}")

    if not text:
        raise ValueError("❌ فشل الحصول على رد من الذكاء الاصطناعي!")

    script, title, desc, tags, query = "", "", "", "", ""
    
    for line in text.split("\n"):
        clean_line = re.sub(r'^\*+|\*+$', '', line.strip()).strip()
        
        if re.match(r'^(SCRIPT|Script):', clean_line, re.IGNORECASE):
            script = re.sub(r'^(SCRIPT|Script):', '', clean_line, flags=re.IGNORECASE).strip()
        elif re.match(r'^(TITLE|Title):', clean_line, re.IGNORECASE):
            title = re.sub(r'^(TITLE|Title):', '', clean_line, flags=re.IGNORECASE).strip()
        elif re.match(r'^(DESCRIPTION|Description):', clean_line, re.IGNORECASE):
            desc = re.sub(r'^(DESCRIPTION|Description):', '', clean_line, flags=re.IGNORECASE).strip()
        elif re.match(r'^(TAGS|Tags):', clean_line, re.IGNORECASE):
            tags = re.sub(r'^(TAGS|Tags):', '', clean_line, flags=re.IGNORECASE).strip()
        elif re.match(r'^(SEARCH_QUERY|Search_Query|Query):', clean_line, re.IGNORECASE):
            query = re.sub(r'^(SEARCH_QUERY|Search_Query|Query):', '', clean_line, flags=re.IGNORECASE).strip()

    # التحقق المباشر من اكتمال البيانات بدون أي خطط احتياطية
    if not script or not title or not desc or not query:
        raise ValueError(f"❌ لم يقم الذكاء الاصطناعي بإنشاء المحتوى بالتنسيق المطلوب!\nالنص المولد كان:\n{text}")

    return script, title, desc, tags, query

def fetch_pexels_video(query, is_short=True):
    if not PEXELS_KEY:
        raise ValueError("❌ لم يتم إضافة PEXELS_API_KEY في GitHub Secrets!")
        
    headers = {"Authorization": PEXELS_KEY}
    orientation = "portrait" if is_short else "landscape"
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=10&orientation={orientation}"
    
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

    raise ValueError(f"❌ تعذر العثور على فيديو مناسب على Pexels للكلمة المفتاحية: '{query}'")

async def text_to_speech_async(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)

def create_text_overlay(text, width, height):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 40 if width < height else 34)
    except:
        font = ImageFont.load_default()

    words = text.split()
    lines, current = [], ""
    limit = 16 if width < height else 30
    for w in words:
        if len(current + " " + w) < limit:
            current += " " + w if current else w
        else:
            lines.append(current)
            current = w
    if current: lines.append(current)

    total_h = len(lines) * 60
    start_y = (height - total_h) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w_len = bbox[2] - bbox[0]
        x = (width - w_len) // 2
        y = start_y + (i * 60)
        draw.rectangle([x - 12, y - 4, x + w_len + 12, y + 48], fill=(0, 0, 0, 190))
        draw.text((x, y), line, fill="#FFD700" if i % 2 == 0 else "#FFFFFF", font=font)

    img.save("overlay.png")
    return "overlay.png"

def build_video(script, query, is_short=True):
    bg_video_path = fetch_pexels_video(query, is_short)

    audio_path = "voice.mp3"
    asyncio.run(text_to_speech_async(script, audio_path))
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    target_w, target_h = (1080, 1920) if is_short else (1920, 1080)

    v_clip = VideoFileClip(bg_video_path).resize(height=target_h)
    w, h = v_clip.size
    if w > target_w:
        v_clip = v_clip.crop(x1=(w - target_w)//2, y1=0, width=target_w, height=target_h)
    
    base_video = v_clip.loop(duration=duration) if v_clip.duration < duration else v_clip.subclip(0, duration)

    overlay_path = create_text_overlay(script, target_w, target_h)
    overlay_clip = ImageClip(overlay_path)
    overlay_clip = set_clip_duration(overlay_clip, duration)

    final_video = CompositeVideoClip([base_video, overlay_clip])
    final_video = set_clip_audio(final_video, audio_clip)

    out_file = "final_video.mp4"
    final_video.write_videofile(out_file, fps=24, codec="libx264", audio_codec="aac", preset="ultrafast", threads=4)
    return out_file

def upload_to_youtube(video_path, title, desc, tags):
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
            'description': f"{desc}\n\n#trending #viral #shorts #facts #knowledge",
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
    
    script, title, desc, tags, query = generate_ai_content(trending_topic, is_short)
    video_path = build_video(script, query, is_short)
    
    upload_to_youtube(video_path, title, desc, tags)
    print("✅ Process Completed Successfully!")
