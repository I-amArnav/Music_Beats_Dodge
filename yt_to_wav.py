import yt_dlp
import os
import re

# Ensure the songs folder exists
SONGS_FOLDER = "songs"
os.makedirs(SONGS_FOLDER, exist_ok=True)

def safe_filename(name):
    """Replace illegal filesystem characters with underscores."""
    return re.sub(r'[\\/*?:"<>|]', "_", name)

url = input("Enter YouTube video URL: ").strip()

ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': os.path.join(SONGS_FOLDER, '%(title)s.%(ext)s'),
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'wav',
        'preferredquality': '192',
    }],
    'quiet': False,
    'progress_hooks': [],
    'restrictfilenames': True  # ensures filenames are filesystem-safe
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=True)
    title = safe_filename(info.get('title', 'song'))
    output_file = os.path.join(SONGS_FOLDER, f"{title}.wav")

print(f"Downloaded and converted to: {output_file}")