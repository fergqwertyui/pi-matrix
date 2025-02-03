import logging
import spotipy
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

        if result is None or "item" not in result:
            print("No song playing")
            return None
        else:
            song_title = result["item"]["name"]
            artist_name = ", ".join(artist["name"] for artist in result["item"]["artists"])
            album_name = result["item"]["album"]["name"]
            imageURL = result["item"]["album"]["images"][0]["url"]
            progress_ms = result.get("progress_ms", 0)
            duration_ms = result["item"]["duration_ms"]
            is_playing = result["is_playing"]

            print(f"Now playing: {song_title} - {artist_name} ({album_name})")

            return {
                "title": song_title,
                "artist": artist_name,
                "album": album_name,
                "progress_ms": progress_ms,
                "duration_ms": duration_ms,
                "is_playing": is_playing
            }, imageURL

    else:
        print("Can't get token for", username)
        return None
