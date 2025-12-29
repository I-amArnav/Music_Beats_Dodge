import pygame
from config import *

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
        pygame.draw.rect(surf, (255, 80, 80), self.get_rect())

class ObstacleManager:
    def __init__(self):
        self.obstacles = []
        self.last_spawn_ms = -10000
        self.last_heavy_ms = -10000

    def spawn(self, lane_start, lane_count, current_time_ms):
        x_pos = SCREEN_W + SPAWN_AHEAD_PIXELS
        self.obstacles.append(Obstacle(lane_start, lane_count, x_pos))
        self.last_spawn_ms = current_time_ms
        if lane_count >= 4:
            self.last_heavy_ms = current_time_ms

    def update(self, dt, current_time_ms):
        for o in self.obstacles:
            o.update(dt)
        self.obstacles = [o for o in self.obstacles if o.x + o.width > -50]

    def draw(self, surf):
        for o in self.obstacles:
            o.draw(surf)

    def check_collision(self, player_rect):
        return any(player_rect.colliderect(o.get_rect()) for o in self.obstacles)

    def mark_passed_and_count(self, player_lane):
        count = 0
        for o in self.obstacles:
            if (not o.passed) and (o.x + o.width < PLAYER_X):
                obstacle_top = o.lane_start
                obstacle_bottom = o.lane_start + o.lane_count - 1
                if player_lane < obstacle_top:
                    dist = obstacle_top - player_lane
                elif player_lane > obstacle_bottom:
                    dist = player_lane - obstacle_bottom
                else:
                    dist = 0
                if dist <= 1:
                    count += 1
                o.passed = True
        return count
