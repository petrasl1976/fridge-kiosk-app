import os
from dotenv import load_dotenv

# Įkrauname .env failą
load_dotenv()

class Config:
    CLIENT_SECRETS_FILE = "client_secret.json"
    FAMILY_CALENDAR_ID = os.getenv("FAMILY_CALENDAR_ID")
    EVENT_SUMMARY_MAX_LENGTH = 30
    PHOTO_DURATION = 30           # s
    VIDEO_DURATION = 60           # s - maksimali video rodymo trukmė
    MEDIA_TYPES = "all"           # Kokio tipo media rodyti: "photo", "video" arba "all"
    VIDEO_SOUND = True            # Ar leisti video garsą
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
        "2025-03-11": "Lietuvos Nepriklausomybės atkūrimo diena",
        "2025-04-20": "Šv. Velykos",
        "2025-04-21": "Šv. Velykų antroji diena",
        "2025-05-01": "Tarptautinė darbo diena",
        "2025-06-24": "Rasos ir Joninių diena",
        "2025-07-06": "Valstybės (Mindaugo karūnavimo) diena",
        "2025-08-15": "Žolinė (Švč. Mergelės Marijos ėmimo į dangų diena)",
        "2025-11-01": "Visų šventųjų diena",
        "2025-12-24": "Šv. Kūčios",
        "2025-12-25": "Šv. Kalėdos (pirma diena)",
        "2025-12-26": "Šv. Kalėdos (antra diena)"
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
        "MIC_ENABLED": False,   # Mikrofono būsena: True - įjungtas, False - išjungtas
        "SOUND_ENABLED": True   # Garso būsena: True - įjungtas, False - išjungtas
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
        "clock_font_size": "7.2em",     # Vos didesnis laikrodžio šriftas
        "date_font_size": "3.5em",
        "events_font_size": "1.5em",
        "sensor_font_size": "1.8em"     # CPU: čia galite keisti sensoriaus duomenų šrifto dydį
    }

    # Temperatūros stebėjimo nustatymai
    TEMP_MONITORING = True          # Ar įjungtas CPU temperatūros stebėjimas
    TEMP_WARNING = 65               # Temperatūra (°C), kurią pasiekus perjungiama į foto režimą
    TEMP_CRITICAL = 80              # Kritinė temperatūra (°C), kurią pasiekus restartuojamas įrenginys
    TEMP_RECOVERY = 60              # Temperatūra (°C), kuriai nukritus galima grįžti į normalų režimą
    TEMP_CHECK_INTERVAL = 10        # Tikrinimo intervalas (sekundėmis)
    
    # Voice overlay nustatymai
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

