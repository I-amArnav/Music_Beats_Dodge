import os
import sys
import subprocess

SONG_DIR = os.path.join(os.path.dirname(__file__), "songs")

def choose_song():
    songs = [f for f in os.listdir(SONG_DIR) if f.lower().endswith(".wav")]
    if not songs:
        print("No songs found in the songs/ directory.")
        sys.exit(1)

    print("\nSelect a song:")
    for i, song in enumerate(songs, start=1):
        print(f"{i}. {song}")

    choice = input("\nEnter choice number: ").strip()

    try:
        idx = int(choice) - 1
        return os.path.join(SONG_DIR, songs[idx])
    except:
        print("Invalid choice.")
        sys.exit(1)

def main():
    song_path = choose_song()
    print(f"\nLaunching game with: {song_path}\n")

    # Run game.py with argument
    subprocess.run([sys.executable, "game.py", "--song", song_path])

if __name__ == "__main__":
    main()