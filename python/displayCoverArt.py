import time
import sys
import logging
from logging.handlers import RotatingFileHandler
from getSongInfo import getSongInfo
import requests
from io import BytesIO
from PIL import Image
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
import os
import configparser

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

    # Load RGBMatrix font
    font = graphics.Font()
    font.LoadFont("../fonts/7x13.bdf")  # Ensure path is correct

    # Define colors
    SPOTIFY_GREEN = graphics.Color(30, 215, 96)
    WHITE = graphics.Color(255, 255, 255)
    GREY = graphics.Color(128, 128, 128)

    # Scrolling configuration – separate offsets for title and artist
    scroll_speed = 1  # pixels per frame
    scroll_offset_title = 64  # Start outside screen
    scroll_offset_artist = 64  # Start outside screen

    try:
        frame = 0
        while True:
            # Fetch song info every 10 frames to optimize API calls
            if frame % 10 == 0:
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

            # Create composite image (64x32)
            composite = Image.new('RGB', (64, 32))
            if album_image:
                composite.paste(album_image, (0, 0))

            # Convert image to matrix format
            matrix.SetImage(composite.convert('RGB'))

            # Get canvas for text rendering
            canvas = matrix.CreateFrameCanvas()
            canvas.Clear()

            # --- Scrolling Title ---
            title_len = graphics.DrawText(canvas, font, scroll_offset_title, 10, WHITE, title)
            scroll_offset_title -= scroll_speed
            if scroll_offset_title + title_len < 0:  # Reset when fully scrolled
                scroll_offset_title = canvas.width

            # --- Scrolling Artist ---
            artist_len = graphics.DrawText(canvas, font, scroll_offset_artist, 20, GREY, artist)
            scroll_offset_artist -= scroll_speed
            if scroll_offset_artist + artist_len < 0:  # Reset when fully scrolled
                scroll_offset_artist = canvas.width

            # --- Progress Bar (2px thick) ---
            bar_width = int((progress_ms / duration_ms) * 32)  # Scale to 32px width
            graphics.DrawLine(canvas, 32, 28, 32 + bar_width, 28, WHITE)  # Progress line

            # --- Play/Pause Icon ---
            if is_playing:
                # Draw pause icon: two vertical bars
                graphics.DrawLine(canvas, 58, 24, 58, 30, SPOTIFY_GREEN)
                graphics.DrawLine(canvas, 60, 24, 60, 30, SPOTIFY_GREEN)
            else:
                # Draw play icon: right-pointing triangle
                graphics.DrawTriangle(canvas, 58, 24, 58, 30, 62, 27, SPOTIFY_GREEN)

            # Refresh matrix display
            canvas = matrix.SwapOnVSync(canvas)
            frame += 1
            time.sleep(0.05)  # Control scrolling speed

    except KeyboardInterrupt:
        sys.exit(0)

else:
    print("Usage: %s username token_path" % sys.argv[0])
    sys.exit()
