import sys
import os
from pydub import AudioSegment

def mp3_to_wav(mp3_path):
    if not os.path.isfile(mp3_path):
        print(f"File not found: {mp3_path}")
        return

    folder, filename = os.path.split(mp3_path)
    name, _ = os.path.splitext(filename)
    wav_path = os.path.join(folder, name + ".wav")

    audio = AudioSegment.from_mp3(mp3_path)
    audio.export(wav_path, format="wav")
    print(f"Converted '{mp3_path}' -> '{wav_path}'")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mp3_to_wav.py <name_of_mp3_file_in_'songs'_folder>")
        sys.exit(1)

    mp3_path = sys.argv[1]
    mp3_path = "songs/"+mp3_path
    mp3_to_wav(mp3_path)