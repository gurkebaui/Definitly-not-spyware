import time
import json
import threading
import subprocess
import sys
import os
import signal
from pynput import mouse, keyboard

# Config
OUTPUT_DIR = "training/demonstrations"
FPS = 30
VIDEO_DEVICE = ":0.0" # Standard X11 Display

AUDIO_VOLUME_MULTIPLIER = 10.5

def get_default_monitor_source():
    """Versucht, die 'Monitor'-Quelle des Standard-Audio-Ausgangs zu finden (System Audio)."""
    try:
        result = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True)
        if result.returncode == 0:
            sink_name = result.stdout.strip()
            return f"{sink_name}.monitor"
    except Exception:
        pass
    return None

def get_default_mic_source():
    """Versucht, das Standard-Mikrofon zu finden."""
    try:
        result = subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "default"

SYSTEM_AUDIO = get_default_monitor_source()
MIC_AUDIO = get_default_mic_source()

print(f"[Audio Config] System: {SYSTEM_AUDIO} | Mic: {MIC_AUDIO}")

class DataRecorder:
    def __init__(self):
        self.running = True
        self.events = []
        self.start_time = 0
        
        # Verzeichnis erstellen
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(OUTPUT_DIR, f"session_{timestamp}")
        os.makedirs(self.session_dir, exist_ok=True)
        
        self.video_path = os.path.join(self.session_dir, "screen_audio.mp4")
        self.log_path = os.path.join(self.session_dir, "events.jsonl")
        
        print(f"=== CHIMERA DATA RECORDER ===")
        print(f"Storage: {self.session_dir}")
        print(f"Controls: Recording starts immediately. Press CTRL+C to save & stop.")

    def log_event(self, event_type, data):
        if not self.running: return
        # Relativer Zeitstempel zum Start der Aufnahme
        t = time.time() - self.start_time
        entry = {
            "t": t,
            "type": event_type,
            "data": data
        }
        self.events.append(entry)

    # --- MOUSECALLBACKS ---
    def on_move(self, x, y):
        self.log_event("mouse_move", {"x": x, "y": y})

    def on_click(self, x, y, button, pressed):
        self.log_event("mouse_click", {"x": x, "y": y, "button": str(button), "pressed": pressed})

    def on_scroll(self, x, y, dx, dy):
        self.log_event("mouse_scroll", {"x": x, "y": y, "dx": dx, "dy": dy})

    # --- KEYBOARD CALLBACKS ---
    def on_key_press(self, key):
        try: k = key.char
        except: k = str(key)
        self.log_event("key_press", {"key": k})

    def on_key_release(self, key):
        try: k = key.char
        except: k = str(key)
        self.log_event("key_release", {"key": k})

    def start_ffmpeg(self):
        # FFmpeg Command für Linux (X11grab + PulseAudio Mixed)
        # Wir nutzen filter_complex, um System-Audio und Mikrofon zu mixen.
        
        cmd = [
            "ffmpeg",
            "-y", # Überschreiben
            "-video_size", "1920x1080",
            "-framerate", str(FPS),
            "-f", "x11grab", "-i", VIDEO_DEVICE, # Input 0: Video
        ]

        # Count of audio inputs
        audio_input_count = 0
        
        if SYSTEM_AUDIO:
            cmd.extend(["-f", "pulse", "-i", SYSTEM_AUDIO]) # First audio input is [1:a]
            audio_input_count += 1
        
        if MIC_AUDIO:
            cmd.extend(["-f", "pulse", "-i", MIC_AUDIO])    # Second audio input is [2:a] if system audio is present, else [1:a]
            audio_input_count += 1

        filter_complex_str = ""
        map_audio_args = []

        if audio_input_count == 2:
            # Both system audio and mic are present: apply volume to each, then mix them
            filter_complex_str = f"[1:a]volume={AUDIO_VOLUME_MULTIPLIER}[a1];[2:a]volume={AUDIO_VOLUME_MULTIPLIER}[a2];[a1][a2]amix=inputs=2:duration=first[aout]"
            map_audio_args = ["-map", "[aout]"]
        elif audio_input_count == 1:
            # Only one audio input (either system or mic): apply volume to it
            filter_complex_str = f"[1:a]volume={AUDIO_VOLUME_MULTIPLIER}[aout]"
            map_audio_args = ["-map", "[aout]"]
        else:
            print("[Warn] Kein Audio-Device gefunden. Video only.")
        
        if filter_complex_str:
            cmd.extend(["-filter_complex", filter_complex_str])
        
        cmd.extend(["-map", "0:v"]) # Always map video

        if map_audio_args:
            cmd.extend(map_audio_args) # Map audio if available

        cmd.extend([
            "-c:v", "libopenh264", "-b:v", "4M", 
            "-c:a", "aac", 
            self.video_path
        ])
        
        # Log file für FFmpeg output um Terminal sauber zu halten
        self.ff_log = open(os.path.join(self.session_dir, "ffmpeg.log"), "w")
        
        print(f"[Recorder] Starting FFmpeg (Inputs: System={bool(SYSTEM_AUDIO)}, Mic={bool(MIC_AUDIO)}, Volume={AUDIO_VOLUME_MULTIPLIER})...")
        self.process = subprocess.Popen(cmd, stdout=self.ff_log, stderr=self.ff_log, stdin=subprocess.PIPE)
        
    def run(self):
        # 1. Start Input Listeners
        m_listener = mouse.Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
        k_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        
        m_listener.start()
        k_listener.start()
        
        # 2. Start Video/Audio
        self.start_time = time.time()
        self.start_ffmpeg()
        
        print("\n[REC] RECORDING ACTIVE.")
        print("      Use your computer naturally.")
        print("      Stop with CTRL+C in this terminal.\n")
        
        try:
            while self.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[Recorder] Stopping...")
        finally:
            self.running = False
            
            # Stop FFmpeg gracefully
            if self.process:
                # Send q to ffmpeg to stop encoding cleanly
                try:
                    self.process.communicate(input=b'q', timeout=3)
                except:
                    self.process.terminate()
                self.process.wait()
                self.ff_log.close()
            
            m_listener.stop()
            k_listener.stop()
            
            # Save Event Log
            print(f"[Recorder] Saving {len(self.events)} input events...")
            with open(self.log_path, 'w') as f:
                for e in self.events:
                    f.write(json.dumps(e) + "\n")
            
            print(f"[Done] Session saved to: {self.session_dir}")

if __name__ == "__main__":
    # Check for FFmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("Error: 'ffmpeg' is not installed. Please install it (sudo apt install ffmpeg).")
        sys.exit(1)
        
    rec = DataRecorder()
    rec.run()
