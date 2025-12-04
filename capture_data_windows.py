import time
import json
import threading
import subprocess
import sys
import os
import signal
# pynput will be installed by the setup script
try:
    from pynput import mouse, keyboard
except ImportError:
    print("pynput not found. Please run 'pip install pynput'")
    sys.exit(1)

# Config
OUTPUT_DIR = os.path.expanduser("~/Documents/ChimeraData") # Better default for Windows
FPS = 30

class DataRecorder:
    def __init__(self):
        self.running = True
        self.events = []
        self.start_time = 0
        
        # Create directory
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(OUTPUT_DIR, f"session_{timestamp}")
        os.makedirs(self.session_dir, exist_ok=True)
        
        self.video_path = os.path.join(self.session_dir, "screen.mp4")
        self.log_path = os.path.join(self.session_dir, "events.jsonl")
        
        print(f"=== CHIMERA DATA RECORDER (WINDOWS) ===")
        print(f"Storage: {self.session_dir}")
        print(f"Controls: Recording starts immediately. Press CTRL+C to save & stop.")

    def log_event(self, event_type, data):
        if not self.running: return
        t = time.time() - self.start_time
        entry = {
            "t": t,
            "type": event_type,
            "data": data
        }
        self.events.append(entry)

    # --- MOUSE CALLBACKS ---
    def on_move(self, x, y):
        self.log_event("mouse_move", {"x": x, "y": y})

    def on_click(self, x, y, button, pressed):
        self.log_event("mouse_click", {"x": x, "y": y, "button": str(button), "pressed": pressed})

    def on_scroll(self, x, y, dx, dy):
        self.log_event("mouse_scroll", {"x": x, "y": y, "dx": dx, "dy": dy})

    # --- KEYBOARDCALLBACKS ---
    def on_key_press(self, key):
        try: k = key.char
        except: k = str(key)
        self.log_event("key_press", {"key": k})

    def on_key_release(self, key):
        try: k = key.char
        except: k = str(key)
        self.log_event("key_release", {"key": k})

    def start_ffmpeg(self):
        # FFmpeg Command for Windows (gdigrab)
        # Note: Audio recording on Windows requires a specific DirectShow device name.
        # This script captures VIDEO ONLY to ensure compatibility.
        # To add audio, you would need: -f dshow -i audio="Microphone (Realtek Audio)"
        
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "gdigrab", 
            "-framerate", str(FPS),
            "-i", "desktop",
            "-c:v", "libx264", 
            "-preset", "ultrafast", 
            "-crf", "25",
            self.video_path
        ]
        
        self.ff_log = open(os.path.join(self.session_dir, "ffmpeg.log"), "w")
        
        print("[Recorder] Starting FFmpeg (Screen)...\n")
        # Creation flag specifically for Windows to hide the console window of ffmpeg if run in background
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
            
        self.process = subprocess.Popen(cmd, stdout=self.ff_log, stderr=self.ff_log, stdin=subprocess.PIPE, creationflags=creationflags)
        
    def run(self):
        m_listener = mouse.Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
        k_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        
        m_listener.start()
        k_listener.start()
        
        self.start_time = time.time()
        self.start_ffmpeg()
        
        print("\n[REC] RECORDING ACTIVE.")
        print("      Stop with CTRL+C in this terminal.\n")
        
        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[Recorder] Stopping...")
        finally:
            self.running = False
            
            if self.process:
                try:
                    self.process.communicate(input=b'q', timeout=3)
                except:
                    self.process.terminate()
                self.process.wait()
                self.ff_log.close()
            
            m_listener.stop()
            k_listener.stop()
            
            print(f"[Recorder] Saving {len(self.events)} input events...")
            with open(self.log_path, 'w') as f:
                for e in self.events:
                    f.write(json.dumps(e) + "\n")
            
            print(f"[Done] Session saved to: {self.session_dir}")

if __name__ == "__main__":
    # Simple check if ffmpeg is reachable
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("Error: 'ffmpeg' is not installed or not in PATH.")
        print("Please install FFmpeg and add it to your System PATH.")
        sys.exit(1)
        
    rec = DataRecorder()
    rec.run()
