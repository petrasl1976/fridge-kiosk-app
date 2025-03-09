try:
    import my_secrets
except ImportError:
    raise RuntimeError("Nerastas secrets.py failas! Sukurk jį ir įrašyk slaptus parametrus.")

class Config:
    CLIENT_SECRETS_FILE = "client_secret.json"
    FAMILY_CALENDAR_ID = my_secrets.FAMILY_CALENDAR_ID
    EVENT_SUMMARY_MAX_LENGTH = 30
    PHOTO_DURATION = 30           # s
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
        "2025-01-01": "Naujųjų metų diena",
        "2025-02-16": "Valstybės atkūrimo diena",
        # ir t. t.
    }

    METEO_API_BASE_URL = "https://api.meteo.lt/v1"
    DISCORD_API_BASE_URL = "https://discord.com/api/v9"

    WEATHER = {
        "LOCATION": "vilnius-paneriai",
        "UNITS": "metric",
        "REFRESH_INTERVAL": 3600,
    }

    DISCORD = {
        "BOT_TOKEN": my_secrets.DISCORD_BOT_TOKEN,
        "CHANNEL_ID": "1320327774548000828",
        "MESSAGE_COUNT": 10,
    }

    BROADLINK = {
        "DISCOVER_TIMEOUT": 5,
        "TARGET_TYPE_PREFIX": "RM4",
    }

    # Overlay parametrai
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
        "font_size": "2.5em",
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
        "width": "50%",
        "height": "30%",
        "z_index": 9999,
        "font_size": "2em",
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
        "font_size": "2em",
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
        "clock_font_size": "8em",
        "date_font_size": "4.1em",
        "events_font_size": "2em",
        "sensor_font_size": "2.5em"
    }

