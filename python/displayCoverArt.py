#!/usr/bin/env python3

import time
import sys
import logging
import threading
from logging.handlers import RotatingFileHandler
from getSongInfo import getSongInfo
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
import os
import configparser

# Restrict execution of the main thread to CPU core 3
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
scroll_offset_title = 0  # used for scrolling title text
scroll_offset_artist = 0  # used for scrolling artist text
scroll_speed = 1

# Create a lock to synchronize access to album_image
album_lock = threading.Lock()

def fetch_song_info(username, token_path, default_image):
    """
    Thread target: updates song info and album art URL in global variables 
    every 1 second (at most), without blocking the main loop.
    """
    global song_data, image_url, album_image
    # Set this thread's affinity to CPU core 2
    try:
        os.sched_setaffinity(threading.get_native_id(), {2})
    except Exception as e:
        print(f"Could not set thread affinity: {e}")
    prev_url = None
    while True:
        try:
            data = getSongInfo(username, token_path)
            if data:
                new_song_data, new_url = data
                song_data = new_song_data
                if new_url != prev_url:
                    try:
                        response = requests.get(new_url, timeout=2)
                        new_album = Image.open(BytesIO(response.content)).convert('RGB')
                        new_album.thumbnail((32, 32), Image.Resampling.LANCZOS)
                        with album_lock:
                            album_image = new_album
                        prev_url = new_url
                        image_url = new_url
                    except Exception:
                        fallback = Image.open(default_image).convert('RGB')
                        fallback.thumbnail((32, 32), Image.Resampling.LANCZOS)
                        with album_lock:
                            album_image = fallback
                        image_url = None
        except Exception as e:
            print(f"Song info fetch error: {e}")
        time.sleep(1)  # fetch at most once per second

if len(sys.argv) > 2:
    username = sys.argv[1]
    token_path = sys.argv[2]

    # Configuration file
    dir_path = os.path.dirname(__file__)
    filename = os.path.join(dir_path, '../config/rgb_options.ini')

    # Configure logger
    logging.basicConfig(
        format='%(asctime)s %(message)s',
        datefmt='%m/%d/%Y %I:%M:%S %p',
        filename='spotipy.log', 
        level=logging.INFO
    )
    logger = logging.getLogger('spotipy_logger')

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

    # Define colors for the LED matrix
    WHITE = graphics.Color(255, 255, 255)
    GREY = graphics.Color(128, 128, 128)
    SPOTIFY_GREEN = graphics.Color(30, 215, 96)
    BLACK = graphics.Color(0, 0, 0)

    # Define PIL colors for drawing
    WHITE_PIL = (255, 255, 255)
    GREY_PIL = (128, 128, 128)
    SPOTIFY_GREEN_PIL = (30, 215, 96)
    BLACK_PIL = (0, 0, 0)

    # Load LED matrix font (for graphics.DrawText) as needed
    font_title = graphics.Font()
    font_title.LoadFont("fonts/7x13.bdf")
    font_artist = font_title

    # Load a PIL font to draw text within our confined image.
    pil_font_title = ImageFont.load_default()

    # Start background thread to fetch song info
    fetch_thread = threading.Thread(
        target=fetch_song_info,
        args=(username, token_path, default_image),
        daemon=True
    )
    fetch_thread.start()

    # Create the offscreen canvas once, then re-use it in the loop.
    offscreen_canvas = matrix.CreateFrameCanvas()
    while True:
        offscreen_canvas.Clear()

        # Create composite PIL image (64×32)
        composite = Image.new('RGB', (64, 32))

        # Safely copy the album image using the lock
        with album_lock:
            local_album = album_image.copy() if album_image is not None else None

        # Left side: album art (or fallback)
        if local_album:
            composite.paste(local_album, (0, 0))
        else:
            composite.paste(Image.new('RGB', (32, 32), BLACK_PIL), (0, 0))

        # Right side panel (32×32): first draw the progress bar and play/pause icon,
        # then overlay the text area (which occupies the upper part).
        right_panel = Image.new('RGB', (32, 32), BLACK_PIL)
        draw = ImageDraw.Draw(right_panel)
        padding = 1
        inner_width = 32 - 2 * padding
        inner_height = 32 - 2 * padding
        inner_x_start = padding
        inner_y_start = padding

        # Draw progress bar on the right panel (located in the lower part)
        icon_size = 6
        progress_bar_y = inner_y_start + inner_height - icon_size
        progress_ratio = 0 if song_data["duration_ms"] == 0 else min(max(song_data["progress_ms"] / song_data["duration_ms"], 0), 1)
        filled_width = int(progress_ratio * inner_width)
        draw.rectangle([inner_x_start, progress_bar_y,
                        inner_x_start + filled_width, progress_bar_y], fill=WHITE_PIL)
        draw.rectangle([inner_x_start + filled_width, progress_bar_y,
                        inner_x_start + inner_width, progress_bar_y], fill=GREY_PIL)

        # Draw play/pause icon on the right panel (just below the progress bar)
        icon_y = progress_bar_y
        # Ensure the icon doesn't go off the bottom of the 32-pixel high panel
        if icon_y + icon_size > 32:
            icon_y = 32 - icon_size
        icon_x = inner_x_start + (inner_width - icon_size) // 2
        if song_data["is_playing"]:
            draw.rectangle([icon_x, icon_y, icon_x + 2, icon_y + icon_size], fill=SPOTIFY_GREEN_PIL)
            draw.rectangle([icon_x + 4, icon_y, icon_x + 6, icon_y + icon_size], fill=SPOTIFY_GREEN_PIL)
        else:
            triangle = [(icon_x, icon_y), (icon_x, icon_y + icon_size), (icon_x + icon_size, icon_y + icon_size // 2)]
            draw.polygon(triangle, fill=SPOTIFY_GREEN_PIL)

        # Reserve the upper area for text (from y=0 up to progress_bar_y).
        text_area_height = progress_bar_y  # this area will not cover the icons
        text_area_img = Image.new('RGB', (32, text_area_height), BLACK_PIL)
        text_draw = ImageDraw.Draw(text_area_img)

        # Get title and artist text from song_data
        title_text = song_data.get("title", "Unknown Title")
        artist_text = song_data.get("artist", "Unknown Artist")

        # Use getbbox() to measure text size
        title_bbox = pil_font_title.getbbox(title_text)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]
        artist_bbox = pil_font_title.getbbox(artist_text)
        artist_width = artist_bbox[2] - artist_bbox[0]
        artist_height = artist_bbox[3] - artist_bbox[1]

        # Layout: title on the first line and artist on the second.
        title_y = 0
        artist_y = title_height  # immediately below title

        # Draw title with horizontal scrolling if needed:
        if title_width <= 32:
            title_x = (32 - title_width) // 2
            text_draw.text((title_x, title_y), title_text, font=pil_font_title, fill=(255, 255, 255))
        else:
            gap = 5
            effective_offset_title = scroll_offset_title % (title_width + gap)
            title_x = -effective_offset_title
            text_draw.text((title_x, title_y), title_text, font=pil_font_title, fill=(255, 255, 255))
            if title_x + title_width < 32:
                text_draw.text((title_x + title_width + gap, title_y), title_text, font=pil_font_title, fill=(255, 255, 255))
            scroll_offset_title += scroll_speed

        # Draw artist with horizontal scrolling if needed (in grey):
        if artist_width <= 32:
            artist_x = (32 - artist_width) // 2
            text_draw.text((artist_x, artist_y), artist_text, font=pil_font_title, fill=GREY_PIL)
        else:
            gap = 5
            effective_offset_artist = scroll_offset_artist % (artist_width + gap)
            artist_x = -effective_offset_artist
            text_draw.text((artist_x, artist_y), artist_text, font=pil_font_title, fill=GREY_PIL)
            if artist_x + artist_width < 32:
                text_draw.text((artist_x + artist_width + gap, artist_y), artist_text, font=pil_font_title, fill=GREY_PIL)
            scroll_offset_artist += scroll_speed

        # Paste the text area into the right panel at (0,0) so it doesn't overlap the icons
        right_panel.paste(text_area_img, (0, 0))

        # Paste the right panel into the composite image at x=32 (right half)
        composite.paste(right_panel, (32, 0))

        # Update the LED matrix with the composite image
        offscreen_canvas.SetImage(composite.convert('RGB'))
        offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)
        time.sleep(0.05)

else:
    print("Usage: %s username token_path" % sys.argv[0])
    sys.exit()
