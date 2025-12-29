import math
import numpy as np
from collections import deque
from pydub import AudioSegment
from config import WINDOW_MS, ENERGY_BASELINE_BUFFER

def clamp(v, a, b):
    return max(a, min(b, v))

class AudioAnalyzer:
    def __init__(self, path, window_ms=WINDOW_MS):
        self.path = path
        self.window_ms = window_ms
        self.audio = AudioSegment.from_file(path)
        self.sample_rate = self.audio.frame_rate
        self.samples = np.array(self.audio.get_array_of_samples()).astype(np.float32)
        if self.audio.channels > 1:
            self.samples = self.samples.reshape((-1, self.audio.channels))
            self.samples = self.samples.mean(axis=1)

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
            self.energy[i] = float(np.sum(window * window) / (len(window) + 1e-9))

    def _compute_running_baseline(self):
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
        baseline += 1e-9
        return baseline

    def get_window_index_for_ms(self, ms_since_start):
        idx = int(ms_since_start / self.ms_per_window)
        return clamp(idx, 0, self.num_windows - 1)

    def get_energy_for_ms(self, ms_since_start):
        return float(self.energy[self.get_window_index_for_ms(ms_since_start)])

    def get_baseline_for_ms(self, ms_since_start):
        return float(self.baseline[self.get_window_index_for_ms(ms_since_start)])
