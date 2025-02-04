import time
import sys
import logging
import threading
from logging.handlers import RotatingFileHandler
from getSongInfo import getSongInfo
import requests
from io import BytesIO
from PIL import Image
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
import os
import configparser

# Restrict execution to CPU core 3
os.sched_setaffinity(0, {3})

# Global shared data for threading
song_data = {
    "title": "Unknown Title",
    "artist": "Unknown Artist",
    "progress_ms": 0,
    "duration_ms": 1,
    "is_playing": False
}
image_url = None
album_image = None

def fetch_song_info(username, token_path, default_image):
    """
    Thread target: updates song info and album art URL in global variables 
    every 2 seconds, without blocking the main loop (which controls scrolling).
    """
    global song_data, image_url, album_image
    prev_url = None
    while True:
        try:
            data = getSongInfo(username, token_path)
            # data is either (song_data_dict, imageURL) or None
            if data:
                new_song_data, new_url = data

                # Update the global song info
                song_data = new_song_data
                if new_url != prev_url:
                    # Fetch album art here so main loop doesn't block on image request
                    try:
                        response = requests.get(new_url, timeout=2)
                        new_album = Image.open(BytesIO(response.content)).convert('RGB')
                        new_album.thumbnail((32, 32), Image.Resampling.LANCZOS)
                        album_image = new_album
                        prev_url = new_url
                        image_url = new_url
                    except Exception:
                        # If download fails, use default
                        fallback = Image.open(default_image).convert('RGB')
                        fallback.thumbnail((32, 32), Image.Resampling.LANCZOS)
                        album_image = fallback
                        image_url = None
        except Exception as e:
            # In case getSongInfo fails or something else
            print(f"Song info fetch error: {e}")
        time.sleep(2)  # Adjust as desired

if len(sys.argv) > 2:
    username = sys.argv[1]
    token_path = sys.argv[2]

    # Configuration file
    dir_path = os.path.dirname(__file__)
    filename = os.path.join(dir_path, '../config/rgb_options.ini')

    # Configure logger
    logging.basicConfig(format='%(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p',
                        filename='spotipy.log', level=logging.INFO)
    logger = logging.getLogger('spotipy_logger')

    # Automatically deletes logs more than 2000 bytes
    handler = RotatingFileHandler('spotipy.log', maxBytes=2000, backupCount=3)
    logger.addHandler(handler)

    # Configuration for the matrix
    config = configparser.ConfigParser()
    config.read(filename)

    options = RGBMatrixOptions()
    options.rows = 32
    options.cols = 64
    options.chain_length = int(config['DEFAULT']['chain_length'])
    options.hardware_mapping = "adafruit-hat"
    options.gpio_slowdown = int(config['DEFAULT']['gpio_slowdown'])
    options.brightness = int(config['DEFAULT']['brightness'])

    default_image = os.path.join(dir_path, config['DEFAULT']['default_image'])

    matrix = RGBMatrix(options=options)

    # Fonts: Title slightly larger, artist smaller
    font_title = graphics.Font()
    font_title.LoadFont("../fonts/7x13.bdf")

    font_artist = graphics.Font()
    font_artist.LoadFont("../fonts/5x8.bdf")  # Ensure you have this smaller font

    # Define colors
    SPOTIFY_GREEN = graphics.Color(30, 215, 96)
    WHITE = graphics.Color(255, 255, 255)
    GREY = graphics.Color(128, 128, 128)
    BLACK = graphics.Color(0, 0, 0)

    # Scrolling offsets
    scroll_speed = 1
    scroll_offset_title = 64  # Start off-screen to the right
    scroll_offset_artist = 64

    # Start background thread for fetching song info
    fetch_thread = threading.Thread(
        target=fetch_song_info,
        args=(username, token_path, default_image),
        daemon=True
    )
    fetch_thread.start()

    try:
        # The main loop handles scrolling and updating the display
        while True:
            # Create a new canvas for each frame
            canvas = matrix.CreateFrameCanvas()
            canvas.Clear()

            # Draw the album image on the left (0,0)
            if album_image:
                matrix.SetImage(album_image, 0, 0)

            # --- TEXT SCROLLING ON THE RIGHT ---
            # We'll draw Title on row ~10, Artist on row ~20
            current_title = song_data.get("title", "Unknown Title")
            current_artist = song_data.get("artist", "Unknown Artist")

            # Title
            title_len = graphics.DrawText(canvas, font_title,
                                          scroll_offset_title, 12,
                                          WHITE, current_title)
            scroll_offset_title -= scroll_speed
            # Once it's fully off-screen to the left, reset
            if scroll_offset_title + title_len < 34:
                # Reset to just beyond right boundary so it starts scrolling again
                scroll_offset_title = 66

            # Artist (smaller font)
            artist_len = graphics.DrawText(canvas, font_artist,
                                           scroll_offset_artist, 22,
                                           GREY, current_artist)
            scroll_offset_artist -= scroll_speed
            if scroll_offset_artist + artist_len < 34:
                scroll_offset_artist = 66

            # --- PROGRESS BAR (2px thick) ---
            current_progress = song_data.get("progress_ms", 0)
            current_duration = song_data.get("duration_ms", 1)
            filled_portion = int((current_progress / current_duration) * 32)

            # Draw the full bar area in grey first (2 px thick)
            for y in (26, 27):
                graphics.DrawLine(canvas, 32, y, 63, y, GREY)

            # Overdraw the filled portion in white
            for y in (26, 27):
                graphics.DrawLine(canvas, 32, y, 32 + filled_portion, y, WHITE)

            # --- PLAY/PAUSE ICON ---
            is_playing = song_data.get("is_playing", False)
            if is_playing:
                # Draw pause icon near bottom right
                # Two vertical bars: (58,24)-(58,30) & (60,24)-(60,30)
                graphics.DrawLine(canvas, 58, 24, 58, 30, SPOTIFY_GREEN)
                graphics.DrawLine(canvas, 60, 24, 60, 30, SPOTIFY_GREEN)
            else:
                # Draw play icon: triangle at bottom right
                # Points: (58,24), (58,30), (62,27)
                graphics.DrawTriangle(canvas, 58, 24, 58, 30, 62, 27, SPOTIFY_GREEN)

            # Swap to show what we drew
            canvas = matrix.SwapOnVSync(canvas)

            # Slight delay for smooth scrolling
            time.sleep(0.05)

    except KeyboardInterrupt:
        sys.exit(0)

else:
    print("Usage: %s username token_path" % sys.argv[0])
    sys.exit()
