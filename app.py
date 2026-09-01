import os
import requests
import asyncio
import random
import time
import re
import edge_tts

# ==========================================
# 1. حل توافقية مكتبة الصور MoviePy مع Pillow
# ==========================================
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
    AudioFileClip, CompositeVideoClip, ImageClip, ColorClip, VideoFileClip, concatenate_videoclips
)

# ==========================================
# 2. إعداد مفاتيح API وعملاء الذكاء الاصطناعي
# ==========================================
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
PEXELS_KEY = os.getenv("PEXELS_API_KEY", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

VOICE = "en-US-AndrewNeural"
client_groq = Groq(api_key=GROQ_KEY) if GROQ_KEY else None
client_gemini = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None


# ==========================================
# 3. دوال مساعدة لإنشاء الفيديو
# ==========================================
def set_clip_duration(clip, duration):
    return clip.set_duration(duration)

def set_clip_audio(clip, audio):
    return clip.set_audio(audio)


# ==========================================
# 4. دالة اختيار الموضوع التريند تلقائياً
# ==========================================
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


# ==========================================
# 5. دالة توليد نص السكربت المضمونة
# ==========================================
def generate_ai_content(topic, is_short=True):
    prompt = f"""You are a professional YouTube Shorts creator specializing in viral high-retention content. Topic: '{topic}'.
Write a highly captivating script optimized for a 30 to 35 seconds fast-paced video.

CRITICAL INSTRUCTION FOR SUBSCRIBERS:
End the script with a very strong call to action asking the viewer to subscribe right now.

Provide the response in this EXACT structure:

SCRIPT:
Write 65 to 85 words of voiceover text ONLY. Fast-paced, high retention, powerful hook.

TITLE:
Write a viral title with emojis and 2 hashtags.

DESCRIPTION:
Write 2-3 full sentences describing the content with a strong SUBSCRIBE call to action.

TAGS:
10 relevant keywords separated by commas.

SEARCH_QUERY:
1 english search word for background video (e.g. ocean, space, technology).
"""
    text = ""

    # 1. قائمة الموديلات الشغالة والحالية في Groq
    if client_groq:
        groq_models = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant"
        ]
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

    # 2. قائمة الموديلات المضمونة في Google Gemini
    if not text and client_gemini:
        print("🔄 Switching to Google Gemini AI Active Models...")
        gemini_models = [
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-2.0-flash-exp"
        ]
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

    # 3. الخيار الأخير (Offline Fallback) لضمان عدم توقف الـ Action نهائياً
    if not text:
        print("⚠️ All AI APIs failed or quota exceeded. Using High-Quality Fallback Template...")
        text = f"""SCRIPT:
Did you know that space is hiding secrets that baffle top scientists? From mysterious cosmic signals to massive black holes consuming entire galaxies, the universe is full of terrifying wonders. Scientists still cannot explain what lies beyond the observable universe. Subscribe right now for more mind blowing facts!

TITLE:
Space Mysteries Scientists Cannot Explain! 😱 #shorts #space

DESCRIPTION:
Discover terrifying mysteries of the universe that keep scientists awake at night. Make sure to subscribe for daily mind-blowing facts!

TAGS:
space, mysteries, science, universe, black hole, astronomy, facts, terrifying, mind blowing, viral

SEARCH_QUERY:
galaxy
"""

    script = re.search(r'SCRIPT:\s*(.*?)(?=TITLE:|DESCRIPTION:|TAGS:|SEARCH_QUERY:|$)', text, re.DOTALL | re.IGNORECASE)
    title = re.search(r'TITLE:\s*(.*?)(?=DESCRIPTION:|TAGS:|SEARCH_QUERY:|$)', text, re.DOTALL | re.IGNORECASE)
    desc = re.search(r'DESCRIPTION:\s*(.*?)(?=TAGS:|SEARCH_QUERY:|$)', text, re.DOTALL | re.IGNORECASE)
    tags = re.search(r'TAGS:\s*(.*?)(?=SEARCH_QUERY:|$)', text, re.DOTALL | re.IGNORECASE)
    query = re.search(r'SEARCH_QUERY:\s*(.*)', text, re.DOTALL | re.IGNORECASE)

    script_val = re.sub(r'[*#]', '', script.group(1)).strip() if script else ""
    title_val = re.sub(r'[*#]', '', title.group(1)).strip() if title else ""
    desc_val = re.sub(r'[*#]', '', desc.group(1)).strip() if desc else ""
    tags_val = re.sub(r'[*#]', '', tags.group(1)).strip() if tags else ""
    query_val = re.sub(r'[*#]', '', query.group(1)).strip() if query else ""

    if query_val:
        query_val = query_val.split()[0]

    return script_val, title_val, desc_val, tags_val, query_val


# ==========================================
# 6. دالة تحميل عدة مقاطع فيديو متنوعة للمشهد
# ==========================================
def fetch_multiple_pexels_videos(query, total_duration, is_short=True):
    if not PEXELS_KEY:
        raise ValueError("❌ لم يتم إضافة PEXELS_API_KEY في GitHub Secrets!")
        
    headers = {"Authorization": PEXELS_KEY}
    orientation = "portrait" if is_short else "landscape"
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=15&orientation={orientation}"
    
    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code == 200:
        videos = res.json().get("videos", [])
        if len(videos) >= 3:
            random.shuffle(videos)
            selected_videos = videos[:3]
        elif videos:
            selected_videos = videos
        else:
            raise ValueError(f"❌ تعذر العثور على مقاطع فيديو مناسبة لـ: '{query}'")

        downloaded_paths = []
        for idx, vid in enumerate(selected_videos):
            video_files = vid.get("video_files", [])
            hd_file = next((f for f in video_files if f.get("quality") == "hd"), video_files[0])
            download_url = hd_file.get("link")
            
            v_res = requests.get(download_url, stream=True, timeout=15)
            v_path = f"bg_video_{idx}.mp4"
            with open(v_path, 'wb') as f:
                for chunk in v_res.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
            downloaded_paths.append(v_path)
            
        print(f"✅ Downloaded {len(downloaded_paths)} HD Video Clips from Pexels!")
        return downloaded_paths

    raise ValueError(f"❌ تعذر الاتصال بـ Pexels!")


# ==========================================
# 7. دالة تحويل النص إلى صوت (TTS)
# ==========================================
async def text_to_speech_async(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)


# ==========================================
# 8. دالة تصميم النص وتلوين الكلمات المفتاحيّة
# ==========================================
POWER_WORDS = {"TERRIFY", "SECRET", "SECRETS", "MIND", "NEVER", "ALWAYS", "DANGEROUS", "SHOCKING", "TRICK", "TRICKS", "SCIENCE", "MYSTERY", "HIDDEN", "REAL", "SUBSCRIBE"}

def create_text_chunk_image(text_chunk, width, height, idx):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 52 if width < height else 42)
    except:
        font = ImageFont.load_default()

    words = text_chunk.split()
    lines, current = [], ""
    limit = 12 if width < height else 22
    for w in words:
        if len(current + " " + w) < limit:
            current += " " + w if current else w
        else:
            lines.append(current)
            current = w
    if current: lines.append(current)

    total_h = len(lines) * 75
    start_y = (height - total_h) // 2

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w_len = bbox[2] - bbox[0]
        x = (width - w_len) // 2
        y = start_y + (i * 75)
        
        draw.rectangle([x - 15, y - 5, x + w_len + 15, y + 60], fill=(0, 0, 0, 210))
        
        clean_line_words = line.split()
        contains_power = any(w.strip(".,!?").upper() in POWER_WORDS for w in clean_line_words)
        
        line_color = "#FF3333" if contains_power else ("#FFD700" if i % 2 == 0 else "#FFFFFF")
        draw.text((x, y), line, fill=line_color, font=font)

    img_path = f"chunk_{idx}.png"
    img.save(img_path)
    return img_path


def create_subscribe_overlay(width, height):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
    except:
        font = ImageFont.load_default()

    sub_text = "🔔 SUBSCRIBE FOR MORE!"
    bbox = draw.textbbox((0, 0), sub_text, font=font)
    w_len = bbox[2] - bbox[0]
    x = (width - w_len) // 2
    y = int(height * 0.82)

    draw.rectangle([x - 25, y - 10, x + w_len + 25, y + 65], fill=(220, 20, 60, 235), outline=(255, 255, 255, 255), width=3)
    draw.text((x, y), sub_text, fill="#FFFFFF", font=font)

    sub_path = "subscribe_cta.png"
    img.save(sub_path)
    return sub_path


def create_thumbnail_cover(title_text, width, height):
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 55 if width < height else 40)
    except:
        font = ImageFont.load_default()

    hook_text = "WAIT FOR THE END! 😱"
    bbox = draw.textbbox((0, 0), hook_text, font=font)
    w_len = bbox[2] - bbox[0]
    x = (width - w_len) // 2
    y = height // 4

    draw.rectangle([x - 20, y - 10, x + w_len + 20, y + 70], fill=(255, 204, 0, 240))
    draw.text((x, y + 5), hook_text, fill="#000000", font=font)

    cover_path = "cover_hook.png"
    img.save(cover_path)
    return cover_path


# ==========================================
# 9. دالة تجميع وإنتاج الفيديو
# ==========================================
def build_video(script, query, is_short=True):
    audio_path = "voice.mp3"
    asyncio.run(text_to_speech_async(script, audio_path))
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration

    bg_paths = fetch_multiple_pexels_videos(query, duration, is_short)

    target_w, target_h = (1080, 1920) if is_short else (1920, 1080)

    clip_dur = duration / len(bg_paths)
    processed_clips = []
    
    for p in bg_paths:
        vc = VideoFileClip(p).resize(height=target_h)
        w, h = vc.size
        if w > target_w:
            vc = vc.crop(x1=(w - target_w)//2, y1=0, width=target_w, height=target_h)
        vc = vc.loop(duration=clip_dur) if vc.duration < clip_dur else vc.subclip(0, clip_dur)
        processed_clips.append(vc)

    base_video = concatenate_videoclips(processed_clips)

    words = script.split()
    words_per_chunk = 6
    chunks = [" ".join(words[i:i+words_per_chunk]) for i in range(0, len(words), words_per_chunk)]
    chunk_duration = duration / len(chunks)

    overlay_clips = []
    for idx, chunk in enumerate(chunks):
        img_p = create_text_chunk_image(chunk, target_w, target_h, idx)
        clip = ImageClip(img_p).set_start(idx * chunk_duration).set_duration(chunk_duration)
        overlay_clips.append(clip)

    sub_img_path = create_subscribe_overlay(target_w, target_h)
    sub_start_time = duration * 0.40
    sub_clip = ImageClip(sub_img_path).set_start(sub_start_time).set_duration(duration - sub_start_time)

    cover_path = create_thumbnail_cover(script, target_w, target_h)
    cover_clip = ImageClip(cover_path).set_start(0).set_duration(0.3)

    all_clips = [base_video] + overlay_clips + [sub_clip, cover_clip]
    final_video = CompositeVideoClip(all_clips)
    final_video = set_clip_audio(final_video, audio_clip)

    out_file = "final_video.mp4"
    final_video.write_videofile(out_file, fps=24, codec="libx264", audio_codec="aac", preset="ultrafast", threads=4)
    return out_file


# ==========================================
# 10. دالة رفع الفيديو إلى يوتيوب
# ==========================================
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
            'description': f"{desc}\n\n👉 SUBSCRIBE for more mind-blowing daily facts!\n#trending #viral #shorts #facts #knowledge",
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


# ==========================================
# 11. نقطة تشغيل السكربت الرئيسية
# ==========================================
if __name__ == "__main__":
    import sys
    is_short = True if len(sys.argv) < 2 or sys.argv[1] == "short" else False
    
    print(f"🚀 Starting Automated Content Engine (Type: {'Short' if is_short else 'Long Video'})...")
    trending_topic = get_realtime_trending_topic()
    
    script, title, desc, tags, query = generate_ai_content(trending_topic, is_short)
    video_path = build_video(script, query, is_short)
    
    upload_to_youtube(video_path, title, desc, tags)
    print("✅ Process Completed Successfully!")
