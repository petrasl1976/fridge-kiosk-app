import os
import json
import time
import datetime
import random
import requests
from collections import defaultdict

from flask import Flask, render_template, redirect, url_for, session, request, jsonify
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

import broadlink
from config import Config

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
CACHE_EXPIRATION = 7 * 24 * 3600  # 7 dienos

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
    albums = get_all_albums(photos_service)
    if not albums:
        return None, None

    album = random.choice(albums)
    album_title = album.get('title', 'Unknown Album')
    items = get_all_media_items(photos_service, album['id'])
    if not items:
        return None, None

    # Filtruojame tik tuos, kurie turi creationTime
    items = [i for i in items if i.get('mediaMetadata', {}).get('creationTime')]
    if not items:
        return None, None

    # Rūšiuojame pagal creationTime
    items.sort(key=lambda x: x['mediaMetadata']['creationTime'])
    total = len(items)
    start_index = random.randint(0, total - 1)
    batch = []
    for i in range(Config.PHOTO_BATCH_COUNT):
        idx = (start_index + i) % total
        meta = items[idx].get('mediaMetadata', {})
        batch.append({
            'baseUrl': items[idx].get('baseUrl', ''),
            'photo_time': meta.get('creationTime', ''),
            'filename': items[idx].get('filename', 'Unknown')
        })

    return batch, album_title

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
        devices = broadlink.discover(timeout=Config.BROADLINK["DISCOVER_TIMEOUT"])
        for d in devices:
            if d.type.startswith(Config.BROADLINK["TARGET_TYPE_PREFIX"]):
                d.auth()
                return d.check_sensors()
    except Exception as e:
        return {"error": str(e)}
    return {"error": "Device not found"}

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
    url = f"{Config.DISCORD_API_BASE_URL}/channels/{Config.DISCORD['CHANNEL_ID']}/messages?limit={Config.DISCORD['MESSAGE_COUNT']}"
    headers = {"Authorization": f"Bot {Config.DISCORD['BOT_TOKEN']}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        messages = r.json()
        for m in messages:
            username = m['author']['username']
            m['color'] = get_username_color(username)
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

    photos_service = googleapiclient.discovery.build(
        'photoslibrary', 'v1', credentials=creds,
        discoveryServiceUrl='https://photoslibrary.googleapis.com/$discovery/rest?version=v1'
    )

    photo_batch, album_title = get_random_photo_batch(photos_service)
    if not photo_batch:
        photo_batch = []

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
        weather_refresh_interval=Config.WEATHER.get("REFRESH_INTERVAL", 3600),
        summary_max_length=Config.EVENT_SUMMARY_MAX_LENGTH,
        show_holidays=Config.SHOW_HOLIDAYS,
        holidays=Config.HOLIDAYS
    )

@app.route('/newphoto')
def newphoto():
    creds_data = session.get('credentials')
    if not creds_data:
        return jsonify({"error": "No credentials in session"}), 403

    creds = google.oauth2.credentials.Credentials(**creds_data)
    photos_service = googleapiclient.discovery.build(
        'photoslibrary', 'v1', credentials=creds,
        discoveryServiceUrl='https://photoslibrary.googleapis.com/$discovery/rest?version=v1'
    )

    photo_batch, album_title = get_random_photo_batch(photos_service)
    if not photo_batch:
        return jsonify({"error": "No photos found"}), 404

    return jsonify({"photos": photo_batch, "album_title": album_title})

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

