import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    CLIENT_SECRETS_FILE = "client_secret.json"
    FAMILY_CALENDAR_ID = os.getenv("FAMILY_CALENDAR_ID")
    EVENT_SUMMARY_MAX_LENGTH = 30
    PHOTO_DURATION = 30           # s
    VIDEO_DURATION = 60           # s - maximum video display duration
    MEDIA_TYPES = "all"           # Media types to show: "photo", "video" or "all"
    VIDEO_SOUND = True            # Allow video sound
    PHOTO_BATCH_COUNT = 5
    WEEKS_TO_SHOW = 5
    SHOW_HOLIDAYS = True

    EVENT_COLORS = {
        "PE": "#4d26f0",
        "BU": "#4d26f0",
        "LI": "#003300",
        "LA": "#3e5393",
        "DA": "#a07ed3",
        "GI": "#660000"
    }
    DEFAULT_EVENT_COLOR = "#000000"

    HOLIDAYS = {
        "2025-01-01": "New Year's Day",
        "2025-02-16": "Independence Day",
        "2025-03-11": "Restoration of Lithuania's Independence Day",
        "2025-04-20": "Easter Sunday",
        "2025-04-21": "Easter Monday",
        "2025-05-01": "International Labor Day",
        "2025-06-24": "St. John's Day (Midsummer)",
        "2025-07-06": "Statehood Day (Coronation of King Mindaugas)",
        "2025-08-15": "Assumption Day",
        "2025-11-01": "All Saints' Day",
        "2025-12-24": "Christmas Eve",
        "2025-12-25": "Christmas Day",
        "2025-12-26": "Boxing Day"
    }

    METEO_API_BASE_URL = "https://api.meteo.lt/v1"
    DISCORD_API_BASE_URL = "https://discord.com/api/v9"

    WEATHER = {
        "LOCATION": "vilnius-paneriai",
        "UNITS": "metric",
        "REFRESH_INTERVAL": 3600,
    }

    DISCORD = {
        "BOT_TOKEN": os.getenv("DISCORD_BOT_TOKEN"),
        "CHANNEL_ID": os.getenv("DISCORD_CHANNEL_ID"),
        "VOICE_CHANNEL_ID": os.getenv("DISCORD_VOICE_CHANNEL_ID"),
        "MESSAGE_COUNT": 10,
        "MIC_ENABLED": False,   # Microphone state: True - enabled, False - disabled
        "SOUND_ENABLED": True   # Sound state: True - enabled, False - disabled
    }

    BROADLINK = {
        "DISCOVER_TIMEOUT": 5,
        "TARGET_TYPE_PREFIX": "RM4",
    }

    # Overlay parameters
    PHOTO_CONTAINER = {
        "top": "0%",
        "left": "0%",
        "width": "100%",
        "height": "60%",
        "z_index": 1,
        "font_size": "1em",
        "background": "#000000"
    }
    PHOTO_INFO_OVERLAY = {
        "top": "8%",
        "left": "0%",
        "width": "100%",
        "height": "4%",
        "z_index": 2,
        "font_size": "2em",
        "background": "rgba(0, 0, 0, 0)",
        "color": "#fff",
        "padding": "10px"
    }
    CALENDAR_CONTAINER = {
        "top": "60%",
        "left": "0%",
        "width": "100%",
        "height": "40%",
        "z_index": 1,
        "font_size": "1.5em",
        "background": "#000000"
    }
    DISCORD_OVERLAY = {
        "top": "14%",
        "left": "0%",
        "width": "65%",
        "height": "45%",
        "z_index": 9999,
        "font_size": "1.5em",
        "background": "rgba(0,0,0,0)",
        "color": "#fff",
        "padding": "10px"
    }
    WEATHER_OVERLAY = {
        "top": "0%",
        "left": "0%",
        "width": "100%",
        "height": "7%",
        "z_index": 9998,
        "font_size": "1.7em",
        "color": "#fff",
        "padding": "10px"
    }
    STATUS_OVERLAY = {
        "top": "7%",
        "left": "65%",
        "width": "30%",
        "height": "auto",
        "z_index": 9999,
        "background": "rgba(0, 0, 0, 0)",
        "color": "#fff",
        "padding": "10px",
        "clock_font_size": "7.2em",     # Slightly larger font size for clock
        "date_font_size": "3.5em",
        "events_font_size": "1.5em",
        "sensor_font_size": "1.8em"     # CPU: you can change sensor data font size here
    }

    # Temperature monitoring settings
    TEMP_MONITORING = True          # Enable CPU temperature monitoring
    TEMP_WARNING = 65               # Temperature (°C) at which to switch to photo mode
    TEMP_CRITICAL = 80              # Critical temperature (°C) at which to restart device
    TEMP_RECOVERY = 60              # Temperature (°C) below which to return to normal mode
    TEMP_CHECK_INTERVAL = 10        # Check interval (seconds)
    
    # Voice overlay settings
    VOICE_OVERLAY = {
        "top": "2%",
        "left": "80%",
        "width": "28%", 
        "height": "auto",
        "z_index": 1000,
        "font_size": "1.5em",
        "background": "rgba(0, 0, 0, 0.7)",
        "color": "#fff",
        "padding": "10px 15px",
        "border_radius": "8px"
    }

