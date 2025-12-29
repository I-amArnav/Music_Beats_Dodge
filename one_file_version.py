"""
Music Dodge - Starter (single-file, modular) for pygame

How this file is organized (modules/classes inside one file for simplicity):
- Config (constants)
- AudioAnalyzer : loads a WAV file (via pydub) -> precomputes energy per window
- Player : handles lane movement, drawing, collision
- Obstacle + ObstacleManager : creates lane-blocking walls based on energy tiers
- Game : pygame loop, playback (pygame.mixer), spawning, scoring, UI

Notes & dependencies
--------------------
Requires:
    pip install pygame pydub numpy

For simplicity use WAV files (no ffmpeg needed). If you want MP3, install ffmpeg and pydub will use it.

Run:
    python music-dodge-game-starter.py --song songs/your_song.wav

"""

import sys
import os
import math
import argparse
import time
from collections import deque

import pygame
import numpy as np
from pydub import AudioSegment

# ------------------ Config ------------------
SCREEN_W = 800
SCREEN_H = 600
FPS = 60
LANES = 10
LANE_HEIGHT = SCREEN_H / LANES
PLAYER_X = 100  # fixed x position
PLAYER_SPEED_LANES = 1  # lanes per keypress (snap)
OBSTACLE_SPEED = 300  # pixels per second
SPAWN_AHEAD_PIXELS = 900  # spawn obstacles this far to the right
WINDOW_MS = 100  # energy window in milliseconds
ENERGY_BASELINE_BUFFER = 50  # number of windows used to compute running baseline

# Energy thresholds (multipliers over baseline)
LOW_TH = 1.05
MEDIUM_TH = 1.5
HIGH_TH = 2.2

# Obstacle sizes per tier (in lane-count)
LOW_SIZES = [1, 1, 2]
MEDIUM_SIZES = [2, 3]
HIGH_SIZES = [4, 5, 6]

# Cooldowns & safety
MIN_SPAWN_INTERVAL_MS = 150  # minimum ms between spawns
HEAVY_COOLDOWN_MS = 600

# Colors
BG_COLOR = (10, 10, 20)
LANE_COLOR = (30, 30, 40)
PLAYER_COLOR = (200, 220, 240)
OBSTACLE_COLOR = (255, 80, 80)
TEXT_COLOR = (230, 230, 230)

# ------------------ Utilities ------------------

def clamp(v, a, b):
    return max(a, min(b, v))

# ------------------ Audio Analyzer ------------------
class AudioAnalyzer:
    """
    Loads audio (wav or mp3) using pydub, converts to mono floats, and precomputes
    energy per WINDOW_MS frame. Also provides a baseline (running median or average)
    for spike detection.
    """
    def __init__(self, path, window_ms=WINDOW_MS):
        self.path = path
        self.window_ms = window_ms
        self.audio = AudioSegment.from_file(path)
        self.sample_rate = self.audio.frame_rate
        self.samples = np.array(self.audio.get_array_of_samples()).astype(np.float32)
        if self.audio.channels > 1:
            self.samples = self.samples.reshape((-1, self.audio.channels))
            # convert to mono by averaging channels
            self.samples = self.samples.mean(axis=1)
        # normalize to -1..1
        maxv = np.max(np.abs(self.samples)) or 1.0
        self.samples = self.samples / maxv

        self.ms_per_window = window_ms
        self.samples_per_window = int(self.sample_rate * (window_ms / 1000.0))
        self.num_windows = max(1, int(math.ceil(len(self.samples) / float(self.samples_per_window))))

        self.energy = np.zeros(self.num_windows, dtype=np.float32)
        self._compute_energy()
        self.baseline = self._compute_running_baseline()

    def _compute_energy(self):
        for i in range(self.num_windows):
            start = i * self.samples_per_window
            end = start + self.samples_per_window
            window = self.samples[start:end]
            # energy is sum of squares (RMS-like)
            self.energy[i] = float(np.sum(window * window) / (len(window) + 1e-9))

    def _compute_running_baseline(self):
        # simple moving average baseline using previous N windows
        N = ENERGY_BASELINE_BUFFER
        baseline = np.zeros_like(self.energy)
        cum = 0.0
        dq = deque()
        for i, e in enumerate(self.energy):
            dq.append(e)
            cum += e
            if len(dq) > N:
                cum -= dq.popleft()
            baseline[i] = cum / len(dq)
        # avoid zeros
        baseline += 1e-9
        return baseline

    def get_window_index_for_ms(self, ms_since_start):
        idx = int(ms_since_start / self.ms_per_window)
        return clamp(idx, 0, self.num_windows - 1)

    def get_energy_for_ms(self, ms_since_start):
        return float(self.energy[self.get_window_index_for_ms(ms_since_start)])

    def get_baseline_for_ms(self, ms_since_start):
        return float(self.baseline[self.get_window_index_for_ms(ms_since_start)])

# ------------------ Player ------------------
class Player:
    def __init__(self):
        self.width = 40
        self.height = int(LANE_HEIGHT * 0.8)
        self.lane = LANES // 2  # start middle-ish
        self.target_lane = self.lane
        self.y = self.lane_to_y(self.lane)
        self.alive = True
        # movement smoothing
        self.last_lane_change_ms = 0
        self.last_lane = self.lane

    def lane_to_y(self, lane):
        # lane 0 is top
        center = lane * LANE_HEIGHT + LANE_HEIGHT / 2
        return int(center - self.height / 2)

    def move_up(self):
        self.target_lane = clamp(self.target_lane - 1, 0, LANES - 1)

    def move_down(self):
        self.target_lane = clamp(self.target_lane + 1, 0, LANES - 1)

    def update(self):
        target_y = self.lane_to_y(self.target_lane)
        # smooth approach
        dy = target_y - self.y
        if abs(dy) < 1:
            old_lane = self.lane
            self.y = target_y
            self.lane = self.target_lane
            if self.lane != old_lane:
                self.last_lane_change_ms = pygame.time.get_ticks()
        else:
            self.y += dy * 0.4  # smoothing factor

    def get_rect(self):
        return pygame.Rect(int(PLAYER_X), int(self.y), self.width, self.height)

    def draw(self, surf):
        pygame.draw.rect(surf, PLAYER_COLOR, self.get_rect(), border_radius=6)

# ------------------ Obstacles ------------------
class Obstacle:
    def __init__(self, lane_start, lane_count, x_pos, width_px=40):
        self.lane_start = lane_start
        self.lane_count = lane_count
        self.x = x_pos
        self.width = width_px
        self.passed = False

    def get_rect(self):
        top = int(self.lane_start * LANE_HEIGHT)
        height = int(self.lane_count * LANE_HEIGHT)
        return pygame.Rect(int(self.x), top, int(self.width), height)

    def update(self, dt):
        self.x -= OBSTACLE_SPEED * dt

    def draw(self, surf):
        pygame.draw.rect(surf, OBSTACLE_COLOR, self.get_rect())

class ObstacleManager:
    def __init__(self):
        self.obstacles = []
        self.last_spawn_ms = -10000
        self.last_heavy_ms = -10000

    def spawn(self, lane_start, lane_count, current_time_ms):
        # choose lane_start so that it fits within lanes
        max_start = LANES - lane_count
        # ensure not impossible: check occupancy of future area
        # simple check: ensure that not all lanes would be blocked at the same x-range
        # We will avoid spawning if it would block all lanes at spawn time
        x_pos = SCREEN_W + SPAWN_AHEAD_PIXELS
        new_obs = Obstacle(lane_start, lane_count, x_pos)
        # a more advanced check would examine future occupancy - keep simple here
        self.obstacles.append(new_obs)
        self.last_spawn_ms = current_time_ms
        if lane_count >= 4:
            self.last_heavy_ms = current_time_ms

    def update(self, dt, current_time_ms):
        for o in self.obstacles:
            o.update(dt)
        # remove offscreen
        self.obstacles = [o for o in self.obstacles if o.x + o.width > -50]

    def draw(self, surf):
        for o in self.obstacles:
            o.draw(surf)

    def check_collision(self, player_rect):
        for o in self.obstacles:
            if player_rect.colliderect(o.get_rect()):
                return True
        return False

    def mark_passed_and_count(self,player_lane):
        count = 0
        for o in self.obstacles:
            if (not o.passed) and (o.x + o.width < PLAYER_X):
                obstacle_top = o.lane_start
                obstacle_bottom = o.lane_start + o.lane_count - 1
                # closest lane distance from player
                if player_lane < obstacle_top:
                    dist = obstacle_top - player_lane
                elif player_lane > obstacle_bottom:
                    dist = player_lane - obstacle_bottom
                else:
                    dist = 0  # would have been a collision if x aligned
                # only count if obstacle passed close (<= 1 lane gap)
                if dist <= 1:
                    count += 1
                o.passed = True
        return count

# ------------------ Game ------------------
class Game:
    def __init__(self, song_path):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption('Music Dodge - Starter')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Consolas', 20)

        self.last_obstacle_near_ms = 0

        self.song_path = song_path
        if not os.path.isfile(song_path):
            raise FileNotFoundError(song_path)

        # audio analysis
        print('Loading audio and precomputing energy...')
        self.analyzer = AudioAnalyzer(song_path)
        print('Audio loaded: windows=', self.analyzer.num_windows)

        # prepare music playback
        pygame.mixer.music.load(song_path)

        self.player = Player()
        self.ob_manager = ObstacleManager()
        self.score = 0
        self.obstacles_dodged = 0
        self.running = True
        self.started = False
        self.start_ticks = 0

    def start(self):
        pygame.mixer.music.play()
        self.start_ticks = pygame.time.get_ticks()
        self.started = True

    def stop(self):
        pygame.mixer.music.stop()
        self.started = False

    def ms_since_start(self):
        if not self.started:
            return 0
        # pygame.mixer.music.get_pos() returns ms since music started
        pos = pygame.mixer.music.get_pos()
        # If pos == -1 sometimes when stopped; fallback to ticks
        if pos < 0:
            pos = pygame.time.get_ticks() - self.start_ticks
        return pos

    def spawn_logic(self, current_ms):
        """
        Handles both:
        (1) Audio-driven obstacle spawning
        (2) Boredom spawns (tiny nudges when player is inactive)
        """

        # -------------------- (1) AUDIO-DRIVEN SPAWNING --------------------
        idx = self.analyzer.get_window_index_for_ms(current_ms)
        energy = float(self.analyzer.energy[idx])
        baseline = float(self.analyzer.baseline[idx])
        ratio = energy / baseline

        time_since_last = current_ms - self.ob_manager.last_spawn_ms

        # enforce minimum spawn interval
        if time_since_last >= MIN_SPAWN_INTERVAL_MS:
            # determine tier
            if ratio >= HIGH_TH:
                tier = 'high'
            elif ratio >= MEDIUM_TH:
                tier = 'medium'
            elif ratio >= LOW_TH:
                tier = 'low'
            else:
                # too quiet, occasional low spawn
                if np.random.rand() < 0.05:
                    tier = 'low'
                else:
                    tier = None

            # upgrade/downgrade based on cooldowns
            if tier == 'high' and (current_ms - self.ob_manager.last_heavy_ms) < HEAVY_COOLDOWN_MS:
                tier = 'medium'

            if tier is not None:
                if tier == 'low':
                    lane_count = int(np.random.choice(LOW_SIZES))
                elif tier == 'medium':
                    lane_count = int(np.random.choice(MEDIUM_SIZES))
                else:
                    lane_count = int(np.random.choice(HIGH_SIZES))

                # place obstacle safely (avoid fully blocking)
                placed = False
                for _ in range(8):
                    start = np.random.randint(0, LANES - lane_count + 1)

                    blocks = [0] * LANES

                    # estimate new obstacle's time to reach player
                    x_pos = SCREEN_W + SPAWN_AHEAD_PIXELS
                    dist_to_player = x_pos - PLAYER_X
                    t_new = dist_to_player / OBSTACLE_SPEED

                    # check conflicts with existing obstacles
                    for o in self.ob_manager.obstacles:
                        t_o = (o.x - PLAYER_X) / OBSTACLE_SPEED
                        if abs(t_o - t_new) < 0.6:
                            for l in range(o.lane_start, o.lane_start + o.lane_count):
                                if 0 <= l < LANES:
                                    blocks[l] = 1

                    # apply new block
                    for l in range(start, start + lane_count):
                        blocks[l] = 1

                    # ensure at least 1 lane open
                    if 0 in blocks:
                        placed = True
                        lane_start = start
                        break

                if placed:
                    self.ob_manager.spawn(lane_start, lane_count, current_ms)

        # -------------------- (2) BOREDOM TINY SPAWN --------------------
        inactive_time = current_ms - self.player.last_lane_change_ms
        quiet_time = current_ms - self.last_obstacle_near_ms

        if inactive_time > 500 and quiet_time > 400:
            lane = self.player.lane
            x_pos = SCREEN_W + SPAWN_AHEAD_PIXELS

            # find obstacles spawning too close (within 0.4 sec)
            conflicting = [
                o for o in self.ob_manager.obstacles
                if o.x > PLAYER_X and abs((o.x - x_pos) / OBSTACLE_SPEED) < 0.4
            ]

            # shift them ahead enough to break timing conflict (>0.4 sec)
            shift_amount = int(OBSTACLE_SPEED * 0.6)  # 0.6 seconds → safe
            for o in conflicting:
                o.x += shift_amount

            # now spawn the tiny nudge obstacle
            tiny = Obstacle(lane_start=lane, lane_count=1, x_pos=x_pos)
            self.ob_manager.obstacles.append(tiny)

            # tiny spawn also counts as a cooldown event
            self.ob_manager.last_spawn_ms = current_ms
            self.player.last_lane_change_ms = current_ms

    def draw_lanes(self):
        for i in range(LANES):
            y = int(i * LANE_HEIGHT)
            pygame.draw.rect(self.screen, LANE_COLOR, (0, y, SCREEN_W, int(LANE_HEIGHT)), 1)

    def draw_ui(self, ms):
        txt = f"Score: {int(self.score)}  Dodged: {self.obstacles_dodged}  Time: {ms/1000:.1f}s"
        surf = self.font.render(txt, True, TEXT_COLOR)
        self.screen.blit(surf, (10, 10))

    def run(self):
        # start playback
        self.start()
        last_time = time.time()
        while self.running:
            # Stop the game cleanly when the song finishes
            if not pygame.mixer.music.get_busy():
                print("\n\nSong finished! Your score is " + str(int(self.score)))
                self.running = False
                continue

            dt = self.clock.tick(FPS) / 1000.0
            # events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        self.player.move_up()
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.player.move_down()

            # update
            self.player.update()
            current_ms = self.ms_since_start()
            # spawn logic based on audio
            self.spawn_logic(current_ms)

            self.ob_manager.update(dt, current_ms)
            # --- Step 2: Track when any obstacle is close to the screen ---
            # If an obstacle is somewhere within or near the visible area
            obstacles_near = any(
                (PLAYER_X < o.x < SCREEN_W + 200)
                for o in self.ob_manager.obstacles
            )

            if obstacles_near:
                self.last_obstacle_near_ms = current_ms

            # collision
            if self.ob_manager.check_collision(self.player.get_rect()):
                print('\n\nScore is : ' + str(int(self.score)))
                print('Collision! Game over.')
                self.running = False

            # scoring
            self.score += dt * 1.0  # 1 point per second
            self.obstacles_dodged += self.ob_manager.mark_passed_and_count(self.player.lane)

            # draw
            self.screen.fill(BG_COLOR)
            self.draw_lanes()
            self.player.draw(self.screen)
            self.ob_manager.draw(self.screen)
            self.draw_ui(current_ms)

            pygame.display.flip()

        # cleanup
        pygame.mixer.music.stop()
        pygame.quit()

# ------------------ Entry point ------------------
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--song', type=str, required=True, help='Path to WAV (or MP3 with ffmpeg)')
    args = parser.parse_args()

    game = Game(args.song)
    game.run()