# daduAssistant (voiceReconizer)

daduAssistant is a simple voice-driven personal assistant implemented
in Python. It listens for the wake word "dadu" and responds to voice
commands to perform common tasks like searching, playing media, fetching
weather, summarizing Wikipedia pages, doing conversions, timers/alarms,
fetching news, telling jokes and fetching horoscopes.

## Key files

- `voiceReconizer.py` — main program and entry point. Uses `sptext()` to
  listen and `speechtex()` to speak. Contains helper functions for
  weather, Wikipedia, conversions, news, timers, horoscope, and Spotify
  integration.
- `build_exe.ps1` — PowerShell script that builds a single-file
  executable (`daduAssistant.exe`) using PyInstaller, moves it to
  `dist\dashboard`, creates an optional Desktop shortcut, and copies
  the executable to the Desktop.
- `requirements.txt` — pip-installable dependencies (ensure this is up
  to date before creating the executable).
- `config.json` — optional project configuration file (not included by
  default). Can store `OPENWEATHER_API_KEY`, `SPOTIPY_CLIENT_ID`, and
  `SPOTIPY_CLIENT_SECRET`.

## Features

- Voice activation (wake word: "dadu").
- YouTube playback/search via `pywhatkit` (opens and plays top result).
- Spotify search/open via `spotipy` (client-credentials search or open
  search page if credentials not provided).
- Weather lookup using OpenWeatherMap (requires `OPENWEATHER_API_KEY`).
- Wikipedia summaries (2-sentence summary via `wikipedia` package).
- Currency conversion (uses a free exchangerate API) and common unit
  conversions (distance, weight, temperature).
- News headlines fetch with fallback to alternate APIs.
- Timers and alarms (background threads).
- Horoscope lookup using Aztro API.
- **Route optimization**: Find best routes considering distance, time, fuel
  consumption (estimated), and toll costs (estimated). Uses OpenStreetMap
  Nominatim for geocoding and calculates route via haversine distance.
  Opens Google Maps for interactive navigation.
  - **GPS Auto-detection**: Automatically detects current location via GPS or
    IP-based geolocation.
  - **Multi-route Suggestions**: Shows 3 optimized routes:
    - **Fastest Route**: Prefers highways, minimizes time (~15% traffic delay)
    - **Cheapest Route**: Avoids tolls, minimizes total cost (~25% traffic delay)
    - **Balanced Route**: Trade-off between speed and cost (~20% traffic delay)
  - **Toll Estimation**: Regional toll database (USA regions supported), estimates
    toll costs based on route and location.
  - **Fuel & Cost Estimation**: Calculates fuel consumption (~7L per 100km) and
    total trip cost (fuel + tolls).

## Setup (development)

1. Install Python 3.10+ (the project was developed with Python 3.13).
2. Create and activate a virtual environment (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you encounter audio-related errors (PyAudio missing on Windows), the
following steps often help:

```powershell
python -m pip install pipwin
python -m pipwin install pyaudio
```

Optional: For GPS location detection, install:

```powershell
python -m pip install geolocation-python
```

Note: on Windows, installing `pyaudio` sometimes requires the `pipwin`
helper which installs prebuilt wheels. The geolocation package is optional;
the assistant gracefully falls back to IP-based geolocation if GPS unavailable.

## Configuration

- Provide an OpenWeatherMap API key to enable spoken weather results.
  You can set it as an environment variable or save it to `config.json`:

PowerShell (current session):

```powershell
$env:OPENWEATHER_API_KEY = 'your_openweather_key_here'
```

Persist for future sessions (Windows):

```powershell
setx OPENWEATHER_API_KEY "your_openweather_key_here"

Or create a `config.json` in the project root with:

```json
{"OPENWEATHER_API_KEY":"your_openweather_key_here"}

- For Spotify searches using the API, set `SPOTIPY_CLIENT_ID` and
  `SPOTIPY_CLIENT_SECRET` in `config.json` or as environment variables.

## Running locally

From the project root (development):

```powershell
python voiceReconizer.py

Speak the wake word "dadu" when prompted, then issue commands like:

- "dadu, search YouTube for lo-fi beats"
- "dadu, what's the weather in Delhi"
- "dadu, convert 10 kilometers to miles"
- "dadu, set timer for 2 minutes"
- "dadu, best route to New York"
- "dadu, directions to the airport"
- "dadu, navigate to Times Square"

## Building a single-file executable

The repository includes `build_exe.ps1` which automates PyInstaller
build steps. From PowerShell in the project folder run:

```powershell
.\build_exe.ps1

The script will:

- Install PyInstaller if missing
- Build a one-file exe named `daduAssistant.exe`
- Move the exe into `dist\dashboard`
- Prompt to create a Desktop shortcut
- Copy `daduAssistant.exe` to your Desktop

If you want the exe only on the Desktop (without `dist\dashboard`),
edit `build_exe.ps1` accordingly.

## Troubleshooting

- Missing `gtts`/`playsound` errors: these packages were used in earlier
  multilingual experiments and are not required in the current single-
  language build. If prompted for them, run `pip install gTTS playsound`.
- Microphone errors (no PyAudio): see the Setup section above.
- If web APIs fail, the assistant falls back to opening web pages.

## Security & privacy

- `config.json` may contain API keys — do not commit this file to
  public repositories. Use environment variables for CI/servers.


If you want, I can also update `README-packaging.md` or add a
`CONTRIBUTING.md` with development notes.

