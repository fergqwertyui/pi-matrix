import time
import sys
import logging
from logging.handlers import RotatingFileHandler
from getSongInfo import getSongInfo
import requests
from io import BytesIO
from PIL import Image
from rgbmatrix import RGBMatrix, RGBMatrixOptions
import sys,os
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
    logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename='spotipy.log',level=logging.INFO)
    logger = logging.getLogger('spotipy_logger')

    # automatically deletes logs more than 2000 bytes
    handler = RotatingFileHandler('spotipy.log', maxBytes=2000,  backupCount=3)
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
    matrix = RGBMatrix(options = options)

    prevSong    = ""
    currentSong = ""

#    client_id = os.environ["SPOTIPY_CLIENT_ID"]
 #   client_secret = os.environ["SPOTIPY_CLIENT_SECRET"]
  #  redirect_url = os.environ["SPOTIPY_REDIRECT_URI"]

#    auth_manager = SpotifyOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_url, scope="user-read-currently-playing")


    try:
      while True:
#        try:
          imageURL = getSongInfo(username, token_path)[1]
          currentSong = imageURL

          if ( prevSong != currentSong ):
            response = requests.get(imageURL)
            image = Image.open(BytesIO(response.content))
            image.thumbnail((matrix.width, matrix.height), Image.Resampling.LANCZOS)
            matrix.SetImage(image.convert('RGB'))
            prevSong = currentSong

          time.sleep(1)
      #  except Exception as e:
     #     image = Image.open(default_image)
    #      image.thumbnail((matrix.width, matrix.height), Image.Resampling.LANCZOS)
   #       matrix.SetImage(image.convert('RGB'))
  #        print(e)
 #         time.sleep(1)
    except KeyboardInterrupt:
      sys.exit(0)

else:
    print("Usage: %s username" % (sys.argv[0],))
    sys.exit()
