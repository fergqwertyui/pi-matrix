# Entire modified file
import time
import sys
import logging
from logging.handlers import RotatingFileHandler
from getSongInfo import getSongInfo
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from rgbmatrix import RGBMatrix, RGBMatrixOptions
import os
import configparser
from spotipy.oauth2 import SpotifyOAuth

if len(sys.argv) > 2:
    username = sys.argv[1]
    token_path = sys.argv[2]

    print(username, token_path)	
    # Configuration file    
    dir = os.path.dirname(__file__)
    filename = os.path.join(dir, '../config/rgb_options.ini')

    # Configures logger for storing song data    
    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename='spotipy.log', level=logging.INFO)
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

    print(options)

    default_image = os.path.join(dir, config['DEFAULT']['default_image'])
    print(default_image)
    matrix = RGBMatrix(options=options)

    prevAlbumArtURL = ""
    album_image = None

    # Load a small font (adjust or use a TrueType font if needed)
    font = ImageFont.load_default()

    # Define colors
    SPOTIFY_GREEN = (30, 215, 96)
    WHITE = (255, 255, 255)
    GREY = (128, 128, 128)

    try:
        while True:
            # Assume getSongInfo returns a tuple:
            #   (song_data, album_art_url)
            # where song_data is a dict with keys: title, artist, album, progress_ms, duration_ms, is_playing
            song_data, imageURL = getSongInfo(username, token_path)
            title = song_data.get("title", "Unknown Title")
            artist = song_data.get("artist", "Unknown Artist")
            album = song_data.get("album", "Unknown Album")
            progress_ms = song_data.get("progress_ms", 0)
            duration_ms = song_data.get("duration_ms", 1)  # avoid division by zero
            is_playing = song_data.get("is_playing", False)

            # Update album art if changed
            if imageURL != prevAlbumArtURL:
                try:
                    response = requests.get(imageURL)
                    album_image = Image.open(BytesIO(response.content)).convert('RGB')
                    album_image.thumbnail((32, 32), Image.Resampling.LANCZOS)
                    prevAlbumArtURL = imageURL
                except Exception as e:
                    album_image = Image.open(default_image).convert('RGB')
                    album_image.thumbnail((32, 32), Image.Resampling.LANCZOS)

            # Create a composite image (64x32): left half for album art, right half for info
            composite = Image.new('RGB', (64, 32))
            if album_image:
                composite.paste(album_image, (0, 0))
            else:
                composite.paste(Image.new('RGB', (32, 32), (0, 0, 0)), (0, 0))

            # Build the right 32x32 info panel
            right_panel = Image.new('RGB', (32, 32), (0, 0, 0))
            draw = ImageDraw.Draw(right_panel)

            # Layout:
            #  • Top region (y: 0–11): scrolling text ("Title - Artist - Album")
            #  • Middle region (y: 12–21): play/pause icon (8x8, centered)
            #  • Bottom region (y: 22–31): progress bar

            # --- Scrolling text ---
            info_text = f"{title} - {artist} - {album}"
            text_width, text_height = draw.textsize(info_text, font=font)
            text_region_height = 12
            text_y = (text_region_height - text_height) // 2

            scroll_speed = 20  # pixels per second
            if text_width > 32:
                total_scroll_width = text_width + 5  # add a small gap
                offset = int(time.time() * scroll_speed) % total_scroll_width
                start_x = 32 - offset
                x = start_x
                while x < 32:
                    draw.text((x, text_y), info_text, font=font, fill=WHITE)
                    x += text_width + 5
            else:
                text_x = (32 - text_width) // 2
                draw.text((text_x, text_y), info_text, font=font, fill=WHITE)

            # --- Play/Pause Icon ---
            icon_size = 8
            icon_region_y_start = 12
            icon_region_height = 10  # y: 12–21
            icon_x = (32 - icon_size) // 2
            icon_y = icon_region_y_start + (icon_region_height - icon_size) // 2

            if is_playing:
                # Draw pause icon: two vertical bars
                bar_width = 2
                gap = 2
                # Left bar
                draw.rectangle([icon_x, icon_y, icon_x + bar_width - 1, icon_y + icon_size - 1], fill=SPOTIFY_GREEN)
                # Right bar
                draw.rectangle([icon_x + bar_width + gap, icon_y,
                                icon_x + bar_width + gap + bar_width - 1, icon_y + icon_size - 1], fill=SPOTIFY_GREEN)
            else:
                # Draw play icon: a right-pointing triangle
                triangle = [(icon_x, icon_y),
                            (icon_x, icon_y + icon_size - 1),
                            (icon_x + icon_size - 1, icon_y + icon_size // 2)]
                draw.polygon(triangle, fill=SPOTIFY_GREEN)

            # --- Progress Bar ---
            progress_region_y_start = 22
            progress_region_height = 10
            progress_bar_height = 4
            progress_bar_y = progress_region_y_start + (progress_region_height - progress_bar_height) // 2
            progress_ratio = min(max(progress_ms / duration_ms, 0), 1)
            filled_width = int(progress_ratio * 32)
            # Filled (completed) part: white
            draw.rectangle([0, progress_bar_y, filled_width, progress_bar_y + progress_bar_height - 1], fill=WHITE)
            # Unfilled part: grey
            draw.rectangle([filled_width, progress_bar_y, 32, progress_bar_y + progress_bar_height - 1], fill=GREY)

            # Paste right info panel into composite image
            composite.paste(right_panel, (32, 0))

            # Update the RGB matrix display
            matrix.SetImage(composite.convert('RGB'))

            time.sleep(0.1)

    except KeyboardInterrupt:
        sys.exit(0)

else:
    print("Usage: %s username token_path" % sys.argv[0])
    sys.exit()
