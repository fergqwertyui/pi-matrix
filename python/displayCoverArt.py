#!/usr/bin/env python3

import time
import sys
import logging
import threading
from logging.handlers import RotatingFileHandler
from getSongInfo import getSongInfo
import requests
from io import BytesIO
from PIL import Image, ImageDraw
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
            if data:
                new_song_data, new_url = data
                song_data = new_song_data
                if new_url != prev_url:
                    try:
                        response = requests.get(new_url, timeout=2)
                        new_album = Image.open(BytesIO(response.content)).convert('RGB')
                        new_album.thumbnail((32, 32), Image.Resampling.LANCZOS)
                        album_image = new_album
                        prev_url = new_url
                        image_url = new_url
                    except Exception:
                        fallback = Image.open(default_image).convert('RGB')
                        fallback.thumbnail((32, 32), Image.Resampling.LANCZOS)
                        album_image = fallback
                        image_url = None
        except Exception as e:
            print(f"Song info fetch error: {e}")
        time.sleep(2)

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

    # Load font using rgbmatrix graphics
    font_title = graphics.Font()
    font_title.LoadFont("fonts/7x13.bdf")
    font_artist = font_title

    # Define colors
    SPOTIFY_GREEN = graphics.Color(30, 215, 96)
    WHITE = graphics.Color(255, 255, 255)
    GREY = graphics.Color(128, 128, 128)
    BLACK = graphics.Color(0, 0, 0)

    # Scrolling offsets
    scroll_speed = 1
    scroll_offset_title = 64
    scroll_offset_artist = 64

    fetch_thread = threading.Thread(
        target=fetch_song_info,
        args=(username, token_path, default_image),
        daemon=True
    )
    fetch_thread.start()

    while True:
        # Create a new offscreen canvas
        offscreen_canvas = matrix.CreateFrameCanvas()
        offscreen_canvas.Clear()

        # Build a composite PIL image
        composite = Image.new('RGB', (64, 32))
        if album_image:
            composite.paste(album_image, (0, 0))
        else:
            composite.paste(Image.new('RGB', (32, 32), BLACK), (0, 0))

        # Create the right panel
        right_panel = Image.new('RGB', (32, 32), BLACK)
        draw = ImageDraw.Draw(right_panel)
        padding = 1
        inner_width = 32 - 2 * padding
        inner_height = 32 - 2 * padding
        inner_x_start = padding
        inner_y_start = padding

        # Progress Bar
        icon_size = 6
        progress_bar_height = 2
        progress_bar_y = inner_y_start + inner_height - (icon_size + progress_bar_height)
        progress_ratio = min(max(song_data["progress_ms"] / song_data["duration_ms"], 0), 1)
        filled_width = int(progress_ratio * inner_width)

        draw.rectangle([inner_x_start, progress_bar_y,
                        inner_x_start + filled_width - 1, progress_bar_y + progress_bar_height - 1], fill=WHITE)
        draw.rectangle([inner_x_start + filled_width, progress_bar_y,
                        inner_x_start + inner_width - 1, progress_bar_y + progress_bar_height - 1], fill=GREY)

        # Play/Pause Icon
        icon_y = progress_bar_y + progress_bar_height + 1
        icon_x = inner_x_start + (inner_width - icon_size) // 2
        if song_data["is_playing"]:
            bar_width = 2
            gap = 2
            draw.rectangle([icon_x, icon_y,
                            icon_x + bar_width - 1, icon_y + icon_size - 1], fill=SPOTIFY_GREEN)
            draw.rectangle([icon_x + bar_width + gap, icon_y,
                            icon_x + bar_width + gap + bar_width - 1, icon_y + icon_size - 1], fill=SPOTIFY_GREEN)
        else:
            triangle = [(icon_x, icon_y),
                        (icon_x, icon_y + icon_size - 1),
                        (icon_x + icon_size - 1, icon_y + icon_size // 2)]
            draw.polygon(triangle, fill=SPOTIFY_GREEN)

        composite.paste(right_panel, (32, 0))
        offscreen_canvas.SetImage(composite.convert('RGB'))

        # Render text with rgbmatrix.graphics
        text_area_x = 32
        margin = 1
        text_area_width = 32 - margin * 2

        title_width = graphics.MeasureText(font_title, song_data["title"])
        artist_width = graphics.MeasureText(font_artist, song_data["artist"])
        title_baseline = 12
        artist_baseline = 24

        if title_width > text_area_width:
            text_x_title = text_area_x + margin - scroll_offset_title
            scroll_offset_title = (scroll_offset_title + scroll_speed) % (title_width + 10)
        else:
            text_x_title = text_area_x + (text_area_width - title_width) // 2

        if artist_width > text_area_width:
            text_x_artist = text_area_x + margin - scroll_offset_artist
            scroll_offset_artist = (scroll_offset_artist + scroll_speed) % (artist_width + 10)
        else:
            text_x_artist = text_area_x + (text_area_width - artist_width) // 2

        graphics.DrawText(offscreen_canvas, font_title, text_x_title, title_baseline, WHITE, song_data["title"])
        graphics.DrawText(offscreen_canvas, font_artist, text_x_artist, artist_baseline, GREY, song_data["artist"])

        # Display everything
        offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)
        time.sleep(0.05)

else:
    print("Usage: %s username token_path" % sys.argv[0])
    sys.exit()
