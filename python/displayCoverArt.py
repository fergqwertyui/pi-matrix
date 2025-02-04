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
            print(f"Song info fetch error: {e}")
        time.sleep(2)  # Adjust as desired

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

            current_title = song_data.get("title", "Unknown Title")
            current_artist = song_data.get("artist", "Unknown Artist")
            progress_ms = song_data.get("progress_ms", 0)
            duration_ms = song_data.get("duration_ms", 1)  # avoid division by zero
            is_playing = song_data.get("is_playing", False)

            title_width, title_height = draw.textsize(current_title, font=font_title)
            title_y = inner_y_start  # e.g. y = 1


            # --- Scrolling Song Title ---
            if title_width > inner_width:
                max_offset_title = title_width - inner_width
                scroll_offset_title = (scroll_offset_title + scroll_speed) % (max_offset_title + 10)
                # Only scroll up to max_offset_title before pausing briefly
                offset_title = scroll_offset_title if scroll_offset_title <= max_offset_title else max_offset_title
                draw.text((inner_x_start - offset_title, title_y), current_title, font=font_title, fill=WHITE)
            else:
                centered_x = (inner_width - title_width) // 2
                draw.text((inner_x_start + centered_x, title_y), current_title, font=font_title, fill=WHITE)


            # --- Scrolling Artist Name ---
            artist_width, artist_height = draw.textsize(current_artist, font=font_artist)
            artist_y = title_y + title_height

            if artist_width > inner_width:
                max_offset_artist = artist_width - inner_width
                scroll_offset_artist = (scroll_offset_artist + scroll_speed) % (max_offset_artist + 10)
                offset_artist = scroll_offset_artist if scroll_offset_artist <= max_offset_artist else max_offset_artist
                draw.text((inner_x_start - offset_artist, artist_y), current_artist, font=font_artist, fill=GREY)
            else:
                centered_x = (inner_width - artist_width) // 2
                draw.text((inner_x_start + centered_x, artist_y), current_artist, font=font_artist, fill=GREY)

            # Create composite image (64x32): left half for album art, right half for info
            composite = Image.new('RGB', (64, 32))
            if album_image:
                composite.paste(album_image, (0, 0))
            else:
                composite.paste(Image.new('RGB', (32, 32), BLACK), (0, 0))

            # Build the right 32x32 info panel with 1px padding all around
            right_panel = Image.new('RGB', (32, 32), BLACK)
            draw = ImageDraw.Draw(right_panel)
            padding = 1  # 1px border
            inner_width = 32 - 2 * padding   # 30px drawing width
            inner_height = 32 - 2 * padding  # 30px drawing height
            inner_x_start = padding
            inner_y_start = padding

            # --- Progress Bar (2px thick) ---
            # Position progress bar above the icon at the bottom of the inner area
            icon_size = 6  # icon height in pixels
            progress_bar_height = 2
            # Calculate progress bar Y so that the icon (with a 1px gap) fits at the very bottom
            progress_bar_y = inner_y_start + inner_height - (icon_size + progress_bar_height)
            progress_ratio = min(max(progress_ms / duration_ms, 0), 1)
            filled_width = int(progress_ratio * inner_width)
            # Draw filled portion (white)
            draw.rectangle([inner_x_start, progress_bar_y,
                            inner_x_start + filled_width - 1, progress_bar_y + progress_bar_height - 1],
                           fill=WHITE)
            # Draw unfilled portion (grey)
            draw.rectangle([inner_x_start + filled_width, progress_bar_y,
                            inner_x_start + inner_width - 1, progress_bar_y + progress_bar_height - 1],
                           fill=GREY)

            # --- PLAY/PAUSE ICON ---
            icon_y = progress_bar_y + progress_bar_height + 1  # position icon below progress bar
            icon_x = inner_x_start + (inner_width - icon_size) // 2
            if is_playing:
                # Draw pause icon: two vertical bars with bar_width 2 and gap 2
                bar_width = 2
                gap = 2
                draw.rectangle([icon_x, icon_y,
                                icon_x + bar_width - 1, icon_y + icon_size - 1],
                               fill=SPOTIFY_GREEN)
                draw.rectangle([icon_x + bar_width + gap, icon_y,
                                icon_x + bar_width + gap + bar_width - 1, icon_y + icon_size - 1],
                               fill=SPOTIFY_GREEN)
            else:
                # Draw play icon: right-pointing triangle
                triangle = [(icon_x, icon_y),
                            (icon_x, icon_y + icon_size - 1),
                            (icon_x + icon_size - 1, icon_y + icon_size // 2)]
                draw.polygon(triangle, fill=SPOTIFY_GREEN)

            # Paste the right panel into the composite image
            composite.paste(right_panel, (32, 0))

            # Update the RGB matrix display
            matrix.SetImage(composite.convert('RGB'))

            # Slight delay for smooth scrolling
            time.sleep(0.05)

    except KeyboardInterrupt:
        sys.exit(0)

else:
    print("Usage: %s username token_path" % sys.argv[0])
    sys.exit()
