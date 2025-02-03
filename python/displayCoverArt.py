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
    BLACK = (0, 0, 0)

    # Variables for text scrolling
    scroll_offset = 0
    scroll_speed = 1  # pixels per frame

    try:
        while True:
            # Assume getSongInfo returns a dictionary with song details
            song_data, imageURL = getSongInfo(username, token_path)
            title = song_data.get("title", "Unknown Title")
            artist = song_data.get("artist", "Unknown Artist")
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
                composite.paste(Image.new('RGB', (32, 32), BLACK), (0, 0))

            # Build the right 32x32 info panel with 1px padding
            right_panel = Image.new('RGB', (32, 32), BLACK)
            draw = ImageDraw.Draw(right_panel)
            padding = 1  # 1 pixel padding around everything
            inner_width = 30  # (32 - 2px padding)
            inner_x_start = padding

            # --- Scrolling Song Title ---
            title_y = padding
            text_width, _ = draw.textsize(title, font=font)
            if text_width > inner_width:  # Enable scrolling if text is too long
                scroll_offset = (scroll_offset - scroll_speed) % (text_width + 10)
                draw.text((-scroll_offset, title_y), title, font=font, fill=WHITE)
            else:
                text_x = (inner_width - text_width) // 2
                draw.text((inner_x_start + text_x, title_y), title, font=font, fill=WHITE)

            # --- Artist Name (Slightly Grey) ---
            artist_y = title_y + 7  # Place artist slightly below the title
            draw.text((inner_x_start, artist_y), artist, font=font, fill=GREY)

            # --- Progress Bar (2px thick, adjusted to fit) ---
            progress_bar_y = 19
            progress_bar_height = 2
            progress_ratio = min(max(progress_ms / duration_ms, 0), 1)
            filled_width = int(progress_ratio * inner_width)

            # Filled (completed) part: white
            draw.rectangle([inner_x_start, progress_bar_y, inner_x_start + filled_width, progress_bar_y + progress_bar_height - 1], fill=WHITE)
            # Unfilled part: grey
            draw.rectangle([inner_x_start + filled_width, progress_bar_y, inner_x_start + inner_width, progress_bar_y + progress_bar_height - 1], fill=GREY)

            # --- Play/Pause Icon (Smaller & Below Progress Bar) ---
            icon_size = 5
            icon_y = 24  # Moved higher to fit in bounds
            icon_x = inner_x_start + (inner_width - icon_size) // 2

            if is_playing:
                # Draw pause icon: two vertical bars
                bar_width = 1
                gap = 1
                draw.rectangle([icon_x, icon_y, icon_x + bar_width, icon_y + icon_size - 1], fill=SPOTIFY_GREEN)
                draw.rectangle([icon_x + bar_width + gap, icon_y, icon_x + bar_width + gap + bar_width, icon_y + icon_size - 1], fill=SPOTIFY_GREEN)
            else:
                # Draw play icon: a right-pointing triangle
                triangle = [(icon_x, icon_y),
                            (icon_x, icon_y + icon_size - 1),
                            (icon_x + icon_size - 1, icon_y + icon_size // 2)]
                draw.polygon(triangle, fill=SPOTIFY_GREEN)

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
