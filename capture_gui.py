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
import tkinter as tk
from tkinter import messagebox

# CONFIG
OUTPUT_DIR = os.path.expanduser("~/Documents/ChimeraData")
FPS = 30
SAMPLE_RATE = 16000

class DataRecorder:
    def __init__(self, status_callback):
        self.running = False
        self.events = []
        self.start_time = 0
        self.status_callback = status_callback
        self.threads = []
        
        # Controller für Maus-Position
        self.mouse_controller = mouse.Controller()
        
        # Listeners placeholders
        self.m_listener = None
        self.k_listener = None

    def log_event(self, event_type, data):
        if not self.running: return
        t = time.time() - self.start_time
        self.events.append({"t": t, "type": event_type, "data": data})

    # --- INPUT CALLBACKS ---
    def on_click(self, x, y, button, pressed):
        self.log_event("mouse_click", {"x": x, "y": y, "button": str(button), "pressed": pressed})

    def on_key(self, key):
        try: k = key.char
        except: k = str(key)
        self.log_event("key_press", {"key": k})

    # --- RECORDING FUNCTIONS ---
    def capture_audio(self):
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1) as stream:
                with sf.SoundFile(self.audio_path, mode='w', samplerate=SAMPLE_RATE, channels=1) as file:
                    while self.running:
                        data, overflow = stream.read(1024)
                        file.write(data)
        except Exception as e:
            print(f"Audio Error: {e}")

    def capture_video(self):
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1] # Primary Monitor
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(self.video_path, fourcc, FPS, (monitor["width"], monitor["height"]))
                
                while self.running:
                    loop_start = time.time()
                    img = np.array(sct.grab(monitor))
                    frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    out.write(frame)
                    
                    elapsed = time.time() - loop_start
                    wait = max(0, (1.0/FPS) - elapsed)
                    time.sleep(wait)
                out.release()
        except Exception as e:
            print(f"Video Error: {e}")

    def capture_mouse_trajectory(self):
        """
        NEU: Speichert die Mausposition kontinuierlich (30Hz).
        """
        try:
            while self.running:
                loop_start = time.time()
                
                # Position holen
                x, y = self.mouse_controller.position
                self.log_event("mouse_pos", {"x": x, "y": y})
                
                # 30 Hz Taktung (0.033s)
                elapsed = time.time() - loop_start
                wait = max(0, 0.033 - elapsed)
                time.sleep(wait)
        except Exception as e:
            print(f"Mouse Track Error: {e}")

    # --- CONTROL ---
    def start(self):
        if self.running: return

        # Setup Directories
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(OUTPUT_DIR, f"session_{timestamp}")
        os.makedirs(self.session_dir, exist_ok=True)
        
        self.video_path = os.path.join(self.session_dir, "screen.mp4")
        self.audio_path = os.path.join(self.session_dir, "microphone.wav")
        self.log_path = os.path.join(self.session_dir, "events.jsonl")

        self.running = True
        self.events = []
        self.start_time = time.time()

        # Start Input Listeners (Klicks & Tasten)
        self.m_listener = mouse.Listener(on_click=self.on_click)
        self.k_listener = keyboard.Listener(on_press=self.on_key)
        self.m_listener.start()
        self.k_listener.start()

        # Start Threads (Video, Audio, Maus-Pfad)
        t_vid = threading.Thread(target=self.capture_video)
        t_aud = threading.Thread(target=self.capture_audio)
        t_mouse = threading.Thread(target=self.capture_mouse_trajectory)
        
        self.threads = [t_vid, t_aud, t_mouse]
        
        for t in self.threads:
            t.start()

        self.status_callback(f"Aufnahme läuft...\nSpeicherort:\n{self.session_dir}")

    def stop(self):
        if not self.running: return
        
        self.status_callback("Speichere Dateien... Bitte warten.")
        self.running = False
        
        # Stop Listeners
        if self.m_listener: self.m_listener.stop()
        if self.k_listener: self.k_listener.stop()

        # Wait for threads to finish
        for t in self.threads:
            t.join()

        # Save JSON Logs
        with open(self.log_path, 'w') as f:
            for e in self.events:
                f.write(json.dumps(e) + "\n")
        
        self.status_callback(f"Fertig! {len(self.events)} Events gespeichert.")

# --- GUI CLASS ---
class RecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Chimera Data Recorder V2")
        self.root.geometry("400x280")
        self.root.resizable(False, False)

        self.recorder = DataRecorder(self.update_status)

        # UI Elements
        self.btn_start = tk.Button(root, text="Aufnahme Starten", command=self.start_rec, bg="#d4f7d4", font=("Arial", 12, "bold"))
        self.btn_start.pack(pady=15, fill='x', padx=30)

        self.btn_stop = tk.Button(root, text="Aufnahme Stoppen", command=self.stop_rec, bg="#f7d4d4", font=("Arial", 12, "bold"), state="disabled")
        self.btn_stop.pack(pady=5, fill='x', padx=30)

        self.lbl_status = tk.Label(root, text="Bereit zur Aufnahme.", wraplength=380, justify="center", fg="#333")
        self.lbl_status.pack(pady=20)
        
        self.lbl_info = tk.Label(root, text="Inkl. 30Hz Maus-Tracking & Audio", font=("Arial", 8), fg="#888")
        self.lbl_info.pack(side="bottom", pady=5)

    def update_status(self, text):
        self.lbl_status.config(text=text)

    def start_rec(self):
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        threading.Thread(target=self.recorder.start).start()

    def stop_rec(self):
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        threading.Thread(target=self.recorder.stop).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = RecorderApp(root)
    root.mainloop()