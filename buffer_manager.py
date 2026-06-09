import time

class BufferManager:
    def __init__(self, segment_duration, min_play_buffer=0.1):
        self.buffer_level = 0.0
        self.segment_duration = segment_duration
        self.min_play_buffer = min_play_buffer
        self.last_update_time = time.perf_counter()
        self.playback_started = False
        self.rebuffering_events = 0
        self.total_rebuffering_time = 0.0
        self.is_rebuffering = False

    def update_decay(self):
        current_time = time.perf_counter()
        elapsed = current_time - self.last_update_time
        self.last_update_time = current_time

        if not self.playback_started:
            return 0.0

        if elapsed <= self.buffer_level:
            self.buffer_level -= elapsed
            return 0.0

        stall_duration = elapsed - self.buffer_level
        self.buffer_level = 0.0

        if not self.is_rebuffering:
            self.rebuffering_events += 1
        self.is_rebuffering = True
        self.total_rebuffering_time += stall_duration
        return stall_duration

    def add_segment(self):
        self.buffer_level += self.segment_duration
        if self.can_play():
            self.playback_started = True
            self.is_rebuffering = False

    def can_play(self, min_buffer=None):
        if min_buffer is None:
            min_buffer = self.min_play_buffer
        return self.buffer_level >= min_buffer

    def check_can_play(self, min_buffer=None):
        return self.can_play(min_buffer)

    def get_buffer_level(self):
        return self.buffer_level

    def record_rebuffering_end(self):
        self.is_rebuffering = False
