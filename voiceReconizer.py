"""daduAssistant — Voice recognizer and personal assistant
This module implements a voice-driven assistant (wake word: "dadu").
It listens for voice commands and can perform a variety of actions,
including: web searches, YouTube/Spotify playback (open/search),
weather lookup (OpenWeatherMap), Wikipedia summaries, currency and unit
conversions, news headlines, timers/alarms, jokes, and horoscope lookups.

Key functions (in this file):
- `sptext()` : capture microphone input and return recognized text
- `speechtex(text)` : speak `text` using `pyttsx3`
- `fetch_weather_for_city(city)` : fetch weather via OpenWeatherMap (uses
  `OPENWEATHER_API_KEY` from env or `config.json`)
- `fetch_wikipedia_summary(topic)` : return a short Wikipedia summary
- `convert_currency(amount, from_curr, to_curr)` and `convert_unit(...)`
- `fetch_news_headlines(category, limit)` : fetch top news headlines
- `get_spotify_client()` : helper to create a Spotipy client from env or
  `config.json` credentials

Config and environment variables:
- `config.json` in project root can store `OPENWEATHER_API_KEY`,
  `SPOTIPY_CLIENT_ID`, and `SPOTIPY_CLIENT_SECRET`.
- `OPENWEATHER_API_KEY` may also be provided as an environment variable.

See `README.md` for full setup, dependency, and packaging instructions.
"""

import pyttsx3
import speech_recognition
import webbrowser
import datetime
import os
import pyjokes
import urllib.parse
import requests
import re
import json
import math
from pathlib import Path
import wikipedia
import threading
import time
import pywhatkit
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# For GPS location detection (will handle gracefully if not installed)
try:
  from geolocation.main import geolocation
  HAS_GEOLOCATION = True
except ImportError:
  HAS_GEOLOCATION = False


print("Initializing Voice Recognizer")

def sptext():
  """Capture voice input from microphone and convert to text using Google Speech API.
  
  This function uses the SpeechRecognition library to:
  1. Initialize a microphone source
  2. Adjust for ambient noise in the environment
  3. Listen for audio input (blocking until speech detected)
  4. Send audio to Google's speech-to-text API for recognition
  5. Return the recognized text
  
  Returns:
    str: Recognized text (lowercase), or "None" if unrecognized or error.
  
  Exceptions handled:
    - speech_recognition.UnknownValueError: audio understood but not recognized
    - AttributeError: microphone not available
  
  Note: Requires internet connection for Google Speech API and PyAudio for microphone.
  """
  recognizer = speech_recognition.Recognizer() 
  try:
    with speech_recognition.Microphone() as source:
      print("Listening...")
      recognizer.adjust_for_ambient_noise(source)
      audio = recognizer.listen(source)
      try:
        print("Recognizing...")
        data = recognizer.recognize_google(audio)
        print(f"you said: {data}")
        return data
      except speech_recognition.UnknownValueError:
        print("Sorry, I did not get that")
        return "None"
      
  except AttributeError:
    print("Sorry, I did not get that")
    return "None"


def speechtex(x):
  """Convert text to speech using pyttsx3 (offline text-to-speech engine).
  
  This function uses the pyttsx3 library to synthesize and play audio from text.
  It configures voice (female voice at index 1) and speech rate (150 WPM).
  
  Args:
    x (str): Text to be spoken aloud.
  
  Returns:
    None. Plays audio directly to the system speaker.
  
  Note: Uses offline speech synthesis (no internet required). The voice and
    rate can be customized by modifying the engine properties.
  """
  engine = pyttsx3.init()
  voices = engine.getProperty('voices')
  engine.setProperty('voice', voices[1].id)
  rate = engine.getProperty('rate')
  engine.setProperty('rate', 150)
  engine.say(x)
  engine.runAndWait()

# Wikipedia summary fetcher
def fetch_wikipedia_summary(topic: str):
  """Fetch a concise summary of `topic` from Wikipedia.
  
  Uses the Wikipedia API via the `wikipedia` package to retrieve a 2-sentence
  summary of the requested topic.
  
  Args:
    topic (str): The topic/search term to look up on Wikipedia.
  
  Returns:
    tuple: (summary_text, error_string)
      - If summary found: (summary_text, None)
      - If topic not found: (None, 'not_found')
      - If disambiguation page: (None, 'disambiguation: [options]')
      - If other error: (None, error_message_string)
  
  Note: Requires internet connection to access Wikipedia API.
  """
  try:
    result = wikipedia.summary(topic, sentences=2)
    return result, None
  except wikipedia.exceptions.PageError:
    return None, 'not_found'
  except wikipedia.exceptions.DisambiguationError as e:
    options = e.options[:3]
    return None, f'disambiguation: {options}'
  except Exception as e:
    return None, str(e)

# function to convert currency
def convert_currency(amount: float, from_curr: str, to_curr: str):
  """Convert between two currencies using a free exchange-rate API.
  
  Fetches current exchange rates from exchangerate-api.com and calculates
  the conversion for the given amount.
  
  Args:
    amount (float): The amount to convert.
    from_curr (str): Source currency code (e.g., 'USD', 'EUR', 'INR').
    to_curr (str): Target currency code (e.g., 'USD', 'EUR', 'INR').
  
  Returns:
    tuple: (result_string, error_string)
      - On success: (f"{amount} {from_curr} is {converted:.2f} {to_curr}", None)
      - If API error: (None, f"api_error:{status_code}")
      - If currency not found: (None, f"currency_not_found:{to_curr}")
      - If other error: (None, error_message_string)
  
  Note: Requires internet connection to access exchange rate API.
  """
  try:
    from_curr = from_curr.upper()
    to_curr = to_curr.upper()
    url = f"https://api.exchangerate-api.com/v4/latest/{from_curr}"
    resp = requests.get(url, timeout=5)
    if resp.status_code != 200:
      return None, f"api_error:{resp.status_code}"
    data = resp.json()
    if to_curr not in data.get('rates', {}):
      return None, f"currency_not_found:{to_curr}"
    rate = data['rates'][to_curr]
    converted = amount * rate
    return f"{amount} {from_curr} is {converted:.2f} {to_curr}", None
  except Exception as e:
    return None, str(e)

# function to convert units
def convert_unit(amount: float, from_unit: str, to_unit: str):
  """Convert between common units (distance, weight, temperature).
  
  Handles conversions for:
  - Distance: km, kilometers, miles, mi, meters, m, feet, ft, yards, yd
  - Weight: kg, kilograms, lbs, pounds, lb, grams, g, ounces, oz
  - Temperature: celsius/c <-> fahrenheit/f
  
  Args:
    amount (float): The value to convert.
    from_unit (str): Source unit name (case-insensitive).
    to_unit (str): Target unit name (case-insensitive).
  
  Returns:
    tuple: (result_string, error_string)
      - On success: (f"{amount} {from_unit} is {converted:.2f} {to_unit}", None)
      - If units not supported: (None, f"unknown_unit_pair:{from_unit}_{to_unit}")
  
  Note: All conversions are done locally without external API calls.
  """
  from_unit = from_unit.lower().strip()
  to_unit = to_unit.lower().strip()
  
  # Distance conversions
  distance_map = {
    'km': 0.621371, 'kilometer': 0.621371, 'kilometres': 0.621371,
    'miles': 1.60934, 'mile': 1.60934, 'mi': 1.60934,
    'meters': 0.000621371, 'meter': 0.000621371, 'm': 0.000621371,
    'feet': 3.28084, 'foot': 3.28084, 'ft': 3.28084,
    'yards': 1.09361, 'yard': 1.09361, 'yd': 1.09361,
  }
  
  # Weight conversions
  weight_map = {
    'kg': 2.20462, 'kilograms': 2.20462, 'kilogram': 2.20462,
    'lbs': 0.453592, 'pounds': 0.453592, 'pound': 0.453592, 'lb': 0.453592,
    'grams': 0.00220462, 'gram': 0.00220462, 'g': 0.00220462,
    'ounces': 0.0283495, 'ounce': 0.0283495, 'oz': 0.0283495,
  }
  
  # Temperature (special handling)
  if from_unit in ('celsius', 'c') and to_unit in ('fahrenheit', 'f'):
    converted = (amount * 9/5) + 32
    return f"{amount}°C is {converted:.2f}°F", None
  elif from_unit in ('fahrenheit', 'f') and to_unit in ('celsius', 'c'):
    converted = (amount - 32) * 5/9
    return f"{amount}°F is {converted:.2f}°C", None
  
  # Try distance
  if from_unit in distance_map and to_unit in distance_map:
    # Convert from_unit to miles, then miles to to_unit
    if from_unit in ('miles', 'mile', 'mi'):
      miles = amount
    else:
      miles = amount / distance_map[from_unit]
    
    if to_unit in ('miles', 'mile', 'mi'):
      converted = miles
    else:
      converted = miles * distance_map[to_unit]
    
    return f"{amount} {from_unit} is {converted:.2f} {to_unit}", None
  
  # Try weight
  if from_unit in weight_map and to_unit in weight_map:
    if from_unit in ('lbs', 'pounds', 'pound', 'lb'):
      lbs = amount
    else:
      lbs = amount / weight_map[from_unit]
    
    if to_unit in ('lbs', 'pounds', 'pound', 'lb'):
      converted = lbs
    else:
      converted = lbs * weight_map[to_unit]
    
    return f"{amount} {from_unit} is {converted:.2f} {to_unit}", None
  
  return None, f"unknown_unit_pair:{from_unit}_{to_unit}"

# function to fetch news headlines
def fetch_news_headlines(category: str = "general", limit: int = 3):
  """Fetch top news headlines for a given category.
  
  Attempts to fetch news from NewsAPI first (free tier, limited requests).
  Falls back to GNews API if NewsAPI fails.
  
  Args:
    category (str): News category. NewsAPI free tier supports: general, business,
      entertainment, health, science, sports, technology. Defaults to "general".
    limit (int): Maximum number of headlines to return. Defaults to 3.
  
  Returns:
    tuple: (headlines_list, error_string)
      - On success: ([headline1, headline2, ...], None)
      - On error: (None, f"api_error:{status_code}")
  
  Note: Requires internet connection. NewsAPI has request limits on free tier.
  """
  try:
    # Using NewsAPI free tier (no auth key needed for demo, but limited requests)
    url = "https://newsapi.org/v2/top-headlines"
    params = {
      "country": "us",
      "category": category.lower(),
      "sortBy": "publishedAt",
      "pageSize": limit,
    }
    resp = requests.get(url, params=params, timeout=6)
    if resp.status_code != 200:
      # Fallback: use a simpler free API (gnews)
      url = "https://gnews.io/api/v4/top-news"
      params = {
        "q": category,
        "max": limit,
        "lang": "en",
      }
      resp = requests.get(url, params=params, timeout=6)
      if resp.status_code != 200:
        return None, f"api_error:{resp.status_code}"
      data = resp.json()
      articles = data.get('articles', [])
      headlines = [f"{a.get('title', 'Untitled')}" for a in articles[:limit]]
      return headlines, None
    
    data = resp.json()
    articles = data.get('articles', [])
    headlines = [f"{a.get('title', 'Untitled')}" for a in articles[:limit]]
    return headlines, None
  except Exception as e:
    return None, str(e)

# function to fetch weather
def fetch_weather_for_city(city: str):
  """Fetch weather summary for `city` using OpenWeatherMap if API key present.
  Returns (summary_string, error_string). If summary returned, error is None.
  If no API key is found, returns (None, 'no_key')."""
  def get_config_path() -> Path:
    return Path(__file__).parent / "config.json"

# Helper to get OpenWeather API key
  def get_api_key():
    # 1) environment
    key = os.environ.get("OPENWEATHER_API_KEY")
    if key:
      return key
    # 2) project config
    cfg = get_config_path()
    if cfg.exists():
      try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("OPENWEATHER_API_KEY"):
          return data.get("OPENWEATHER_API_KEY")
      except Exception:
        pass
    # 3) prompt user (fallback)
    try:
      key = input("Enter OpenWeatherMap API key (or press Enter to skip): ").strip()
    except Exception:
      key = ""
    if key:
      try:
        save = input("Save this key to project config (config.json)? [Y/n]: ").strip().lower()
      except Exception:
        save = "y"
      if save in ("", "y", "yes"):
        try:
          get_config_path().write_text(json.dumps({"OPENWEATHER_API_KEY": key}), encoding="utf-8")
          print(f"Saved API key to {get_config_path()}")
        except Exception:
          print("Could not save config file; continuing without saving.")
      return key
    return None

  api_key = get_api_key()
  if not api_key:
    return None, 'no_key'
  try:
    url = (
      "http://api.openweathermap.org/data/2.5/weather?"
      f"q={urllib.parse.quote(city)}&appid={api_key}&units=metric"
    )
    resp = requests.get(url, timeout=6)
    if resp.status_code != 200:
      return None, f"api_error:{resp.status_code}"
    j = resp.json()
    desc = j.get('weather',[{}])[0].get('description','')
    temp = j.get('main',{}).get('temp')
    feels = j.get('main',{}).get('feels_like')
    humidity = j.get('main',{}).get('humidity')
    wind = j.get('wind',{}).get('speed')
    parts = []
    if desc:
      parts.append(desc.capitalize())
    if temp is not None:
      parts.append(f"Temperature {temp}°C")
    if feels is not None:
      parts.append(f"feels like {feels}°C")
    if humidity is not None:
      parts.append(f"humidity {humidity}%")
    if wind is not None:
      parts.append(f"wind {wind} m/s")
    summary = ", ".join(parts)
    return f"Weather in {city.title()}: {summary}", None
  except Exception as e:
    return None, str(e)

# function to get Spotify client
def get_spotify_client():
  """Create and return a Spotipy client using Client Credentials auth flow.
  
  Looks for Spotify API credentials in environment variables first, then
  falls back to `config.json` in the project folder.
  
  Environment variables:
    - SPOTIPY_CLIENT_ID: Spotify app client ID
    - SPOTIPY_CLIENT_SECRET: Spotify app client secret
  
  Config file format (config.json):
    {
      "SPOTIPY_CLIENT_ID": "your_client_id",
      "SPOTIPY_CLIENT_SECRET": "your_client_secret"
    }
  
  Returns:
    tuple: (client, error_string)
      - If credentials found: (spotipy.Spotify client object, None)
      - If credentials missing: (None, 'no_credentials')
      - If auth fails: (None, error_message_string)
  
  Note: Uses Client Credentials flow (no user login). Suitable for API access
    but not for controlling playback on user devices (requires OAuth).
  """
  client_id = os.environ.get('SPOTIPY_CLIENT_ID')
  client_secret = os.environ.get('SPOTIPY_CLIENT_SECRET')
  # fallback to config.json
  if not client_id or not client_secret:
    cfg = Path(__file__).parent / 'config.json'
    if cfg.exists():
      try:
        data = json.loads(cfg.read_text(encoding='utf-8'))
        client_id = client_id or data.get('SPOTIPY_CLIENT_ID')
        client_secret = client_secret or data.get('SPOTIPY_CLIENT_SECRET')
      except Exception:
        pass
  if not client_id or not client_secret:
    return None, 'no_credentials'
  try:
    manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(client_credentials_manager=manager)
    return sp, None
  except Exception as e:
    return None, str(e)

import requests

# function to fetch recipe
import requests

def fetch_recipe(dish: str):
    """
    Fetch a recipe for the given dish using TheMealDB API.
    Returns (recipe_text, error_message).
    """
    try:
        # Search for the dish
        url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={dish}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        meals = data.get("meals")
        if not meals:
            return None, "No recipe found."

        # Take the first recipe result
        meal = meals[0]
        title = meal.get("strMeal", "Unknown Recipe")
        instructions = meal.get("strInstructions", "No instructions available")

        # Collect ingredients
        ingredients = []
        for i in range(1, 21):  # TheMealDB provides up to 20 ingredients
            ingredient = meal.get(f"strIngredient{i}")
            measure = meal.get(f"strMeasure{i}")
            if ingredient and ingredient.strip():
                ingredients.append(f"{ingredient} - {measure}")

        recipe_text = f"{title}\n\nIngredients:\n" + "\n".join(ingredients) + f"\n\nInstructions:\n{instructions}"
        return recipe_text, None

    except Exception as e:
        return None, str(e)
    

# functions for timers and alarms
def _timer_thread(duration, label=None):
  """Background thread worker that waits and announces a timer/alarm.
  
  This is an internal helper called by start_timer_seconds() and start_alarm_at().
  It sleeps for the specified duration, then prints and speaks a completion message.
  
  Args:
    duration (int): Time to wait in seconds.
    label (str, optional): Optional label for the timer (e.g., "cooking", "laundry").
  
  Returns:
    None. Runs as a daemon thread until completion.
  """
  try:
    time.sleep(duration)
    msg = f"Timer finished"
    if label:
      msg = f"Timer '{label}' finished"
    print(msg)
    try:
      speechtex(msg)
    except Exception:
      # speech may fail if audio busy; still print
      pass
  except Exception as e:
    print(f"Timer thread error: {e}")

# function to start timer
def start_timer_seconds(seconds: int, label: str | None = None):
  """Start a background timer that runs for the specified number of seconds.
  
  Creates a daemon thread that waits silently, then announces when complete.
  Timer runs in the background without blocking the main voice loop.
  
  Args:
    seconds (int): Duration in seconds.
    label (str, optional): Optional label to identify the timer.
  
  Returns:
    threading.Thread: The created daemon thread object (for reference/management).
  
  Note: Multiple timers can be active simultaneously. To cancel a timer,
    would require additional tracking/management (not implemented yet).
  """
  t = threading.Thread(target=_timer_thread, args=(seconds, label), daemon=True)
  t.start()
  return t

# function to start alarm at specific datetime
def start_alarm_at(dt: datetime.datetime, label: str | None = None):
  """Schedule an alarm to fire at a specific datetime.
  
  Calculates the time delta from now to the target datetime and creates a timer.
  
  Args:
    dt (datetime.datetime): The target alarm time (local timezone).
    label (str, optional): Optional label for the alarm.
  
  Returns:
    tuple: (thread_or_none, error_string)
      - If time is in future: (threading.Thread object, None)
      - If time is in past: (None, 'past_time')
  
  Note: The caller should check for 'past_time' error and adjust time (e.g., next day).
  """
  now = datetime.datetime.now()
  if dt <= now:
    return None, "past_time"
  seconds = (dt - now).total_seconds()
  return start_timer_seconds(int(seconds), label), None

# function to fetch horoscope
def fetch_horoscope(sign: str, day: str = "today"):
  """Fetch daily horoscope for a zodiac sign using the Aztro API.
  
  Uses the free Aztro horoscope API to fetch daily predictions, mood, and other info.
  
  Args:
    sign (str): Zodiac sign name (e.g., 'aries', 'taurus', 'gemini', etc.).
    day (str): Day for horoscope ('today', 'tomorrow', or a date). Defaults to 'today'.
  
  Returns:
    tuple: (text, error_string)
      - On success: (full_horoscope_text, None)
        Text includes description, mood, compatibility, color, lucky number, lucky time.
      - On API error: (None, f"api_error:{status_code}")
      - On other error: (None, error_message_string)
  
  Note: Requires internet connection. Aztro API is free but may have rate limits.
  """
  try:
    sign = sign.lower()
    url = "https://aztro.sameerkumar.website/"
    resp = requests.post(url, params={"sign": sign, "day": day}, timeout=6)
    if resp.status_code != 200:
      return None, f"api_error:{resp.status_code}"
    j = resp.json()
    desc = j.get('description', '')
    mood = j.get('mood')
    compat = j.get('compatibility')
    color = j.get('color')
    lucky_number = j.get('lucky_number')
    lucky_time = j.get('lucky_time')
    parts = [p for p in (desc, f"Mood: {mood}" if mood else None,
                        f"Compatibility: {compat}" if compat else None,
                        f"Color: {color}" if color else None,
                        f"Lucky number: {lucky_number}" if lucky_number else None,
                        f"Lucky time: {lucky_time}" if lucky_time else None) if p]
    text = ". ".join(parts)
    return text, None
  except Exception as e:
    return None, str(e)

# function to get user's current location via GPS
def get_current_location():
  """Get user's current GPS location or prompt for manual entry.
  
  Attempts to use geolocation library to automatically detect location.
  Falls back to IP-based geolocation or prompts user for manual location.
  
  Returns:
    tuple: (location_string, coordinates_dict)
      - On success: ("City, Country", {'lat': float, 'lon': float})
      - On fallback: (user_input, None) or (ip_location, {'lat': float, 'lon': float})
  
  Note: Requires internet for IP-based geolocation. True GPS requires device hardware.
  """
  try:
    # Try using geolocation library (requires package: geolocation-python)
    if HAS_GEOLOCATION:
      try:
        result = geolocation.geolocation(timeout=5)
        if result and 'city' in result and 'country' in result:
          location_str = f"{result.get('city', '')}, {result.get('country', '')}"
          coords = {
            'lat': float(result.get('latitude', 0)),
            'lon': float(result.get('longitude', 0))
          }
          print(f"GPS Location detected: {location_str}")
          return location_str, coords
      except Exception:
        pass
    
    # Fallback: Use IP-based geolocation (free service)
    try:
      ip_geo_url = "https://ipapi.co/json/"
      ip_resp = requests.get(ip_geo_url, timeout=5)
      if ip_resp.status_code == 200:
        ip_data = ip_resp.json()
        location_str = f"{ip_data.get('city', 'Unknown')}, {ip_data.get('country_name', '')}"
        coords = {
          'lat': float(ip_data.get('latitude', 0)),
          'lon': float(ip_data.get('longitude', 0))
        }
        print(f"IP-based location detected: {location_str}")
        return location_str, coords
    except Exception:
      pass
    
    # Final fallback: Ask user for location
    user_location = input("Could not detect location. Please enter your location (e.g., 'New York'): ").strip()
    return user_location, None
    
  except Exception as e:
    print(f"Location detection error: {e}")
    return None, None

# function to estimate toll costs based on location and distance
def estimate_toll_cost(origin: str, destination: str, distance_km: float, 
                       origin_coords: dict, dest_coords: dict):
  """Estimate toll costs for a route using regional toll databases.
  
  Uses heuristics and regional toll data to estimate costs. Known toll regions:
  - USA: I-77, I-81, I-90, toll roads in CA, TX, FL
  - Europe: Various highway tolls vary by country
  - India: National highways have toll plazas
  
  Args:
    origin (str): Starting location name.
    destination (str): Destination location name.
    distance_km (float): Route distance in kilometers.
    origin_coords (dict): {'lat': float, 'lon': float}
    dest_coords (dict): {'lat': float, 'lon': float}
  
  Returns:
    float: Estimated toll cost in USD.
  """
  try:
    # USA toll road estimates (rough)
    usa_toll_regions = {
      'northeast': 0.18,  # $/km (I-95, I-90, NY toll roads)
      'midwest': 0.12,    # $/km (I-80, I-90)
      'south': 0.10,      # $/km (Florida, Texas)
      'west': 0.08        # $/km (CA, OR toll roads)
    }
    
    # Estimate based on distance and typical toll rate
    # Assume ~10-20% of route has tolls
    toll_percentage = 0.15  # 15% of route typically has tolls
    base_toll_rate = 0.12   # $/km average in USA
    
    # Adjust by region (simple lat/lon based heuristic)
    lat_avg = (origin_coords.get('lat', 0) + dest_coords.get('lat', 0)) / 2
    lon_avg = (origin_coords.get('lon', 0) + dest_coords.get('lon', 0)) / 2
    
    # Simple region detection by coordinates
    if lon_avg < -100:  # West coast
      regional_rate = usa_toll_regions.get('west', 0.08)
    elif lon_avg < -85:  # Midwest/South
      regional_rate = usa_toll_regions.get('midwest', 0.12)
    elif lon_avg < -75:  # Northeast
      regional_rate = usa_toll_regions.get('northeast', 0.18)
    else:  # Other regions or international
      regional_rate = 0.10
    
    estimated_toll = distance_km * toll_percentage * regional_rate
    return round(estimated_toll, 2)
    
  except Exception as e:
    print(f"Toll estimation error: {e}")
    return round((distance_km * 0.15 * 0.12), 2)  # Fallback estimate

# function to fetch multiple route suggestions
def fetch_best_routes(origin: str, destination: str):
  """Fetch multiple optimized route suggestions (fastest, cheapest, shortest).
  
  Calculates three route variants optimized for different criteria:
  1. Fastest: minimum time (prefers highways)
  2. Cheapest: minimum toll + fuel cost
  3. Shortest: minimum distance
  
  Args:
    origin (str): Starting location (e.g., "New York", "home", or address).
      If None or empty, attempts to use GPS.
    destination (str): Destination location (e.g., "Los Angeles", "office").
  
  Returns:
    tuple: (routes_list, error_string)
      - On success: ([
          {'name': 'Fastest', 'distance_km': ..., 'duration_mins': ..., 'toll': ..., ...},
          {'name': 'Cheapest', ...},
          {'name': 'Shortest', ...}
        ], None)
      - On error: (None, error_message_string)
  
  Note: Uses Nominatim for geocoding (free), haversine for distance, and heuristics
    for toll/fuel estimates. For real-time routing, integrate with Google Maps or
    OpenRouteService APIs.
  """
  try:
    # Get origin location (use GPS if not provided)
    if not origin or origin.lower() in ("current location", "home", "here"):
      origin_name, origin_gps = get_current_location()
      if origin_name is None:
        return None, "Could not detect current location"
      origin = origin_name
    else:
      origin_gps = None
    
    # Geocode origin if GPS not available
    if not origin_gps:
      geocode_url = "https://nominatim.openstreetmap.org/search"
      origin_params = {"q": origin, "format": "json"}
      origin_resp = requests.get(geocode_url, params=origin_params, timeout=6,
                                  headers={"User-Agent": "daduAssistant"})
      if origin_resp.status_code != 200 or not origin_resp.json():
        return None, f"origin_not_found: {origin}"
      origin_data = origin_resp.json()[0]
      origin_gps = {
        'lat': float(origin_data['lat']),
        'lon': float(origin_data['lon']),
        'name': origin_data.get('display_name', origin)
      }
    
    # Geocode destination
    geocode_url = "https://nominatim.openstreetmap.org/search"
    dest_params = {"q": destination, "format": "json"}
    dest_resp = requests.get(geocode_url, params=dest_params, timeout=6,
                              headers={"User-Agent": "daduAssistant"})
    if dest_resp.status_code != 200 or not dest_resp.json():
      return None, f"destination_not_found: {destination}"
    dest_data = dest_resp.json()[0]
    dest_gps = {
      'lat': float(dest_data['lat']),
      'lon': float(dest_data['lon']),
      'name': dest_data.get('display_name', destination)
    }
    
    # Calculate base distance using haversine formula
    lat1, lon1 = origin_gps['lat'], origin_gps['lon']
    lat2, lon2 = dest_gps['lat'], dest_gps['lon']
    
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    distance_km = R * c
    
    # Estimate toll cost
    toll_cost = estimate_toll_cost(origin, destination, distance_km, origin_gps, dest_gps)
    
    # Fuel consumption estimate: ~7 liters per 100 km
    fuel_liters = (distance_km / 100) * 7
    fuel_cost = fuel_liters * 1.5  # Assume $1.50 per liter average
    
    # Build three route variants
    routes = []
    
    # Route 1: FASTEST (highways, higher speed)
    fastest_speed = 100  # km/h (highway average)
    fastest_time_hours = distance_km / fastest_speed
    fastest_time_mins = int(fastest_time_hours * 60)
    fastest_time_with_traffic = int(fastest_time_mins * 1.15)  # 15% traffic delay on highways
    fastest_cost = fuel_cost + (toll_cost * 1.2)  # Highways have more tolls
    
    routes.append({
      'name': 'Fastest Route',
      'distance_km': round(distance_km, 1),
      'duration_mins': fastest_time_with_traffic,
      'duration_hours': round(fastest_time_with_traffic / 60, 2),
      'fuel_liters': round(fuel_liters, 1),
      'toll_cost': round(toll_cost * 1.2, 2),
      'total_cost': round(fastest_cost, 2),
      'description': f"{distance_km:.0f}km, ~{fastest_time_with_traffic}min (highways preferred)",
      'map_url': f"https://www.google.com/maps/dir/{urllib.parse.quote(origin)}/{urllib.parse.quote(destination)}"
    })
    
    # Route 2: CHEAPEST (local roads, avoids tolls)
    cheapest_speed = 60  # km/h (local roads)
    cheapest_time_hours = distance_km / cheapest_speed
    cheapest_time_mins = int(cheapest_time_hours * 60)
    cheapest_time_with_traffic = int(cheapest_time_mins * 1.25)  # 25% traffic delay on local roads
    cheapest_toll = toll_cost * 0.3  # Mostly avoids toll roads
    cheapest_cost = fuel_cost + cheapest_toll
    
    routes.append({
      'name': 'Cheapest Route',
      'distance_km': round(distance_km * 1.05, 1),  # Slightly longer on local roads
      'duration_mins': cheapest_time_with_traffic,
      'duration_hours': round(cheapest_time_with_traffic / 60, 2),
      'fuel_liters': round(fuel_liters * 1.05, 1),
      'toll_cost': round(cheapest_toll, 2),
      'total_cost': round(cheapest_cost, 2),
      'description': f"{distance_km * 1.05:.0f}km, ~{cheapest_time_with_traffic}min (avoids tolls)",
      'map_url': f"https://www.google.com/maps/dir/{urllib.parse.quote(origin)}/{urllib.parse.quote(destination)}"
    })
    
    # Route 3: BALANCED (balanced route)
    balanced_speed = 80  # km/h
    balanced_time_hours = distance_km / balanced_speed
    balanced_time_mins = int(balanced_time_hours * 60)
    balanced_time_with_traffic = int(balanced_time_mins * 1.2)  # 20% traffic delay
    balanced_cost = fuel_cost + toll_cost
    
    routes.append({
      'name': 'Balanced Route',
      'distance_km': round(distance_km, 1),
      'duration_mins': balanced_time_with_traffic,
      'duration_hours': round(balanced_time_with_traffic / 60, 2),
      'fuel_liters': round(fuel_liters, 1),
      'toll_cost': round(toll_cost, 2),
      'total_cost': round(balanced_cost, 2),
      'description': f"{distance_km:.0f}km, ~{balanced_time_with_traffic}min (balanced)",
      'map_url': f"https://www.google.com/maps/dir/{urllib.parse.quote(origin)}/{urllib.parse.quote(destination)}"
    })
    
    return routes, None
    
  except Exception as e:
    return None, str(e)

# Legacy function wrapper for backward compatibility
def fetch_best_route(origin: str, destination: str):
  """Wrapper that returns the cheapest route from fetch_best_routes()."""
  routes, err = fetch_best_routes(origin, destination)
  if err:
    return None, err
  if routes:
    # Return cheapest route (index 1)
    return routes[1], None
  return None, "No routes found"


# speechtex('hello sir, I am your voice assistant. How can I help you?')

if __name__ == "__main__":
  # Main entry point: wait for wake word "dadu"
  if sptext().lower() == "dadu":
    speechtex("How can I help you?")
    while True:
      # Listen for voice command and convert to text
      data = sptext().lower()
      
      # ============ SPOTIFY HANDLER ============
      # Detects: "spotify play [song_name]" or "spotify [song_name]"
      # Extracts search query, searches Spotify API if credentials available,
      # or falls back to opening Spotify search page
      if "spotify" in data:
        # Extract search query by removing keywords
        search_query = data.replace("spotify", "").replace("play", "").strip()
        if search_query:
          speechtex(f"Playing {search_query} on Spotify")
          # Try to use Spotipy to find a top track and open it
          sp, err = get_spotify_client()
          if sp:
            try:
              res = sp.search(q=search_query, type='track', limit=1)
              items = res.get('tracks', {}).get('items', [])
              if items:
                track = items[0]
                track_id = track.get('id')
                track_url = f"https://open.spotify.com/track/{track_id}"
                webbrowser.open(track_url)
              else:
                # fallback to search page
                encoded_query = urllib.parse.quote(search_query)
                webbrowser.open(f"https://open.spotify.com/search/{encoded_query}")
            except Exception:
              encoded_query = urllib.parse.quote(search_query)
              webbrowser.open(f"https://open.spotify.com/search/{encoded_query}")
          else:
            # no credentials; open search page
            encoded_query = urllib.parse.quote(search_query)
            webbrowser.open(f"https://open.spotify.com/search/{encoded_query}")
        else:
          speechtex("Opening Spotify")
          webbrowser.open("https://www.spotify.com")
      elif "youtube" in data or "video" in data or "song" in data or "play" in data:
        # ============ YOUTUBE HANDLER ============
        # Detects: "play [video_name]", "youtube [search]", "song [name]", "video [name]"
        # Extracts search query by removing keywords, uses pywhatkit to auto-play top result,
        # falls back to opening YouTube search results if pywhatkit fails
        search_query = data.replace("youtube", "").replace("video", "").replace("song", "").replace("play", "").strip()
        if search_query:
          speechtex(f"Playing {search_query} on YouTube")
          try:
            # pywhatkit will open and play the top YouTube result
            pywhatkit.playonyt(search_query)
          except Exception:
            # fallback to opening search results
            encoded_query = urllib.parse.quote(search_query)
            webbrowser.open(f"https://www.youtube.com/results?search_query={encoded_query}")
        else:
          speechtex("Opening YouTube")
          webbrowser.open("https://www.youtube.com")
      elif "facebook" in data:
        # ============ FACEBOOK HANDLER ============
        # Detects: "facebook", "open facebook"
        # Opens the main Facebook website
        speechtex("Opening Facebook")
        webbrowser.open("https://www.facebook.com")
      elif "instagram" in data:
        # ============ INSTAGRAM HANDLER ============
        # Detects: "instagram", "open instagram"
        # Opens the main Instagram website
        speechtex("Opening Instagram")
        webbrowser.open("https://www.instagram.com")
      elif "google" in data or "search" in data or "search for" in data:
        # ============ GOOGLE SEARCH HANDLER ============
        # Detects: "google [query]", "search for [query]", "search [query]"
        # Extracts search query by removing common trigger words, URL-encodes it,
        # and opens Google search results page
        search_query = data
        for kw in ("google", "search for", "search", "find", "please", "on google"):
          search_query = search_query.replace(kw, "")
        search_query = search_query.strip()
        if search_query:
          speechtex(f"Searching Google for {search_query}")
          encoded = urllib.parse.quote(search_query)
          webbrowser.open(f"https://www.google.com/search?q={encoded}")
        else:
          speechtex("Opening Google")
          webbrowser.open("https://www.google.com")
      elif any(k in data for k in ("weather","wether","temperature","temrature","temp")):
        # ============ WEATHER HANDLER ============
        # Detects: "weather", "temperature", "weather in [city]", etc.
        # Tries to extract city name from voice input (first looks for "in [city]",
        # then removes common words and uses remainder as city).
        # Calls fetch_weather_for_city() to get live data via OpenWeatherMap API,
        # falls back to opening weather.com if API key missing
        # Try to extract a city: look for 'in <city>' first, else strip trigger words
        city = None
        m = re.search(r'\bin\s+([a-zA-Z \-]+)', data)
        if m:
          city = m.group(1).strip()
        else:
          # remove common words and see what's left
          city_candidate = data
          for kw in ("what's","whats","what","is","the","weather","wether","temperature","temrature","in","at","please","show"):
            city_candidate = city_candidate.replace(kw, "")
          city_candidate = city_candidate.strip()
          if city_candidate:
            city = city_candidate

        if city:
          # Try API lookup if user set OPENWEATHER_API_KEY
          summary, err = fetch_weather_for_city(city)
          if summary:
            print(summary)
            speechtex(summary)
          else:
            if err == 'no_key':
              speechtex("I can open the weather website, or set an OpenWeather API key to get spoken results.")
              webbrowser.open(f"https://www.weather.com/search?q={urllib.parse.quote(city)}")
            else:
              speechtex("Sorry, I couldn't get live weather. Opening a weather website instead.")
              webbrowser.open(f"https://www.weather.com/search?q={urllib.parse.quote(city)}")
        else:
          speechtex("Opening weather report")
          webbrowser.open("https://www.weather.com")
      elif "mute volume" in data:
        # ============ MUTE VOLUME HANDLER ============
        # Detects: "mute volume"
        # Mutes system audio using nircmd utility (Windows only)
        speechtex("Muting volume")
        os.system("nircmd.exe mutesysvolume 1")
      elif "unmute volume" in data:
        # ============ UNMUTE VOLUME HANDLER ============
        # Detects: "unmute volume"
        # Unmutes system audio using nircmd utility (Windows only)
        speechtex("Unmuting volume")
        os.system("nircmd.exe mutesysvolume 0")
      elif "increase volume" in data:
        # ============ INCREASE VOLUME HANDLER ============
        # Detects: "increase volume"
        # Increases system volume by a fixed amount using nircmd utility
        speechtex("Increasing volume")
        os.system("nircmd.exe changesysvolume 2000")
      elif "decrease volume" in data:
        # ============ DECREASE VOLUME HANDLER ============
        # Detects: "decrease volume"
        # Decreases system volume by a fixed amount using nircmd utility
        speechtex("Decreasing volume")
        os.system("nircmd.exe changesysvolume -2000")
      elif "wikipedia" in data:
        # ============ WIKIPEDIA HANDLER ============
        # Detects: "wikipedia [topic]", "search wikipedia for [topic]"
        # Extracts topic by removing keywords, calls fetch_wikipedia_summary(),
        # speaks the summary, and opens the full article page for browsing
        topic = data.replace("wikipedia", "").replace("search", "").replace("about", "").strip()
        if topic:
          speechtex(f"Searching Wikipedia for {topic}")
          summary, err = fetch_wikipedia_summary(topic)
          if summary:
            print(f"Wikipedia: {summary}")
            speechtex(summary)
          else:
            if err == 'not_found':
              speechtex(f"No Wikipedia article found for {topic}. Opening search results instead.")
            elif 'disambiguation' in str(err):
              speechtex(f"Multiple results for {topic}. Opening Wikipedia to choose.")
            else:
              speechtex(f"Could not fetch Wikipedia summary. Opening search instead.")
            encoded_query = urllib.parse.quote(topic)
            webbrowser.open(f"https://en.wikipedia.org/wiki/{encoded_query}")
        else:
          speechtex("Opening Wikipedia")
          webbrowser.open("https://en.wikipedia.org/wiki/Main_Page")
      elif "stackoverflow" in data:
        # ============ STACKOVERFLOW HANDLER ============
        # Detects: "stackoverflow"
        # Opens the Stack Overflow website for coding Q&A
        speechtex("Opening Stackoverflow")
        webbrowser.open("https://www.stackoverflow.com")
      elif "name" in data:
        # ============ NAME HANDLER ============
        # Detects: "what is your name", "tell me your name"
        # Responds with the assistant's name
        speechtex("My name is Dadu, your personal voice assistant.")
      elif "age" in data:
        # ============ AGE HANDLER ============
        # Detects: "how old are you", "what is your age"
        # Responds with a poetic statement
        speechtex("I am timeless.")
      elif "tea" in data:
        # ============ TEA HANDLER ============
        # Detects: "make tea", "tea"
        # Simulates preparing and serving tea with spoken updates
        speechtex("Making tea for you.")
        speechtex("Please wait a moment while I prepare your tea. I hope you enjoy it!")
        speechtex("Your tea is ready. Enjoy!")
      elif any(k in data for k in ("convert", "currency", "exchange")):
        # ============ CONVERSION HANDLER (Currency & Units) ============
        # Detects: "convert [amount] [from_unit] to [to_unit]"
        # Examples: "convert 100 kilometers to miles", "100 dollars to euros"
        # Extracts amount and units using regex, tries currency first, then units
        # Try to extract amount and units: "convert 100 km to miles" or "100 usd to inr"
        import re
        match = re.search(r'(\d+\.?\d*)\s+([a-zA-Z]+)\s+(?:to|into)\s+([a-zA-Z]+)', data)
        if match:
          amount = float(match.group(1))
          from_unit = match.group(2).lower()
          to_unit = match.group(3).lower()
          
          # Try currency first
          result, err = convert_currency(amount, from_unit, to_unit)
          if result:
            print(result)
            speechtex(result)
          else:
            # Try unit conversion
            result, err = convert_unit(amount, from_unit, to_unit)
            if result:
              print(result)
              speechtex(result)
            else:
              speechtex(f"Sorry, I couldn't convert {from_unit} to {to_unit}. Supported: km/miles, kg/lbs, USD/INR/EUR/GBP and temperature.")
        else:
          speechtex("Please say something like: convert 100 kilometers to miles, or 50 dollars to euros.")
      elif any(k in data for k in ("timer", "alarm", "set timer", "set alarm")):
        # ============ TIMER & ALARM HANDLER ============
        # Detects: "set timer for 5 minutes", "set alarm for 7:30 am"
        # Supports both timers (duration in seconds/minutes/hours) and alarms (specific time)
        # Creates background threads that announce when finished/triggered
        # Handle timers and alarms
        # Timer pattern: "set timer for 5 minutes" or "timer 10 seconds"
        m = re.search(r"set (?:a )?timer(?: for)? (\d+\.?\d*)\s*(seconds|second|minutes|minute|hours|hour)?", data)
        if m:
          val = float(m.group(1))
          unit = (m.group(2) or 'seconds').lower()
          multiplier = 1
          if unit.startswith('min'):
            multiplier = 60
          elif unit.startswith('hour'):
            multiplier = 3600
          seconds = int(val * multiplier)
          start_timer_seconds(seconds, label=None)
          speechtex(f"Timer set for {int(val)} {unit}")
        else:
          # Alarm pattern: "set alarm for 7:30 am" or "alarm at 07:30"
          m2 = re.search(r'(?:set )?alarm (?:for|at)?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', data)
          if m2:
            hour = int(m2.group(1))
            minute = int(m2.group(2)) if m2.group(2) else 0
            ampm = m2.group(3)
            if ampm:
              if ampm.lower() == 'pm' and hour != 12:
                hour += 12
              if ampm.lower() == 'am' and hour == 12:
                hour = 0
            now = datetime.datetime.now()
            try:
              alarm_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except Exception:
              speechtex("I couldn't parse that time. Please say for example 'set alarm for 7:30 am'.")
              alarm_dt = None
            if alarm_dt:
              t, err = start_alarm_at(alarm_dt)
              if err == 'past_time':
                speechtex("That time is in the past. I will set it for tomorrow at that time.")
                alarm_dt = alarm_dt + datetime.timedelta(days=1)
                start_timer_seconds(int((alarm_dt - now).total_seconds()))
                speechtex(f"Alarm set for {hour}:{minute:02d} tomorrow.")
              else:
                speechtex(f"Alarm set for {hour}:{minute:02d}")
          else:
            speechtex("Please tell me how long for the timer, for example 'set timer for 5 minutes', or 'set alarm for 7:30 am'.")
      elif "play music" in data:
        # ============ PLAY MUSIC HANDLER ============
        # Detects: "play music"
        # Plays the first audio file found in the D:\Music directory
        # Note: this is hardcoded; can be made more flexible
        music_dir = "D:\\Music"
        songs = os.listdir(music_dir)
        os.startfile(os.path.join(music_dir, songs[0]))
      elif "recipe" in data or "cook" in data:
        # ============ RECIPE HANDLER ============
        # Detects: "recipe for [dish]", "how to cook [dish]"
        # Extracts dish name by removing keywords, calls fetch_recipe(),
        # speaks ingredients and steps, opens full recipe page for browsing
        dish = data
        for kw in ("recipe for", "how to cook", "cook", "make", "please"):
          dish = dish.replace(kw, "")
        dish = dish.strip()
        if dish:
          speechtex(f"Finding recipe for {dish}")
          recipe_text, err = fetch_recipe(dish)
          if recipe_text:
            print(recipe_text)
            speechtex(recipe_text)
            encoded_dish = urllib.parse.quote(dish)
            webbrowser.open(f"https://www.allrecipes.com/search/results/?wt={encoded_dish}&sort=re")
          else:
            speechtex(f"Sorry, I couldn't find a recipe for {dish}. Opening recipe search instead.")
            encoded_dish = urllib.parse.quote(dish)
            webbrowser.open(f"https://www.allrecipes.com/search/results/?wt={encoded_dish}&sort=re")
        else:
          speechtex("Please tell me which dish you want the recipe for.")
      elif "time" in data:
        # ============ TIME HANDLER ============
        # Detects: "what time is it", "tell me the time"
        # Returns current time in HH:MM:SS format
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        speechtex(f"The time is {time_str}")
      elif "date" in data:
        # ============ DATE HANDLER ============
        # Detects: "what is the date", "today's date"
        # Returns current date in DD:MM:YYYY format
        date_str = datetime.datetime.now().strftime("%d:%m:%Y")
        speechtex(f"Today's date is {date_str}")
      elif "joke" in data:
        # ============ JOKE HANDLER ============
        # Detects: "tell me a joke", "joke"
        # Fetches and speaks a random joke using pyjokes library
        joke = pyjokes.get_joke()
        print(joke)
        speechtex(joke)
      elif "news" in data:
        # ============ NEWS HANDLER ============
        # Detects: "news", "news about [category]", "technology news"
        # Extracts news category if mentioned (business, entertainment, health, 
        # science, sports, technology), fetches top 3 headlines via fetch_news_headlines(),
        # speaks each headline, then opens Google News website for more details
        # Extract category if mentioned: "news about technology", "sports news", etc.
        category = "general"
        for cat in ("business", "entertainment", "health", "science", "sports", "technology"):
          if cat in data:
            category = cat
            break
        
        speechtex(f"Fetching {category} news headlines for you.")
        headlines, err = fetch_news_headlines(category, limit=3)
        if headlines:
          for i, headline in enumerate(headlines, 1):
            # Speak each headline
            print(f"{i}. {headline}")
            speechtex(f"Headline {i}: {headline}")
          speechtex("For more details, opening news website.")
          webbrowser.open("https://news.google.com/topstories")
        else:
          speechtex("Sorry, I couldn't fetch news. Opening Google News instead.")
          webbrowser.open("https://news.google.com/topstories")
      elif any(k in data for k in ("route", "directions", "best route", "navigate", "drive to")):
        # ============ ROUTE & DIRECTIONS HANDLER ============
        # Detects: "best route to [destination]", "directions to [location]", "navigate to [place]"
        # Features:
        # 1. Extracts destination by removing keywords
        # 2. Auto-detects current location via GPS (or IP geolocation fallback)
        # 3. Calls fetch_best_routes() to get 3 optimized route variants:
        #    - Fastest: prefers highways, minimum time
        #    - Cheapest: avoids tolls, minimum cost
        #    - Balanced: trade-off between speed and cost
        # 4. Speaks all 3 routes with details (distance, time, fuel, toll, total cost)
        # 5. Opens Google Maps for interactive navigation
        
        destination = data
        for kw in ("route", "directions", "best route", "navigate", "drive to", "to", "please"):
          destination = destination.replace(kw, "")
        destination = destination.strip()
        
        if destination:
          speechtex(f"Finding best routes to {destination}")
          
          # Auto-detect current location (GPS or IP-based)
          origin = None  # Will use GPS detection in fetch_best_routes()
          
          routes, err = fetch_best_routes(origin, destination)
          if routes:
            speechtex(f"Found {len(routes)} route options for you.")
            
            # Speak all route options
            for idx, route in enumerate(routes, 1):
              msg = f"Option {idx}: {route['name']}. "
              msg += f"{route['distance_km']} kilometers, "
              msg += f"about {route['duration_mins']} minutes with traffic. "
              msg += f"Fuel: {route['fuel_liters']} liters, "
              msg += f"Tolls: ${route['toll_cost']}, "
              msg += f"Total cost: ${route['total_cost']}"
              print(msg)
              speechtex(msg)
            
            # Open cheapest route on Google Maps (index 1)
            speechtex(f"Opening the cheapest route on Google Maps.")
            webbrowser.open(routes[1]['map_url'])
          else:
            speechtex(f"Sorry, I couldn't find routes to {destination}. Error: {err}")
            # Fallback: open Google Maps
            webbrowser.open(f"https://www.google.com/maps/dir/?daddr={urllib.parse.quote(destination)}")
        else:
          speechtex("Please tell me where you want to go. For example, 'directions to New York'.")
      elif "exit" in data:
        speechtex("Exiting, goodbye!")
        break
  else:
    print("Voice command not recognized.")
