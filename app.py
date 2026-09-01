import os
import requests
import asyncio
import random
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

GROQ_KEY = os.getenv("GROQ_API_KEY", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

# اختيار صوت حماسي واحترافي
VOICE = "en-US-AndrewNeural"

client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

def generate_viral_content():
    topics = [
        "Mind Blowing Psychology Facts", 
        "Dark Mysteries of Deep Space", 
        "Billionaire Daily Discipline", 
        "Unsolved Ancient Secrets"
    ]
    topic = random.choice(topics)
    
    prompt = f"""You are a viral YouTube Shorts creator. Create content for '{topic}':
1. SCRIPT: A ultra high-energy, 18-word viral hook script in English that captivates instantly.
2. TITLE: A high-CTR SEO title with 2 viral hashtags.
3. DESCRIPTION: A concise 2-sentence SEO description.
4. TAGS: 8 comma-separated search tags.

Format strictly as:
SCRIPT: <script text>
TITLE: <title text>
DESCRIPTION: <description text>
TAGS: <tags>
"""
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        text = response.choices[0].message.content
        script = text.split("SCRIPT:")[1].split("TITLE:")[0].strip()
        title = text.split("TITLE:")[1].split("DESCRIPTION:")[0].strip()
        desc = text.split("DESCRIPTION:")[1].split("TAGS:")[0].strip()
        tags = text.split("TAGS:")[1].strip()
        return script, title, desc, tags
    except Exception as e:
        print(f"Groq Error: {e}")
        return (
            "Stop scrolling right now! Your daily habits determine whether you win or lose in life.", 
            "The Brutal Truth About Success! 🧠 #shorts #mindset", 
            "How daily discipline completely changes your life.", 
            "shorts, motivation, mindset, success, viral"
        )

# جلب فيديو خلفية HD مجاني ومباشر
def get_background_video():
    video_urls = [
        "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-1610-large.mp4",
        "https://assets.mixkit.co/videos/preview/mixkit-storm-clouds-in-the-sky-4210-large.mp4",
        "https://assets.mixkit.co/videos/preview/mixkit-abstract-laser-lights-background-41555-large.mp4"
    ]
    url = random.choice(video_urls)
    v_path = "bg_video.mp4"
    try:
        res = requests.get(url, stream=True, timeout=10)
        if res.status_code == 200:
            with open(v_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
            return v_path
    except Exception as e:
        print(f"Error fetching video: {e}")
    return None

async def text_to_speech_async(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)

def create_text_overlay(text, width=1080, height=1920):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 65)
    except Exception:
        font = ImageFont.load_default()

    words = text.split()
    lines, current = [], ""
    for w in words:
        if len(current + " " + w) < 14:
            current += " " + w if current else w
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)

    total_h = len(lines) * 100
    start_y = (height - total_h) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w_len = bbox[2] - bbox[0]
        x = (width - w_len) // 2
        y = start_y + (i * 100)
        
        # خلفية سوداء شفافة خلف كل سطر نص لسهولة القراءة
        draw.rectangle([x - 20, y - 10, x + w_len + 20, y + 80], fill=(0, 0, 0, 160))
        
        # حد خارجي للنص (Stroke)
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                draw.text((x + dx, y + dy), line, fill="black", font=font)
        
        # تبديل الألوان بين الأصفر والأبيض لجذب العين
        text_color = "#FFD700" if i % 2 == 0 else "#FFFFFF"
        draw.text((x, y), line, fill=text_color, font=font)

    img.save("overlay.png")
    return "overlay.png"

def build_short_video(script):
    audio_path = "voice.mp3"
    asyncio.run(text_to_speech_async(script, audio_path))
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    bg_video_path = get_background_video()
    
    if bg_video_path:
        try:
            v_clip = VideoFileClip(bg_video_path).resize(height=1920)
            w, h = v_clip.size
            if w > 1080:
                crop_x = (w - 1080) // 2
                v_clip = v_clip.crop(x1=crop_x, y1=0, width=1080, height=1920)
            
            base_video = v_clip.loop(duration=duration) if v_clip.duration < duration else v_clip.subclip(0, duration)
        except Exception:
            base_video = ColorClip(size=(1080, 1920), color=(15, 20, 30), duration=duration)
    else:
        base_video = ColorClip(size=(1080, 1920), color=(15, 20, 30), duration=duration)

    overlay_path = create_text_overlay(script)
    overlay_clip = ImageClip(overlay_path).set_duration(duration)

    final_video = CompositeVideoClip([base_video, overlay_clip]).set_audio(audio_clip)
    out_file = "final_short.mp4"
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
    access_token = response.get('access_token')

    creds = Credentials(
        token=access_token,
        refresh_token=REFRESH_TOKEN,
        token_uri=token_url,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )

    youtube = build('youtube', 'v3', credentials=creds)

    body = {
        'snippet': {
            'title': title,
            'description': f"{desc}\n\n#shorts #viral #trending",
            'tags': [t.strip() for t in tags.split(',')] if tags else [],
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
    res = request.execute()
    print(f"🎉 Uploaded High Quality Short! Video ID: {res['id']}")

if __name__ == "__main__":
    print("🚀 Generating High Quality Automated Short...")
    script, title, desc, tags = generate_viral_content()
    video_path = build_short_video(script)
    upload_to_youtube(video_path, title, desc, tags)
    print("✅ Finished Successfully!")
