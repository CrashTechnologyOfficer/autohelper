import threading
import time
from typing import List

from autoui.capture.windows.WindowsGraphicsCaptureMethod import BaseCaptureMethod
from autoui.feature.Box import Box
from autoui.interaction.BaseInteraction import BaseInteraction
from autoui.scene.Scene import Scene
from autoui.stats.StreamStats import StreamStats


class TaskExecutor:
    tasks = []
    scenes: List[Scene] = []
    current_scene: Scene | None = None
    frame_stats = StreamStats()

    def __init__(self, method: BaseCaptureMethod, interaction: BaseInteraction, overlay=None, target_fps=10,
                 exit_event=threading.Event()):
        self.interaction = interaction
        self.method = method
        self.target_delay = 1.0 / target_fps
        self.thread = threading.Thread(target=self.execute)
        self.exit_event = exit_event
        self.thread.start()
        self.overlay = overlay

    def wait_fps(self, start):
        cost = time.time() - start
        if cost < self.target_delay:
            # print(f"TaskExecutor:cost {cost} lower than target {self.target_delay}, sleeping")
            self.exit_event.wait(self.target_delay - cost)

    def next_frame(self):
        while not self.exit_event.is_set():
            frame = self.method.get_frame()
            if frame is not None:
                return frame

    def click(self, x, y):
        self.reset_scene()
        self.interaction.click(x, y)

    def click_relative(self, x, y):
        self.reset_scene()
        self.interaction.click_relative(x, y)

    def click_box(self, box: Box, relative_x=0.5, relative_y=0.5):
        self.reset_scene()
        self.interaction.click_box(box, relative_x, relative_y)

    def reset_scene(self):
        self.current_scene = None

    def execute(self):
        print(f"execute")
        while not self.exit_event.is_set():
            frame = self.method.get_frame()
            start = time.time()
            if frame is not None:
                self.detect_scene(frame)
                # print(f"detect_scene: {self.current_scene.__class__.__name__} {(time.time() - start)}")
                if self.current_scene is not None:
                    task_executed = 0
                    for task in self.tasks:
                        task.run_frame(self, self.current_scene, frame)
                        processing_time = time.time() - start
                        task_executed += 1
                        if processing_time > 0.2:
                            print(
                                f"{task.__class__.__name__} taking too long skip to next frame {processing_time} {task_executed} {len(self.tasks)}")
                            break
                if self.overlay:
                    frame_time_ms = round((time.time() - start) * 1000)
                    self.frame_stats.add(frame_time_ms)
                    mean = self.frame_stats.mean()
                    if mean > 0:
                        # print(f"frame_stats.mean(): {mean}, fps:{round(1000 / mean)}")
                        self.overlay.draw_text("fps", 0.3, 0.01,
                                               f"Scene:{self.current_scene.__class__.__name__} FrameTime:{mean}, FPS:{round(1000 / mean)}")
            self.wait_fps(start)

    def detect_scene(self, frame):
        if self.current_scene is not None:
            # detect the last scene optimistically
            if self.current_scene.detect(frame):
                return
        for scene in self.scenes:
            if scene != self.current_scene:
                if scene.detect(frame):
                    self.current_scene = scene
                    print(f"TaskExecutor: scene changed {scene.__class__.__name__}")
                    return
        if self.current_scene is not None:
            print(f"TaskExecutor: scene changed to None")
            self.current_scene = None

    def stop(self):
        self.exit_event.set()

    def wait_until_done(self):
        self.thread.join()
