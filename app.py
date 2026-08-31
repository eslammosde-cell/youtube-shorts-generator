import os
import random
import requests
import asyncio
import streamlit as st
import edge_tts
from google import genai
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip, CompositeVideoClip, ImageClip, ColorClip, VideoFileClip
)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# إعدادات الصفحات
st.set_page_config(page_title="Pro AI YouTube Shorts Studio", page_icon="🎬", layout="wide")

st.title("🎬 Pro AI YouTube Shorts Studio")

# 1. إعدادات API
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

VOICE = "en-US-ChristopherNeural"

def generate_viral_content(topic):
    if not client:
        return (
            "Stop waiting for the right moment. The 5-second rule rewires your brain instantly to take massive action.",
            "Stop Procrastinating Right Now! 🧠 #shorts #mindset",
            "Learn how to rewire your focus and destroy hesitation. High-performance mindset tips.",
            "shorts, productivity, mindset, motivation, psychology, viral"
        )
    
    prompt = f"""You are an expert YouTube Shorts creator. Create content for the topic '{topic}':
1. SCRIPT: A high-energy, 20-word viral voiceover script in clear English.
2. TITLE: A high-CTR SEO title with 2 relevant hashtags.
3. DESCRIPTION: A concise 2-sentence SEO description.
4. TAGS: 10 comma-separated search tags.

Format strictly as:
SCRIPT: <script text>
TITLE: <title text>
DESCRIPTION: <description text>
TAGS: <tags>
"""
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        text = response.text
        
        script = text.split("SCRIPT:")[1].split("TITLE:")[0].strip()
        title = text.split("TITLE:")[1].split("DESCRIPTION:")[0].strip()
        desc = text.split("DESCRIPTION:")[1].split("TAGS:")[0].strip()
        tags = text.split("TAGS:")[1].strip()
        return script, title, desc, tags
    except Exception:
        return (
            f"The hidden truth behind {topic} will completely change your perspective on life today.",
            f"The Dark Secret of {topic} 🤫 #shorts",
            f"Discover the undeniable facts about {topic}. Viral insight.",
            "shorts, viral, mystery, mind blowing, facts"
        )

def fetch_broll_video():
    url = "https://assets.mixkit.co/videos/preview/mixkit-stars-in-space-1610-large.mp4"
    v_path = "broll_bg.mp4"
    try:
        v_res = requests.get(url, stream=True, timeout=8)
        if v_res.status_code == 200:
            with open(v_path, 'wb') as f:
                for chunk in v_res.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
            return v_path
    except Exception:
        pass
    return None

async def text_to_speech_async(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)

def create_text_overlay(text, width=1080, height=1920):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 60)
    except Exception:
        font = ImageFont.load_default()

    words = text.split()
    lines, current = [], ""
    for w in words:
        if len(current + " " + w) < 15:
            current += " " + w if current else w
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    
    total_h = len(lines) * 90
    start_y = (height - total_h) // 2
    
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w_len = bbox[2] - bbox[0]
        x = (width - w_len) // 2
        y = start_y + (i * 90)
        
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                draw.text((x + dx, y + dy), line, fill="black", font=font)
        
        text_color = "#FFE600" if i % 2 == 0 else "#FFFFFF"
        draw.text((x, y), line, fill=text_color, font=font)
        
    img.save("overlay.png")
    return "overlay.png"

def build_short_video(script):
    audio_path = "voice.mp3"
    asyncio.run(text_to_speech_async(script, audio_path))
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    
    bg_file = fetch_broll_video()
    if bg_file:
        try:
            v_clip = VideoFileClip(bg_file).resize(height=1920)
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
    
    final_video.write_videofile(
        out_file, 
        fps=24, 
        codec="libx264", 
        audio_codec="aac", 
        preset="ultrafast", 
        threads=4
    )
    return out_file

def get_youtube_credentials():
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }
    
    response = requests.post(token_url, data=data).json()
    access_token = response.get('access_token')
    
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=token_url,
        client_id=client_id,
        client_secret=client_secret
    )

def upload_to_youtube(video_path, title, desc, tags):
    try:
        creds = get_youtube_credentials()
        youtube = build('youtube', 'v3', credentials=creds)

        body = {
            'snippet': {
                'title': title,
                'description': f"{desc}\n\n#shorts #viral",
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
        response = request.execute()

        return f"🎉 تم الرفع بنجاح! رابط الفيديو: https://youtu.be/{response['id']}"
    except Exception as e:
        return f"❌ خطأ أثناء الرفع: {str(e)}"

# واجهة المستخدم عبر Streamlit
col1, col2 = st.columns([1, 1])

with col1:
    category = st.selectbox(
        "Content Category",
        ["Psychology & Mindset", "True Crime & Mystery", "Success & Billionaires", "Mind-Blowing Science"]
    )
    auto_upload = st.checkbox("Auto Upload to YouTube Channel", value=True)
    generate_btn = st.button("⚡ Generate & Upload Viral Short", type="primary")

if generate_btn:
    with st.spinner("جاري إعداد محتوى الفيديو والمونتاج..."):
        script, title, desc, tags = generate_viral_content(category)
        video_path = build_short_video(script)
        
        status_msg = "✅ تم إنتاج الفيديو بنجاح!"
        if auto_upload:
            upload_res = upload_to_youtube(video_path, title, desc, tags)
            status_msg += f" | {upload_res}"

    with col1:
        st.text_input("Generated SEO Title", value=title)
        st.text_input("High-Ranking Tags", value=tags)
        st.text_area("Generated Script", value=script, height=100)
        st.success(status_msg)

    with col2:
        st.video(video_path)
