import logging
import spotipy
import spotipy.util as util
from spotipy.oauth2 import SpotifyOAuth


import requests
from io import BytesIO
from PIL import Image

def getSongInfo(username, token_path):
    with open(token_path, 'r') as f: 
      token = eval(f.readlines()[0])["access_token"]
    print(token)
    if token:
      sp = spotipy.Spotify(auth=token)
      result = sp.current_user_playing_track()
    
      if result is None:
         print("No song playing")
      else:  
        song = result["item"]["name"]
        imageURL = result["item"]["album"]["images"][0]["url"]
        print(song)
        return [song, imageURL]
    else:
      print("Can't get token for", username)
      return None
  
