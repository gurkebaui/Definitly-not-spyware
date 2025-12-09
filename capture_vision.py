
import time
import json
import os
import cv2
import numpy as np
import mss
from pynput import mouse, keyboard
import threading
import sys

# Config
OUTPUT_DIR = "training/demonstrations_vision"
CHUNK_SIZE = 16
RECORD_HZ = 30 # Etwas langsamer als Ghost, damit Vision hinterherkommt

class VisionRecorder:
    def __init__(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(OUTPUT_DIR, f"session_{timestamp}")
        self.img_dir = os.path.join(self.session_dir, "images")
        os.makedirs(self.img_dir, exist_ok=True)
        self.log_path = os.path.join(self.session_dir, "data.jsonl")
        
        self.running = True
        self.chunk_buffer = []
        
        # Screen Capture Init
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[1] if len(self.sct.monitors) > 1 else self.sct.monitors[0]
        self.width = self.monitor["width"]
        self.height = self.monitor["height"]
        
        # State
        self.mx = 0.5
        self.my = 0.5
        self.clicks = {'left':0, 'right':0, 'middle':0}
        self.keys = []
        
        print(f"[REC] Vision Recorder active.")
        print(f"      Saving to: {self.session_dir}")
        print("      Stop with CTRL+C")

    def on_move(self, x, y):
        # Normalisieren auf 0..1
        self.mx = x / self.width
        self.my = y / self.height

    def on_click(self, x, y, button, pressed):
        if pressed:
            if button == mouse.Button.left: self.clicks['left'] = 1
            if button == mouse.Button.right: self.clicks['right'] = 1
            if button == mouse.Button.middle: self.clicks['middle'] = 1

    def on_press(self, key):
        try: k = key.char
        except: k = str(key)
        if k: self.keys.append(k)

    def capture_screen(self):
        try:
            sct_img = self.sct.grab(self.monitor)
            img = np.array(sct_img)
            # BGRA -> RGB
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
            # Resize für Speicherplatz (DINOv2 braucht eh kleine Bilder)
            # Wir speichern in einer vernünftigen Auflösung (z.B. 640x360 oder 320x180)
            # DINOv2 ist robust.
            img_small = cv2.resize(img, (640, 360))
            return img_small
        except:
            return None

    def loop(self):
        m_lis = mouse.Listener(on_move=self.on_move, on_click=self.on_click)
        k_lis = keyboard.Listener(on_press=self.on_press)
        m_lis.start()
        k_lis.start()
        
        frame_counter = 0
        
        try:
            while self.running:
                start_t = time.time()
                
                # Logic:
                # Wir sammeln 16 Maus-Positionen.
                # Das BILD dazu gehört zum START des Chunks (Reaktion auf das Bild).
                
                # 1. Wenn Buffer leer ist, machen wir den Screenshot (Start des Chunks)
                if len(self.chunk_buffer) == 0:
                    current_img = self.capture_screen()
                    img_filename = f"frame_{frame_counter:06d}.jpg"
                    if current_img is not None:
                        # Asynchron speichern wäre besser, aber hier keep it simple
                        # BGR für OpenCV save
                        cv2.imwrite(os.path.join(self.img_dir, img_filename), cv2.cvtColor(current_img, cv2.COLOR_RGB2BGR))
                
                # 2. Mausposition sammeln
                self.chunk_buffer.append([self.mx, self.my])
                
                # 3. Wenn Chunk voll -> Speichern
                if len(self.chunk_buffer) >= CHUNK_SIZE:
                    entry = {
                        "img": img_filename,
                        "trajectory": self.chunk_buffer, # 16 steps
                        "clicks": self.clicks.copy(),
                        "keys": self.keys.copy()
                    }
                    
                    with open(self.log_path, 'a') as f:
                        f.write(json.dumps(entry) + "\n")
                    
                    # Reset
                    self.chunk_buffer = []
                    self.clicks = {'left':0, 'right':0, 'middle':0}
                    self.keys = []
                    frame_counter += 1
                    
                    sys.stdout.write(f"\r[REC] Samples: {frame_counter}")
                    sys.stdout.flush()

                # Pacing
                elapsed = time.time() - start_t
                time.sleep(max(0, (1.0/RECORD_HZ) - elapsed))
                
        except KeyboardInterrupt:
            print("\nStopped.")
        finally:
            m_lis.stop()
            k_lis.stop()

if __name__ == "__main__":
    rec = VisionRecorder()
    rec.loop()