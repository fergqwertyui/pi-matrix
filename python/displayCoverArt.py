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

os.sched_setaffinity(0, {3})  # Restrict execution to CPU core 3

if len(sys.argv) > 2:
    username = sys.argv[1]
    token_path = sys.argv[2]

    print(username, token_path)
    # Configuration file
    dir = os.path.dirname(__file__)
    filename = os.path.join(dir, '../config/rgb_options.ini')

    # Configures logger for storing song data
    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
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

    print(options)

    default_image = os.path.join(dir, config['DEFAULT']['default_image'])
    print(default_image)
    matrix = RGBMatrix(options=options)

    prevAlbumArtURL = ""
    album_image = None

    # Load a small font (adjust or use a TTF font if needed)
    font = ImageFont.load_default()

    # Define colors
    SPOTIFY_GREEN = (30, 215, 96)
    WHITE = (255, 255, 255)
    GREY = (128, 128, 128)
    BLACK = (0, 0, 0)

    # Scrolling configuration – separate offsets for title and artist
    scroll_speed = 1  # pixels per frame
    scroll_offset_title = 0
    scroll_offset_artist = 0

    try:
        while True:
            # Assume getSongInfo returns a dictionary with song details and an image URL
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

            # Layout:
            # • Title at the top (y = inner_y_start)
            # • Artist immediately below title
            # • Progress bar (2px thick) placed near the bottom
            # • Play/Pause icon (old style) below the progress bar

            # --- Title & Artist Positions ---
            # Measure title height
            title_width, title_height = draw.textsize(title, font=font)
            title_y = inner_y_start  # e.g. y = 1
            # Place artist one pixel below the title line
            artist_y = title_y + title_height + 1

            # --- Scrolling Song Title ---
            if title_width > inner_width:
                max_offset_title = title_width - inner_width
                scroll_offset_title = (scroll_offset_title + scroll_speed) % (max_offset_title + 10)
                # Only scroll up to max_offset_title before pausing briefly
                offset_title = scroll_offset_title if scroll_offset_title <= max_offset_title else max_offset_title
                draw.text((inner_x_start - offset_title, title_y), title, font=font, fill=WHITE)
            else:
                centered_x = (inner_width - title_width) // 2
                draw.text((inner_x_start + centered_x, title_y), title, font=font, fill=WHITE)

            # --- Scrolling Artist Name ---
            artist_width, artist_height = draw.textsize(artist, font=font)
            if artist_width > inner_width:
                max_offset_artist = artist_width - inner_width
                scroll_offset_artist = (scroll_offset_artist + scroll_speed) % (max_offset_artist + 10)
                offset_artist = scroll_offset_artist if scroll_offset_artist <= max_offset_artist else max_offset_artist
                draw.text((inner_x_start - offset_artist, artist_y), artist, font=font, fill=GREY)
            else:
                centered_x = (inner_width - artist_width) // 2
                draw.text((inner_x_start + centered_x, artist_y), artist, font=font, fill=GREY)

            # --- Progress Bar (2px thick) ---
            # Position progress bar above the icon at the bottom of the inner area
            icon_size = 6  # icon height in pixels
            progress_bar_height = 2
            # Calculate progress bar Y so that the icon (with a 1px gap) fits at the very bottom
            progress_bar_y = inner_y_start + inner_height - (icon_size + progress_bar_height + 1)
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

            # --- Play/Pause Icon (Old pause icon style) ---
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

            time.sleep(0.1)

    except KeyboardInterrupt:
        sys.exit(0)

else:
    print("Usage: %s username token_path" % sys.argv[0])
    sys.exit()
