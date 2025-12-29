import pygame
from config import *

def clamp(v, a, b):
    return max(a, min(b, v))

class Player:
    def __init__(self):
        self.width = 40
        self.height = int(LANE_HEIGHT * 0.8)
        self.lane = LANES // 2
        self.target_lane = self.lane
        self.y = self.lane_to_y(self.lane)
        self.alive = True
        self.move_speed = 30.0
        self.last_lane_change_ms = 0
        self.last_lane = self.lane

    def lane_to_y(self, lane):
        center = lane * LANE_HEIGHT + LANE_HEIGHT / 2
        return int(center - self.height / 2)

    def move_up(self):
        self.target_lane = clamp(self.target_lane - 1, 0, LANES - 1)

    def move_down(self):
        self.target_lane = clamp(self.target_lane + 1, 0, LANES - 1)

    def update(self):
        target_y = self.lane_to_y(self.target_lane)
        dy = target_y - self.y
        if abs(dy) < 1:
            old_lane = self.lane
            self.y = target_y
            self.lane = self.target_lane
            if self.lane != old_lane:
                self.last_lane_change_ms = pygame.time.get_ticks()
        else:
            self.y += dy * 0.4

    def get_rect(self):
        return pygame.Rect(int(PLAYER_X), int(self.y), self.width, self.height)

    def draw(self, surf):
        pygame.draw.rect(surf, (200, 220, 240), self.get_rect(), border_radius=6)
