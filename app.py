import customtkinter as ctk
import threading
from queue import Queue
from PIL import Image, ImageTk
import requests
from io import BytesIO

from backend import BackendThread

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("iPodLink Companion")
        self.geometry("350x500")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")

        # --- App State for Progress Bar ---
        self.song_is_playing = False
        self.current_pos = 0
        self.current_duration = 0

        self.ui_queue = Queue()

        # --- UI Elements ---
        self.album_art_label = ctk.CTkLabel(self, text="", corner_radius=10, fg_color="gray20")
        self.album_art_label.place(relx=0.5, rely=0.3, relwidth=0.7, relheight=0.45, anchor="center")
        self.title_label = ctk.CTkLabel(self, text="Not Playing", font=("Segoe UI", 18, "bold"), anchor="w")
        self.title_label.place(relx=0.5, rely=0.6, relwidth=0.9, anchor="n")
        self.artist_album_label = ctk.CTkLabel(self, text="", font=("Segoe UI", 12), anchor="w", text_color="gray60")
        self.artist_album_label.place(relx=0.5, rely=0.67, relwidth=0.9, anchor="n")
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.place(relx=0.5, rely=0.75, relwidth=0.9, anchor="n")
        self.time_label = ctk.CTkLabel(self, text="0:00 / 0:00", font=("Segoe UI", 10), text_color="gray60")
        self.time_label.place(relx=0.5, rely=0.8, relwidth=0.9, anchor="n")
        self.volume_label = ctk.CTkLabel(self, text="Volume", font=("Segoe UI", 10), text_color="gray60", anchor="w")
        self.volume_label.place(relx=0.05, rely=0.85, anchor="w")
        self.volume_bar = ctk.CTkProgressBar(self)
        self.volume_bar.set(0)
        self.volume_bar.place(relx=0.5, rely=0.9, relwidth=0.9, anchor="n")
        self.status_label = ctk.CTkLabel(self, text="Initializing...", anchor="w", text_color="gray50")
        self.status_label.place(relx=0.02, rely=0.98, anchor="sw")

        self.placeholder_image = self.create_placeholder_image(250, 250)
        self.album_art_label.configure(image=self.placeholder_image)

        self.backend_thread = BackendThread(self.ui_queue)
        self.backend_thread.start()
        
        self.after(100, self.process_queue)
        self.after(1000, self.update_progress) # Start the "fake" progress bar timer

    def create_placeholder_image(self, width, height):
        image = Image.new('RGBA', (width, height), (40, 40, 40, 255))
        return ImageTk.PhotoImage(image)

    def fetch_and_display_image(self, url):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            img_data = response.content
            pil_image = Image.open(BytesIO(img_data))
            pil_image = pil_image.resize((250, 250), Image.LANCZOS)
            ctk_image = ImageTk.PhotoImage(pil_image)
            self.album_art_label.configure(image=ctk_image)
        except Exception:
            self.album_art_label.configure(image=self.placeholder_image)

    def format_time(self, seconds):
        if seconds < 0: return "0:00"
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes}:{seconds:02d}"

    def update_progress(self):
        """The 'fake' progress bar timer. Runs every second on the UI thread."""
        if self.song_is_playing and self.current_duration > 0:
            self.current_pos += 1
            if self.current_pos > self.current_duration:
                self.current_pos = self.current_duration
            
            self.progress_bar.set(self.current_pos / self.current_duration)
            self.time_label.configure(text=f"{self.format_time(self.current_pos)} / {self.format_time(self.current_duration)}")
        
        self.after(1000, self.update_progress)

    def process_queue(self):
        try:
            while not self.ui_queue.empty():
                message = self.ui_queue.get_nowait()
                msg_type = message.get("type")

                if msg_type == "status_update":
                    self.status_label.configure(text=message["message"])
                
                elif msg_type == "volume_update":
                    self.volume_bar.set(message["value"] / 100)

                elif msg_type == "progress_correction":
                    timeline = message["data"]
                    self.current_pos = timeline.get('position', 0)

                elif msg_type == "media_update":
                    data = message["data"]
                    title = data.get('title', '')
                    
                    if not title: # Handle song ending
                        self.song_is_playing = False
                        self.title_label.configure(text="Not Playing")
                        self.artist_album_label.configure(text="")
                        self.time_label.configure(text="0:00 / 0:00")
                        self.progress_bar.set(0)
                        self.album_art_label.configure(image=self.placeholder_image)
                        continue

                    self.song_is_playing = True
                    artist = data.get('artist', '')
                    album = data.get('album_title', '')
                    self.title_label.configure(text=title)
                    self.artist_album_label.configure(text=f"{artist} — {album}")

                    timeline = data.get('timeline', {})
                    self.current_pos = timeline.get('position', 0)
                    self.current_duration = timeline.get('end_time', 0)

                    art_url = data.get('album_art_url')
                    if art_url:
                        threading.Thread(target=self.fetch_and_display_image, args=(art_url,), daemon=True).start()
                    else:
                        self.album_art_label.configure(image=self.placeholder_image)
        finally:
            self.after(100, self.process_queue)

if __name__ == "__main__":
    app = App()
    app.mainloop()