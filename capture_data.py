
import time
import json
import os
import sys
import numpy as np
from pynput import mouse, keyboard
import threading

OUTPUT_DIR = "training/demonstrations"
CHUNK_SIZE = 16
RECORD_HZ = 60 # Wir nehmen hochfrequent auf, um glatte Kurven zu haben

class GhostRecorder:
    def __init__(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(OUTPUT_DIR, f"session_{timestamp}")
        os.makedirs(self.session_dir, exist_ok=True)
        self.log_path = os.path.join(self.session_dir, "trajectory.jsonl")
        
        self.running = True
        self.mouse_buffer = []
        self.chunk_buffer = []
        
        # Aktueller Status
        self.mx = 0.5
        self.my = 0.5
        self.screen_w = 2560 # Anpassen an deinen Monitor oder automatisch
        self.screen_h = 1440
        self.clicks = {'left':0, 'right':0, 'middle':0}
        self.keys = []
        
        print(f"[REC] Ghost Recorder active. Saving to {self.session_dir}")
        print("[REC] Press CTRL+C to stop.")

    def on_move(self, x, y):
        self.mx = x / self.screen_w
        self.my = y / self.screen_h

    def on_click(self, x, y, button, pressed):
        if pressed:
            if button == mouse.Button.left: self.clicks['left'] = 1
            if button == mouse.Button.right: self.clicks['right'] = 1
            if button == mouse.Button.middle: self.clicks['middle'] = 1

    def on_press(self, key):
        try: k = key.char
        except: k = str(key)
        self.keys.append(k)

    def loop(self):
        # Listener starten
        m_lis = mouse.Listener(on_move=self.on_move, on_click=self.on_click)
        k_lis = keyboard.Listener(on_press=self.on_press)
        m_lis.start()
        k_lis.start()
        
        # Aufnahmeschleife
        while self.running:
            start_t = time.time()
            
            # Aktuellen Zustand snapshotten
            frame_data = [self.mx, self.my]
            self.chunk_buffer.append(frame_data)
            
            # Wenn Chunk voll (16 Frames)
            if len(self.chunk_buffer) >= CHUNK_SIZE:
                # Wir speichern: 
                # - Die Trajektorie (16x2)
                # - Die Klicks die im Chunk passiert sind (als 'Wahrheit' für den ganzen Chunk)
                # - Tasten
                
                entry = {
                    "t": time.time(),
                    "trajectory": self.chunk_buffer, # [[x,y], [x,y]...]
                    "clicks": self.clicks.copy(),
                    "keys": self.keys.copy()
                }
                
                # Schreiben
                with open(self.log_path, 'a') as f:
                    f.write(json.dumps(entry) + "\n")
                
                # Reset
                self.chunk_buffer = []
                self.clicks = {'left':0, 'right':0, 'middle':0}
                self.keys = []
                
                sys.stdout.write(f"\r[REC] Captured chunks: {time.time():.1f}")
                sys.stdout.flush()

            # Wait to match HZ
            elapsed = time.time() - start_t
            sleep_t = max(0, (1.0/RECORD_HZ) - elapsed)
            time.sleep(sleep_t)

        m_lis.stop()
        k_lis.stop()

if __name__ == "__main__":
    rec = GhostRecorder()
    try:
        rec.loop()
    except KeyboardInterrupt:
        rec.running = False
        print("\n[REC] Saved.")