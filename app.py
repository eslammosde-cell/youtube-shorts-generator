import os
import requests
import asyncio
import random
import time
import re
import sys
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

HISTORY_FILE = "used_topics.txt"

# ==========================================
# 3. إدارة سجل منع التكرار
# ==========================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip().lower() for line in f if line.strip())
    return set()

def save_to_history(topic):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(topic.strip() + "\n")

# ==========================================
# 4. جلب التريندات من مصادر متعددة (بدون احتياطي)
# ==========================================
def fetch_from_google_trends():
    url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US"
    res = requests.get(url, timeout=7)
    titles = re.findall(r'<title>(.*?)</title>', res.text)
    return [t for t in titles if "Daily Trends" not in t]

def fetch_from_reddit():
    url = "https://www.reddit.com/r/todayilearned/hot.json?limit=25"
    headers = {'User-agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers, timeout=7).json()
    posts = res.get('data', {}).get('children', [])
    return [p['data']['title'].replace("TIL ", "").replace("TIL that ", "") for p in posts if 'title' in p['data']]

def fetch_from_wikipedia():
    url = "https://en.wikipedia.org/api/rest_v1/feed/featured/today"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    res = requests.get(url, headers=headers, timeout=7).json()
    most_read = res.get('mostread', {}).get('articles', [])
    return [article['title'].replace("_", " ") for article in most_read if 'title' in article]

def get_strictly_new_trending_topic():
    used_topics = load_history()
    sources = [
        ("Google Trends", fetch_from_google_trends),
        ("Reddit TIL", fetch_from_reddit),
        ("Wikipedia Featured", fetch_from_wikipedia)
    ]
    random.shuffle(sources)

    for source_name, source_func in sources:
        try:
            print(f"🔍 Fetching trends from: {source_name}...")
            topics = source_func()
            # استبعاد الأفكار المستخدمة سابقاً
            fresh_topics = [t for t in topics if t.lower().strip() not in used_topics]
            
            if fresh_topics:
                selected = random.choice(fresh_topics)
                save_to_history(selected)
                print(f"🔥 Found NEW topic from {source_name}: '{selected}'")
                return selected
            else:
                print(f"⚠️ All topics from {source_name} were already used. Moving to next source...")
        except Exception as e:
            print(f"⚠️ Failed fetching from {source_name}: {e}. Moving to next source...")

    # إذا فشلت كل المصادر ولم يجد موضوع جديد -> إيقاف السكربت فوراً لمنع التكرار
    print("❌ ERROR: No new unique trending topic could be fetched right now. Stopping execution to prevent duplication!")
    sys.exit(0)


# ==========================================
# 5. توليد النص بالذكاء الاصطناعي (بدون نص احتياطي)
# ==========================================
def generate_ai_content(topic, is_short=True):
    prompt = f"""You are a professional YouTube Shorts creator. Topic: '{topic}'.
Write a unique, highly captivating script (30-35 secs).

CRITICAL INSTRUCTION:
End with a strong call to action asking the viewer to subscribe right now.

Provide the response in this EXACT structure:

SCRIPT:
Write 65 to 85 words of voiceover text ONLY. Fast-paced, high retention.

TITLE:
Write a viral title with emojis.

DESCRIPTION:
Write 2-3 sentences describing the content with a SUBSCRIBE call to action.

TAGS:
10 relevant keywords separated by commas.

SEARCH_QUERY:
1 simple english search word for background video (e.g. ocean, space, technology, nature).
"""
    text = ""

    # 1. تجربة نماذج Groq بالأسماء المستقرة
    if client_groq:
        groq_models = ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "llama3-70b-8192", "llama3-8b-8192"]
        for model_name in groq_models:
            try:
                response = client_groq.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_name,
                )
                text = response.choices[0].message.content
                print(f"✅ Generated script via Groq ({model_name})")
                break
            except Exception as e:
                print(f"⚠️ Groq {model_name} failed: {e}")

    # 2. تجربة Gemini بالنظام والموديلات الحديثة
    if not text and client_gemini:
        gemini_models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash-latest"]
        for g_model in gemini_models:
            try:
                response = client_gemini.models.generate_content(
                    model=g_model,
                    contents=prompt,
                )
                text = response.text
                print(f"✅ Generated script via Gemini ({g_model})")
                break
            except Exception as e:
                print(f"⚠️ Gemini {g_model} failed: {e}")

    # إذا فشلت كل النماذج، يتم إيقاف السكربت بدون رفع فيديوهات فارغة
    if not text:
        print("❌ ERROR: All AI Models failed to respond. Stopping execution to prevent uploading dummy/fallback content!")
        sys.exit(0)

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
# 6. تحميل مقاطع الفيديو من Pexels
# ==========================================
def fetch_multiple_pexels_videos(query, total_duration, is_short=True):
    if not PEXELS_KEY:
        print("❌ ERROR: PEXELS_API_KEY is missing!")
        sys.exit(0)
        
    headers = {"Authorization": PEXELS_KEY}
    orientation = "portrait" if is_short else "landscape"
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=15&orientation={orientation}"
    
    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code == 200:
        videos = res.json().get("videos", [])
        if not videos:
            url = f"https://api.pexels.com/videos/search?query=nature&per_page=10&orientation={orientation}"
            res = requests.get(url, headers=headers, timeout=10)
            videos = res.json().get("videos", [])

        if not videos:
            print(f"❌ ERROR: No background videos found on Pexels for query: {query}. Stopping process!")
            sys.exit(0)

        random.shuffle(videos)
        selected_videos = videos[:3]

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
            
        print(f"✅ Downloaded {len(downloaded_paths)} HD Video Clips!")
        return downloaded_paths

    print("❌ ERROR: Failed to communicate with Pexels API. Stopping!")
    sys.exit(0)


# ==========================================
# 7. تحويل النص إلى صوت (TTS)
# ==========================================
async def text_to_speech_async(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)


# ==========================================
# 8. تصميم الطبقات البصرية والنصوص
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
# 9. تجميع الفيديو
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
# 10. رفع الفيديو إلى يوتيوب
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

    formatted_title = f"{title} #shorts #viral" if "#shorts" not in title.lower() else title

    body = {
        'snippet': {
            'title': formatted_title,
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
# 11. التشغيل الرئيسي
# ==========================================
if __name__ == "__main__":
    import sys
    is_short = True if len(sys.argv) < 2 or sys.argv[1] == "short" else False
    
    print(f"🚀 Starting Automated Content Engine...")
    trending_topic = get_strictly_new_trending_topic()
    
    script, title, desc, tags, query = generate_ai_content(trending_topic, is_short)
    video_path = build_video(script, query, is_short)
    
    upload_to_youtube(video_path, title, desc, tags)
    print("✅ Process Completed Successfully!")
