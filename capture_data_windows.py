import time
import json
import threading
import os
import sys
import cv2
import numpy as np
import mss
import sounddevice as sd
import soundfile as sf
from pynput import mouse, keyboard

# CONFIG
OUTPUT_DIR = os.path.expanduser("~/Documents/ChimeraData")
FPS = 30
SAMPLE_RATE = 16000 # 16kHz is standard for AI Audio

class DataRecorder:
    def __init__(self):
        self.running = True
        self.events = []
        self.start_time = 0
        self.mouse_controller = mouse.Controller()
        
        # Directory Setup
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(OUTPUT_DIR, f"session_{timestamp}")
        os.makedirs(self.session_dir, exist_ok=True)
        
        self.video_path = os.path.join(self.session_dir, "screen.mp4")
        self.audio_path = os.path.join(self.session_dir, "microphone.wav")
        self.log_path = os.path.join(self.session_dir, "events.jsonl")
        
        print(f"[Storage] {self.session_dir}")

    def log_event(self, event_type, data):
        if not self.running: return
        t = time.time() - self.start_time
        self.events.append({"t": t, "type": event_type, "data": data})

    # --- INPUT LISTENERS ---
    def on_click(self, x, y, button, pressed):
        self.log_event("mouse_click", {"x": x, "y": y, "button": str(button), "pressed": pressed})
    def on_key(self, key):
        try: k = key.char
        except: k = str(key)
        self.log_event("key_press", {"key": k})



    def capture_audio(self):
        print("[Stream] Mic Recording Started...")
        # Open stream
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1) as stream:
            with sf.SoundFile(self.audio_path, mode='w', samplerate=SAMPLE_RATE, channels=1) as file:
                while self.running:
                    # Read 1024 frames (approx 60ms)
                    data, overflow = stream.read(1024)
                    file.write(data)

    def capture_video(self):
        print("[Stream] Screen Recording Started...")
        with mss.mss() as sct:
            monitor = sct.monitors[1] # Primary
            # Define Codec
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(self.video_path, fourcc, FPS, (monitor["width"], monitor["height"]))
            
            while self.running:
                loop_start = time.time()
                
                # Grab Frame
                img = np.array(sct.grab(monitor))
                frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # Mouse Cursor Overlay (Visual feedback for World Model)
                # Note: We record the cursor visually so Phase 1 (World Model) can see it
                # Getting cursor pos requires pynput or ctypes, skipping for pure speed here
                # relying on inverse dynamics to learn cursor position.
                
                out.write(frame)
                
                # FPS Lock
                elapsed = time.time() - loop_start
                wait = max(0, (1.0/FPS) - elapsed)
                time.sleep(wait)
            
            out.release()

    def capture_mouse_trajectory(self):
        """
        NEU: Speichert die Mausposition kontinuierlich (30Hz).
        Das ist essenziell für flüssige Bewegungen.
        """
        print("[Stream] Mouse Trajectory Tracking Started...")
        while self.running:
            loop_start = time.time()
            
            # Position holen
            x, y = self.mouse_controller.position
            
            # Loggen als 'mouse_pos' Event
            # Wir speichern KEIN Button-State hier, das machen die Listener
            self.log_event("mouse_pos", {"x": x, "y": y})
            
            # 30 Hz Taktung (0.033s)
            elapsed = time.time() - loop_start
            wait = max(0, 0.033 - elapsed)
            time.sleep(wait)

    def run(self):
        # Start Listeners (für Klicks & Tasten)
        m_listener = mouse.Listener(on_click=self.on_click)
        k_listener = keyboard.Listener(on_press=self.on_key)
        m_listener.start()
        k_listener.start()

        self.start_time = time.time()
        
        # Threads starten
        t_vid = threading.Thread(target=self.capture_video)
        t_aud = threading.Thread(target=self.capture_audio)
        
        # NEU: Thread für Maus-Bewegung
        t_mouse = threading.Thread(target=self.capture_mouse_trajectory)
        
        t_vid.start()
        t_aud.start()
        t_mouse.start() # Startet das Tracking
        
        print("\n=== RECORDING ACTIVE ===")
        # ... Rest bleibt gleich ...
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            # ... cleanup ...
            self.running = False
            t_vid.join()
            t_aud.join()
            t_mouse.join() # Warten bis Mouse-Thread beendet ist
            m_listener.stop()
            k_listener.stop()
            
            print(f"[Save] {len(self.events)} events logged.")
            with open(self.log_path, 'w') as f:
                for e in self.events:
                    f.write(json.dumps(e) + "\n")
            print("Done.")

if __name__ == "__main__":
    rec = DataRecorder()
    rec.run()