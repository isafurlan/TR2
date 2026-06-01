import time

class BufferManager:
    def __init__(self, segment_duration):
        self.buffer_level = 0.0
        self.segment_duration = segment_duration
        self.last_update_time = time.time()
        self.rebuffering_events = 0
        self.total_rebuffering_time = 0.0
        self.is_rebuffering = False
        
    def update_decay(self):
        current_time = time.time()
        elapsed = current_time - self.last_update_time
        self.last_update_time = current_time
        
        self.buffer_level = max(0, self.buffer_level - elapsed)
        
        if self.buffer_level == 0 and not self.is_rebuffering:
            self.is_rebuffering = True
            self.rebuffering_start = time.time()
            self.rebuffering_events += 1
            
    def add_segment(self):
        self.update_decay()
        self.buffer_level += self.segment_duration
        
    def check_can_play(self, min_buffer=0.1):
        self.update_decay()
        return self.buffer_level >= min_buffer
    
    def get_buffer_level(self):
        self.update_decay()
        return self.buffer_level
    
    def record_rebuffering_end(self):
        if self.is_rebuffering:
            rebuffering_duration = time.time() - self.rebuffering_start
            self.total_rebuffering_time += rebuffering_duration
            self.is_rebuffering = False