#!/home/kiosk/fridge-kiosk-app/venv/bin/python3
import os
import json
import time
import datetime
import random
import requests
from collections import defaultdict
import logging
import subprocess
import hashlib
import base64
import threading

from flask import Flask, render_template, redirect, url_for, session, request, jsonify, Response, make_response
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

# Išjungiame cache įspėjimą
import googleapiclient.discovery_cache
googleapiclient.discovery_cache.LOGGER.setLevel(logging.ERROR)

# Išjungiame werkzeug įprastų HTTP užklausų logginimą
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)  # Rodyti tik WARNING ir aukštesnio lygio žinutes

import broadlink
from config import Config
from temp_monitor import TemperatureMonitor

# Bandome importuoti Discord voice modulį, jei jis egzistuoja
try:
    from discord_voice import DiscordVoiceClient
    discord_available = True
except ImportError:
    app.logger.warning("Discord voice modulis nėra prieinamas. Voice kanalas neveiks.")
    discord_available = False

# Pridedame zoneinfo (veikia nuo Python 3.9). Jei neturite, naudokite pytz.
from zoneinfo import ZoneInfo

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__, static_folder='static')
app.secret_key = "something_secret"

SCOPES = [
    'https://www.googleapis.com/auth/photoslibrary.readonly',
    'https://www.googleapis.com/auth/calendar.readonly'
]

ALBUMS_CACHE_FILE = 'albums_cache.json'
CACHE_EXPIRATION = 30 * 24 * 3600  # 30 dienų (buvo 7)

# Inicializuojame temperatūros stebėjimą
temp_monitor = TemperatureMonitor(Config)

# Inicializuojame Discord voice klientą, jei yra konfiguracijos ir modulis prieinamas
voice_client = None
if discord_available and Config.DISCORD and Config.DISCORD.get('BOT_TOKEN') and Config.DISCORD.get('VOICE_CHANNEL_ID'):
    try:
        voice_client = DiscordVoiceClient(
            token=Config.DISCORD.get('BOT_TOKEN'),
            channel_id=Config.DISCORD.get('VOICE_CHANNEL_ID')
        )
        app.logger.info('Discord voice klientas sukurtas')
    except Exception as e:
        app.logger.error(f'Klaida inicializuojant Discord voice klientą: {e}')

def load_album_cache():
    try:
        with open(ALBUMS_CACHE_FILE, 'r') as f:
            cache = json.load(f)
            age = time.time() - cache.get('timestamp', 0)
            if age < CACHE_EXPIRATION:
                return cache.get('albums', [])
    except:
        pass
    return []

def save_album_cache(albums):
    cache = {
        'timestamp': time.time(),
        'albums': albums
    }
    try:
        with open(ALBUMS_CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except:
        pass

def get_all_albums(photos_service):
    albums = load_album_cache()
    if albums:
        return albums

    albums = []
    next_page_token = None
    while True:
        resp = photos_service.albums().list(pageSize=50, pageToken=next_page_token).execute()
        found_albums = resp.get('albums', [])
        albums.extend(found_albums)
        next_page_token = resp.get('nextPageToken')
        if not next_page_token:
            break

    save_album_cache(albums)
    return albums

def get_all_media_items(photos_service, album_id):
    items = []
    next_page_token = None
    while True:
        resp = photos_service.mediaItems().search(
            body={'albumId': album_id, 'pageSize': 100, 'pageToken': next_page_token}
        ).execute()
        found_items = resp.get('mediaItems', [])
        items.extend(found_items)
        next_page_token = resp.get('nextPageToken')
        if not next_page_token:
            break
    return items

def get_random_photo_batch(photos_service):
    try:
        albums = get_all_albums(photos_service)
        if not albums:
            app.logger.warning("Nerasta albumų.")
            return [{"error": "No albums found"}], "Error"
        
        # Sumaišome albumus atsitiktine tvarka
        random.shuffle(albums)
        
        # Bandome per visus albumus, kol rasime tinkamą
        for album_attempt in range(len(albums)):
            album = albums[album_attempt]
            album_title = album.get('title', 'Unknown Album')
            app.logger.info(f"Trying album: {album_title} (attempt {album_attempt+1}/{len(albums)})")
            
            try:
                items = get_all_media_items(photos_service, album['id'])
                if not items:
                    app.logger.info(f"Album {album_title} has no items, skipping")
                    continue

                # Filtruojame tik tuos, kurie turi creationTime
                items = [i for i in items if i.get('mediaMetadata', {}).get('creationTime')]
                if not items:
                    app.logger.info(f"Album {album_title} has no items with creationTime, skipping")
                    continue

                # Identifikuojame medijos tipus ir filtruojame pagal MEDIA_TYPES nustatymą
                processed_items = []
                for item in items:
                    meta = item.get('mediaMetadata', {})
                    # Nustatome medijos tipą ir pridedame papildomus metaduomenis
                    media_type = "photo"
                    video_metadata = {}
                    
                    if 'video' in meta:
                        media_type = "video"
                        video_metadata = meta.get('video', {})
                    
                    # Filtruojame pagal nustatytą medijos tipą
                    if Config.MEDIA_TYPES.lower() == "all" or Config.MEDIA_TYPES.lower() == media_type:
                        processed_items.append({
                            'baseUrl': item.get('baseUrl', ''),
                            'photo_time': meta.get('creationTime', ''),
                            'filename': item.get('filename', 'Unknown'),
                            'mediaType': media_type,
                            'videoMetadata': video_metadata,
                            'mimeType': item.get('mimeType', '')
                        })
                
                # Jei šiame albume yra tinkamo tipo medijos, naudojame ją
                if processed_items:
                    app.logger.info(f"Album {album_title} has {len(processed_items)} matching items of type {Config.MEDIA_TYPES}")
                    
                    # Rūšiuojame pagal creationTime
                    processed_items.sort(key=lambda x: x['photo_time'])
                    total = len(processed_items)
                    start_index = random.randint(0, total - 1)
                    batch = []
                    
                    # Renkame batch
                    count = min(Config.PHOTO_BATCH_COUNT, total)
                    for i in range(count):
                        idx = (start_index + i) % total
                        batch.append(processed_items[idx])

                    return batch, album_title
                else:
                    app.logger.info(f"Album {album_title} has no matching items of type {Config.MEDIA_TYPES}, skipping")
            except googleapiclient.errors.HttpError as error:
                app.logger.error(f"Error processing album {album_title}: {error}")
                if error.resp.status == 429:
                    # Quota exceeded - sustojame ir grąžiname klaidos pranešimą
                    app.logger.warning("Google Photos API quota exceeded")
                    return [{"error": "Google Photos API quota exceeded", "mediaType": "error"}], "API Limit Error"
                # Tęsiame su kitu albumu, jei klaida su dabartiniu
                continue
        
        # Jei apeiti visus albumus ir nerasta tinkamo tipo medijos
        app.logger.warning(f"No albums with media type '{Config.MEDIA_TYPES}' found after checking all {len(albums)} albums")
        
    except Exception as e:
        app.logger.error(f"Unexpected error in get_random_photo_batch: {e}")
        return [{"error": str(e), "mediaType": "error"}], "Error"
    
    # Jei niekas nerasta
    return [{"error": "No suitable media found", "mediaType": "error"}], "No Media"

def parse_meteo_lt_time(dt_str):
    fmts = ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]
    for fmt in fmts:
        try:
            return datetime.datetime.strptime(dt_str, fmt)
        except:
            pass
    raise ValueError(f"Bad time format: {dt_str}")

def get_weather():
    url = f"{Config.METEO_API_BASE_URL}/places/{Config.WEATHER['LOCATION']}/forecasts/long-term"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    data = r.json()
    forecasts = data.get("forecastTimestamps", [])
    by_date = {}
    for entry in forecasts:
        dt_obj = parse_meteo_lt_time(entry["forecastTimeUtc"])
        date_str = dt_obj.strftime("%Y-%m-%d")
        by_date.setdefault(date_str, []).append(entry)
    daily_list = []
    for date_str in sorted(by_date.keys()):
        daily_entries = by_date[date_str]
        if not daily_entries:
            continue
        min_temp, max_temp = None, None
        best_condition, best_dt_obj = None, None
        best_diff = 24
        for f in daily_entries:
            t = f["airTemperature"]
            if min_temp is None or t < min_temp:
                min_temp = t
            if max_temp is None or t > max_temp:
                max_temp = t
            dt_obj = parse_meteo_lt_time(f["forecastTimeUtc"])
            midday = dt_obj.replace(hour=12, minute=0, second=0, microsecond=0)
            diff = abs((dt_obj - midday).total_seconds()) / 3600.0
            if diff < best_diff:
                best_diff = diff
                best_condition = f["conditionCode"]
                best_dt_obj = dt_obj
        if not best_dt_obj:
            f0 = daily_entries[0]
            best_dt_obj = parse_meteo_lt_time(f0["forecastTimeUtc"])
            best_condition = f0["conditionCode"]
        daily_list.append({
            "dt": int(best_dt_obj.timestamp()),
            "main": {"temp_min": min_temp, "temp_max": max_temp},
            "weather": [{"description": best_condition}]
        })
    daily_list = daily_list[:7]
    return {"daily": daily_list}

def get_sensor_data():
    try:
        # Gauname sensoriaus duomenis
        sensor_data = {}
        devices = broadlink.discover(timeout=Config.BROADLINK["DISCOVER_TIMEOUT"])
        for d in devices:
            if d.type.startswith(Config.BROADLINK["TARGET_TYPE_PREFIX"]):
                d.auth()
                sensor_data = d.check_sensors()
                break
        
        # Jei nėra sensoriaus duomenų ar yra klaida, sukuriame tuščią objektą
        if not sensor_data or "error" in sensor_data:
            sensor_data = {}
        
        # Pridedame CPU temperatūrą
        cpu_temp = temp_monitor.get_cpu_temperature()
        temp_status = temp_monitor.get_status()
        
        # Sujungiame duomenis
        result = {
            "temperature": sensor_data.get("temperature"),
            "humidity": sensor_data.get("humidity"),
            "cpu_temp": cpu_temp
        }
        
        # Jei nėra sensoriaus duomenų, bet yra CPU temperatūra, nerodome klaidos
        if cpu_temp > 0 and ("error" in sensor_data or not sensor_data):
            result.pop("error", None)
            
        # Jei yra klaida iš sensoriaus, ją išlaikome
        if "error" in sensor_data:
            result["error"] = sensor_data["error"]
            
        return result
    except Exception as e:
        return {"error": str(e), "cpu_temp": temp_monitor.get_cpu_temperature()}

def get_username_color(username):
    prefix = username[:2].upper()
    return Config.EVENT_COLORS.get(prefix, Config.DEFAULT_EVENT_COLOR)

def get_event_color(summary):
    if not summary:
        return Config.DEFAULT_EVENT_COLOR
    prefix = summary[:2].upper()
    return Config.EVENT_COLORS.get(prefix, Config.DEFAULT_EVENT_COLOR)

# Registruojame filtrą event_color
app.jinja_env.filters['event_color'] = get_event_color

@app.template_filter('strftime')
def strftime_filter(value, fmt='%Y-%m-%d'):
    return value.strftime(fmt)

@app.template_filter('datetime_fromtimestamp')
def datetime_fromtimestamp_filter(ts):
    return datetime.datetime.fromtimestamp(int(ts))

@app.route('/newsensors')
def newsensors():
    data = get_sensor_data()
    return jsonify(data)

@app.route('/discordmessages')
def discord_messages():
    # Gaunama ne tik žinutės turinys, bet ir embeds bei attachments
    params = {
        "limit": Config.DISCORD['MESSAGE_COUNT']
    }
    url = f"{Config.DISCORD_API_BASE_URL}/channels/{Config.DISCORD['CHANNEL_ID']}/messages"
    headers = {"Authorization": f"Bot {Config.DISCORD['BOT_TOKEN']}"}
    
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 200:
        messages = r.json()
        for m in messages:
            username = m['author']['username']
            m['color'] = get_username_color(username)
            
            # Užtikrinam, kad paveikslėliai nebūtų supressinti (Proxy URL nėra atfiltruoti)
            if 'attachments' in m and m['attachments']:
                for attachment in m['attachments']:
                    if 'proxy_url' in attachment and not 'url' in attachment:
                        attachment['url'] = attachment['proxy_url']
            
            # Užtikrinam, kad embed paveikslėliai nebūtų supressinti
            if 'embeds' in m and m['embeds']:
                for embed in m['embeds']:
                    if 'image' in embed and 'proxy_url' in embed['image'] and not 'url' in embed['image']:
                        embed['image']['url'] = embed['image']['proxy_url']
                    if 'thumbnail' in embed and 'proxy_url' in embed['thumbnail'] and not 'url' in embed['thumbnail']:
                        embed['thumbnail']['url'] = embed['thumbnail']['proxy_url']
                        
        return jsonify(messages)
    return jsonify({"error": "Unable to fetch messages"}), r.status_code

def load_stored_credentials():
    if os.path.exists("token.json"):
        try:
            with open("token.json", 'r') as token_file:
                token_data = json.load(token_file)
                return google.oauth2.credentials.Credentials(**token_data)
        except:
            pass
    return None

@app.route('/')
def index():
    creds = load_stored_credentials()
    if creds is None:
        return redirect(url_for('authorize'))

    photo_batch = []
    album_title = ""
    error_message = None

    try:
        photos_service = googleapiclient.discovery.build(
            'photoslibrary', 'v1', credentials=creds,
            discoveryServiceUrl='https://photoslibrary.googleapis.com/$discovery/rest?version=v1'
        )

        photo_batch, album_title = get_random_photo_batch(photos_service)
        # Patikriname, ar turime klaidos pranešimą
        if photo_batch and len(photo_batch) > 0 and 'error' in photo_batch[0]:
            error_message = photo_batch[0]['error']
    except Exception as e:
        app.logger.error(f"Error getting photos: {e}")
        photo_batch = [{"error": f"Failed to get photos: {str(e)}", "mediaType": "error"}]
        album_title = "Error"

    cal_service = googleapiclient.discovery.build('calendar', 'v3', credentials=creds)
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    start_of_week = today - datetime.timedelta(days=today.weekday())
    end_of_range = start_of_week + datetime.timedelta(days=(Config.WEEKS_TO_SHOW * 7) - 1)
    time_min = start_of_week.isoformat() + 'T00:00:00Z'
    time_max = end_of_range.isoformat() + 'T23:59:59Z'
    ev_res = cal_service.events().list(
        calendarId=Config.FAMILY_CALENDAR_ID,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime',
        timeZone='Europe/Vilnius'
    ).execute()
    events = ev_res.get('items', [])

    events_by_day = defaultdict(list)
    for e in events:
        s = e['start'].get('dateTime', e['start'].get('date'))
        day_str = s[:10]
        events_by_day[day_str].append(e)

    weeks = []
    cur_day = start_of_week
    for _ in range(Config.WEEKS_TO_SHOW):
        row = []
        for __ in range(7):
            row.append(cur_day)
            cur_day += datetime.timedelta(days=1)
        weeks.append(row)

    weather = get_weather()

    session['credentials'] = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }

    return render_template(
        "index.html",
        photo_batch=photo_batch,
        album_title=album_title if album_title else "",
        weather=weather,
        weeks=weeks,
        events_by_day=events_by_day,
        today=today,
        tomorrow=tomorrow,
        weather_overlay=Config.WEATHER_OVERLAY,
        photo_container=Config.PHOTO_CONTAINER,
        photo_info_overlay=Config.PHOTO_INFO_OVERLAY,
        discord_overlay=Config.DISCORD_OVERLAY,
        calendar_container=Config.CALENDAR_CONTAINER,
        status_overlay=Config.STATUS_OVERLAY,
        photo_duration=Config.PHOTO_DURATION,
        video_duration=Config.VIDEO_DURATION,
        media_types=Config.MEDIA_TYPES,
        video_sound=Config.VIDEO_SOUND,
        weather_refresh_interval=Config.WEATHER.get("REFRESH_INTERVAL", 3600),
        summary_max_length=Config.EVENT_SUMMARY_MAX_LENGTH,
        show_holidays=Config.SHOW_HOLIDAYS,
        holidays=Config.HOLIDAYS,
        config=Config,  # Pridedame config objektą
        error_message=error_message
    )

@app.route('/newphoto')
def newphoto():
    creds_data = session.get('credentials')
    if not creds_data:
        return jsonify({"error": "No credentials in session"}), 403

    try:
        creds = google.oauth2.credentials.Credentials(**creds_data)
        photos_service = googleapiclient.discovery.build(
            'photoslibrary', 'v1', credentials=creds,
            discoveryServiceUrl='https://photoslibrary.googleapis.com/$discovery/rest?version=v1'
        )

        photo_batch, album_title = get_random_photo_batch(photos_service)
        
        # Patikriname, ar photo_batch yra None arba turi klaidos pranešimą
        if not photo_batch:
            return jsonify({"error": "No photos found", "photos": [{"error": "No photos found", "mediaType": "error"}]}), 404
        
        # Jei pirmas elementas turi error lauką, grąžiname klaidos pranešimą bet su 200 statusu
        if 'error' in photo_batch[0]:
            return jsonify({"error": photo_batch[0]['error'], "photos": photo_batch, "album_title": album_title})

        return jsonify({"photos": photo_batch, "album_title": album_title})
        
    except Exception as e:
        app.logger.error(f"Error in newphoto: {e}")
        # Grąžiname klaidos pranešimą, bet su 200 statusu kad frontend galėtų jį apdoroti
        return jsonify({"error": str(e), "photos": [{"error": str(e), "mediaType": "error"}], "album_title": "Error"})

@app.route('/newweather')
def newweather():
    w = get_weather()
    if w:
        return jsonify(w)
    return jsonify({"error": "Unable to fetch weather"}), 500

@app.route('/calendarevents')
def calendarevents():
    creds_data = session.get('credentials')
    if not creds_data:
        return "No credentials", 403

    creds = google.oauth2.credentials.Credentials(**creds_data)
    cal_service = googleapiclient.discovery.build('calendar', 'v3', credentials=creds)

    today = datetime.date.today()
    start_of_week = today - datetime.timedelta(days=today.weekday())
    end_of_range = start_of_week + datetime.timedelta(days=(Config.WEEKS_TO_SHOW * 7) - 1)
    time_min = start_of_week.isoformat() + 'T00:00:00Z'
    time_max = end_of_range.isoformat() + 'T23:59:59Z'

    ev_res = cal_service.events().list(
        calendarId=Config.FAMILY_CALENDAR_ID,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime',
        timeZone='Europe/Vilnius'
    ).execute()
    events = ev_res.get('items', [])

    events_by_day = defaultdict(list)
    for e in events:
        s = e['start'].get('dateTime', e['start'].get('date'))
        day_str = s[:10]
        events_by_day[day_str].append(e)

    weeks = []
    cur_day = start_of_week
    for _ in range(Config.WEEKS_TO_SHOW):
        row = []
        for __ in range(7):
            row.append(cur_day)
            cur_day += datetime.timedelta(days=1)
        weeks.append(row)

    return render_template(
        'calendar_fragment.html',
        weeks=weeks,
        events_by_day=events_by_day,
        today=today,
        holidays=Config.HOLIDAYS,
        summary_max_length=Config.EVENT_SUMMARY_MAX_LENGTH,
        show_holidays=Config.SHOW_HOLIDAYS
    )

###################################################################################
# Pataisytas /todayevents maršrutas, kad rodytų vietinę (Europe/Vilnius) parą
###################################################################################
@app.route('/todayevents')
def todayevents():
    creds_data = session.get('credentials')
    if not creds_data:
        return "No credentials", 403

    creds = google.oauth2.credentials.Credentials(**creds_data)
    cal_service = googleapiclient.discovery.build('calendar', 'v3', credentials=creds)

    # Nustatome laiko zoną
    vilnius_tz = ZoneInfo('Europe/Vilnius')

    # Šiandienos vidurnaktis vietos laiku
    now = datetime.datetime.now(vilnius_tz)
    local_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Dienos pabaiga (23:59:59) - 1 sek. iki kitos paros
    local_end = local_midnight + datetime.timedelta(days=1, seconds=-1)

    # Konvertuojame į ISO formatą be 'Z' (nes tai vietinis laikas, ne UTC)
    time_min = local_midnight.isoformat()
    time_max = local_end.isoformat()

    ev_res = cal_service.events().list(
        calendarId=Config.FAMILY_CALENDAR_ID,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime',
        timeZone='Europe/Vilnius'
    ).execute()
    events = ev_res.get('items', [])

    # Grąžiname fragmentą, kuriame bus spalvos
    return render_template(
        'today_events_fragment.html',
        events=events,
        summary_max_length=Config.EVENT_SUMMARY_MAX_LENGTH
    )

@app.route('/authorize')
def authorize():
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        Config.CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = url_for('oauth2callback', _external=True)
    url_, state_ = flow.authorization_url(
        access_type='offline', prompt='consent', include_granted_scopes='true')
    session['state'] = state_
    return redirect(url_)

@app.route('/oauth2callback')
def oauth2callback():
    st = session['state']
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        Config.CLIENT_SECRETS_FILE, scopes=SCOPES, state=st)
    flow.redirect_uri = url_for('oauth2callback', _external=True)
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    if not creds.refresh_token:
        session.pop('credentials', None)
        return redirect(url_for('authorize'))
    token_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    with open("token.json", "w") as token_file:
        json.dump(token_data, token_file)
    session['credentials'] = token_data
    return redirect(url_for('index'))

@app.route('/systemstatus')
def system_status():
    """Grąžina sistemos būsenos informaciją JSON formatu"""
    status = {
        'system': {
            'uptime': get_uptime(),
            'memory': get_memory_usage(),
            'disk': get_disk_usage()
        },
        'temperature': temp_monitor.get_status()
    }
    return jsonify(status)

def get_uptime():
    """Gauna sistemos uptime"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            return str(datetime.timedelta(seconds=uptime_seconds))
    except Exception as e:
        app.logger.error(f"Klaida gaunant uptime: {e}")
        return "Nežinomas"

def get_memory_usage():
    """Gauna RAM atminties naudojimą"""
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = {}
            for line in f:
                if ':' in line:
                    key, value = line.split(':', 1)
                    meminfo[key.strip()] = value.strip()
            
            total = int(meminfo.get('MemTotal', '0').split()[0]) / 1024  # MB
            available = int(meminfo.get('MemAvailable', '0').split()[0]) / 1024  # MB
            used = total - available
            
            return {
                'total': f"{total:.1f} MB",
                'used': f"{used:.1f} MB",
                'available': f"{available:.1f} MB",
                'percent': f"{(used/total*100):.1f}%"
            }
    except Exception as e:
        app.logger.error(f"Klaida gaunant RAM naudojimą: {e}")
        return {'error': str(e)}

def get_disk_usage():
    """Gauna disko naudojimą"""
    try:
        # Bandome nuskaityti tiesiogiai iš /proc/mounts ir statvfs
        import os
        stat = os.statvfs('/')
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bfree * stat.f_frsize
        used = total - free
        
        # Konvertuojame į žmogui suprantamą formatą
        def human_readable_size(size):
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} PB"
        
        percent = used / total * 100
        
        return {
            'total': human_readable_size(total),
            'used': human_readable_size(used),
            'available': human_readable_size(free),
            'percent': f"{percent:.1f}%"
        }
    except Exception as e:
        app.logger.error(f"Klaida gaunant disko naudojimą: {e}")
        return {'error': str(e)}

@app.route('/voice_control', methods=['POST'])
def voice_control():
    """Valdo voice kliento būseną"""
    if not discord_available:
        return jsonify({"success": False, "message": "Discord modulis neįdiegtas"}), 400
        
    if not voice_client:
        return jsonify({"success": False, "message": "Discord voice klientas neinicializuotas"}), 400
    
    try:
        action = request.json.get('action')
        
        if action == 'mute':
            result = voice_client.toggle_mute()
            return jsonify(result)
        elif action == 'deafen':
            result = voice_client.toggle_deafen()
            return jsonify(result)
        else:
            return jsonify({"success": False, "message": "Neteisinga komanda"}), 400
            
    except Exception as e:
        app.logger.error(f"Klaida voice_control: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/voice_status', methods=['GET'])
def voice_status():
    """Grąžina voice kliento būseną"""
    if not discord_available:
        return jsonify({"success": False, "message": "Discord modulis neįdiegtas"}), 400
        
    if not voice_client:
        return jsonify({"success": False, "message": "Discord voice klientas neinicializuotas"}), 400
    
    try:
        status = voice_client.get_status()
        return jsonify({"success": True, "status": status})
            
    except Exception as e:
        app.logger.error(f"Klaida voice_status: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Registruojame shutdown funkciją
@app.teardown_appcontext
def shutdown_session(exception=None):
    pass  # Kol kas nieko

def cleanup_resources():
    # Sustabdome temperatūros stebėjimą
    if temp_monitor:
        temp_monitor.stop()
        app.logger.info("Temperatūros stebėjimas sustabdytas")
    
    # Sustabdome Discord voice klientą
    if discord_available and voice_client:
        try:
            voice_client.stop()
            app.logger.info("Discord voice klientas sustabdytas")
        except Exception as e:
            app.logger.error(f"Klaida stabdant Discord voice klientą: {e}")
    
    # Uždarome aiohttp klientų sesijas ir konektorius
    try:
        import asyncio
        import aiohttp
        
        # Ieškome neuždarytų konektorių ir sesijų
        for task in asyncio.all_tasks(loop=asyncio.get_event_loop()):
            if not task.done() and 'aiohttp' in str(task):
                task.cancel()
                app.logger.info(f"Nutraukta neužbaigta aiohttp užduotis: {task}")
                
        app.logger.info("Visi aiohttp resursai išvalyti")
    except Exception as e:
        app.logger.error(f"Klaida išvalant aiohttp resursus: {e}")

# Nustatome išėjimo procesą
import atexit
atexit.register(cleanup_resources)

# Prieš app paleidimą, startuojame temperatūros stebėjimą
def before_app_start():
    temp_monitor.start()
    app.logger.info("Temperatūros stebėjimas pradėtas")
    
    # Paleidžiame Discord voice klientą
    if discord_available and voice_client:
        voice_client.start()
        app.logger.info("Discord voice klientas paleistas")
        
        # Nustatome pradinę mikrofono ir garso būseną pagal konfigūraciją
        try:
            # Jei sukonfigūruota, kad mikrofonas turi būti įjungtas, bet dabar yra išjungtas
            if Config.DISCORD.get('MIC_ENABLED', False) != voice_client.muted:
                threading.Timer(5.0, lambda: voice_client.toggle_mute()).start()
                app.logger.info(f"Mikrofono būsena bus nustatyta į: {'įjungta' if Config.DISCORD.get('MIC_ENABLED', False) else 'išjungta'}")
            
            # Jei sukonfigūruota, kad garsas turi būti įjungtas, bet dabar yra išjungtas
            if Config.DISCORD.get('SOUND_ENABLED', False) != voice_client.deafened:
                threading.Timer(5.0, lambda: voice_client.toggle_deafen()).start()
                app.logger.info(f"Garso būsena bus nustatyta į: {'įjungta' if Config.DISCORD.get('SOUND_ENABLED', False) else 'išjungta'}")
        except Exception as e:
            app.logger.error(f"Klaida nustatant pradinę mikrofono ir garso būseną: {e}")

# Paleidžiame temperatūros stebėjimą ir inicializuojame Discord klientą
before_app_start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

