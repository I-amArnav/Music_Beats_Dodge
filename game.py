import os
import time
import numpy as np
import pygame
from config import *
from player import Player
from obstacles import ObstacleManager, Obstacle
from audio import AudioAnalyzer

class Game:
    def __init__(self, song_path):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption('Music Dodge - Starter')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Consolas', 20)
        self.last_obstacle_near_ms = 0
        self.recent_high_count = 0

        if not os.path.isfile(song_path):
            raise FileNotFoundError(song_path)
        print('Loading audio and precomputing energy...')
        self.analyzer = AudioAnalyzer(song_path)
        print('Audio loaded: windows=', self.analyzer.num_windows)

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
        pos = pygame.mixer.music.get_pos()
        if pos < 0:
            pos = pygame.time.get_ticks() - self.start_ticks
        return pos

    def spawn_logic(self, current_ms):
        """Audio-driven and boredom spawns"""
        # --- AUDIO-DRIVEN ---
        idx = self.analyzer.get_window_index_for_ms(current_ms)
        energy = float(self.analyzer.energy[idx])
        baseline = float(self.analyzer.baseline[idx])
        ratio = energy / baseline

        time_since_last = current_ms - self.ob_manager.last_spawn_ms

        if time_since_last >= MIN_SPAWN_INTERVAL_MS:
            tier = None
            # ----- High-energy streak smoothing -----
            if ratio >= HIGH_TH:
                # First high → actual high
                if self.recent_high_count == 0:
                    tier = 'high'
                # Second high → downgrade to medium
                elif self.recent_high_count == 1:
                    tier = 'medium'
                # Third/fourth/fifth → downgrade to low
                else:
                    tier = 'low'

                self.recent_high_count = min(self.recent_high_count + 1, 4)

            elif ratio >= MEDIUM_TH:
                tier = 'medium'
                self.recent_high_count = 0

            elif ratio >= LOW_TH:
                tier = 'low'
                self.recent_high_count = 0

            else:
                # quiet region logic stays same
                if np.random.rand() < 0.05:
                    tier = 'low'
                else:
                    return
                self.recent_high_count = 0


            if tier == 'high' and (current_ms - self.ob_manager.last_heavy_ms) < HEAVY_COOLDOWN_MS:
                tier = 'medium'

            if tier is not None:
                if tier == 'low':
                    lane_count = int(np.random.choice(LOW_SIZES))
                elif tier == 'medium':
                    lane_count = int(np.random.choice(MEDIUM_SIZES))
                else:
                    lane_count = int(np.random.choice(HIGH_SIZES))

                placed = False
                for _ in range(8):
                    start = np.random.randint(0, LANES - lane_count + 1)
                    blocks = [0] * LANES

                    x_pos = SCREEN_W + SPAWN_AHEAD_PIXELS
                    dist_to_player = x_pos - PLAYER_X
                    t_new = dist_to_player / OBSTACLE_SPEED

                    for o in self.ob_manager.obstacles:
                        t_o = (o.x - PLAYER_X) / OBSTACLE_SPEED
                        if abs(t_o - t_new) < 0.6:
                            for l in range(o.lane_start, o.lane_start + o.lane_count):
                                if 0 <= l < LANES:
                                    blocks[l] = 1

                    for l in range(start, start + lane_count):
                        blocks[l] = 1

                    if 0 in blocks:
                        lane_start = start
                        placed = True
                        break

                if placed:
                    self.ob_manager.spawn(lane_start, lane_count, current_ms)

        # --- BOREDOM / TINY SPAWNS ---
        inactive_time = current_ms - self.player.last_lane_change_ms
        quiet_time = current_ms - self.last_obstacle_near_ms

        if inactive_time > 500 and quiet_time > 400:
            lane = self.player.lane
            x_pos = SCREEN_W + SPAWN_AHEAD_PIXELS

            conflicting = [
                o for o in self.ob_manager.obstacles
                if o.x > PLAYER_X and abs((o.x - x_pos) / OBSTACLE_SPEED) < 0.4
            ]

            shift_amount = int(OBSTACLE_SPEED * 0.6)
            for o in conflicting:
                o.x += shift_amount

            tiny = Obstacle(lane_start=lane, lane_count=1, x_pos=x_pos)
            self.ob_manager.obstacles.append(tiny)
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
        self.start()
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
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

            self.player.update()
            current_ms = self.ms_since_start()
            if not pygame.mixer.music.get_busy():
                print("\n\nSong finished!")
                print('\nScore is : ' + str(int(self.score)))
                print('Collision! Game over.')
                self.running = False
                break
            self.spawn_logic(current_ms)
            self.ob_manager.update(dt, current_ms)

            obstacles_near = any((PLAYER_X < o.x < SCREEN_W + 200) for o in self.ob_manager.obstacles)
            if obstacles_near:
                self.last_obstacle_near_ms = current_ms

            if self.ob_manager.check_collision(self.player.get_rect()):
                print('\n\nScore is : ' + str(int(self.score)))
                print('Collision! Game over.')
                self.running = False

            self.score += dt * 1.0
            self.obstacles_dodged += self.ob_manager.mark_passed_and_count(self.player.lane)

            self.screen.fill(BG_COLOR)
            self.draw_lanes()
            self.player.draw(self.screen)
            self.ob_manager.draw(self.screen)
            self.draw_ui(current_ms)
            pygame.display.flip()

        pygame.mixer.music.stop()
        pygame.quit()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--song', type=str, required=True)
    args = parser.parse_args()
    game = Game(args.song)
    game.run()