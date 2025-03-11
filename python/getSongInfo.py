import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
from io import BytesIO
from PIL import Image

def getSongInfo(username, token_path):
    # Initialize Spotipy with automatic token refresh
    auth_manager = SpotifyOAuth(
        scope='user-read-currently-playing',
        cache_path=token_path,
        open_browser=False
    )
    sp = spotipy.Spotify(auth_manager=auth_manager)
    result = sp.current_user_playing_track()

    if result is None or "item" not in result:
        print("No media playing")
        return None
    else:
        item = result["item"]
        item_type = item.get("type", "track")
        progress_ms = result.get("progress_ms", 0)
        duration_ms = item.get("duration_ms", 0)
        is_playing = result.get("is_playing", False)

        if item_type == "track":
            # Extract music track details
            song_title = item.get("name", "Unknown Title")
            artist_name = ", ".join(artist.get("name", "Unknown Artist") for artist in item.get("artists", []))
            album_info = item.get("album", {})
            album_name = album_info.get("name", "Unknown Album")
            imageURL = None
            if "images" in album_info and album_info["images"]:
                imageURL = album_info["images"][0].get("url", None)
            print(f"Now playing track: {song_title} - {artist_name} ({album_name})")
            return {
                "title": song_title,
                "artist": artist_name,
                "album": album_name,
                "progress_ms": progress_ms,
                "duration_ms": duration_ms,
                "is_playing": is_playing,
                "type": item_type
            }, imageURL

        else:
            # Handle podcasts, audiobooks, or any non-track media
            media_title = item.get("name", "Unknown Title")
            # Attempt to get the series/show info if available
            if "show" in item:
                show_name = item["show"].get("name", "Unknown Show")
                # Prefer the episode image; if not available, fall back to the show's image
                imageURL = None
                if "images" in item and item["images"]:
                    imageURL = item["images"][0].get("url", None)
                elif "images" in item["show"] and item["show"]["images"]:
                    imageURL = item["show"]["images"][0].get("url", None)
            else:
                show_name = "Unknown Artist"
                imageURL = None

            print(f"Now playing {item_type}: {media_title} - {show_name}")
            return {
                "title": media_title,
                "artist": show_name,
                "progress_ms": progress_ms,
                "duration_ms": duration_ms,
                "is_playing": is_playing,
                "type": item_type
            }, imageURL
