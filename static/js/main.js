// static/js/main.js

console.log("main.js loaded");

// Iš index.html paimame globalius kintamuosius
let currentBatch = window.PHOTO_BATCH || [];
let currentIndex = 0;
let currentAlbum = window.ALBUM_TITLE || "";
const PHOTO_DURATION = window.PHOTO_DURATION || 30;
const WEATHER_REFRESH_INTERVAL = window.WEATHER_REFRESH_INTERVAL || 3600;

let progressIntervalId = null;

/* ========================
   NUOTRAUKŲ RODYMO FUNKCIJOS
   ======================== */

function startProgressBar() {
  // Sustabdome ankstesnį intervalą, jei buvo
  if (progressIntervalId) {
    clearInterval(progressIntervalId);
  }

  let timePassed = 0;
  const progressEl = document.getElementById('photo-progress');
  if (progressEl) {
    progressEl.style.width = '66%';
  }

  progressIntervalId = setInterval(() => {
    timePassed++;
    const percentLeft = 66 - (timePassed / PHOTO_DURATION) * 100;
    if (progressEl) {
      progressEl.style.width = percentLeft + '%';
    }

    if (timePassed >= PHOTO_DURATION) {
      clearInterval(progressIntervalId);
      nextMedia();
    }
  }, 1000);
}

function nextMedia() {
  if (currentBatch && currentIndex < currentBatch.length - 1) {
    currentIndex++;
    showMedia(currentBatch[currentIndex]);
    startProgressBar();
  } else {
    updatePhotoBatch();
  }
}

function showMedia(m) {
  const display = document.getElementById('photo-display');
  if (!display) return;

  // Išvalome seną mediją
  display.innerHTML = '';
  
  // Log displayed media to server
  logMediaDisplay(m);

  if (m.mediaType === "video") {
    // Sukuriame video elementą
    let videoEl = document.createElement('video');
    videoEl.id = 'current-video';
    videoEl.src = m.baseUrl;
    videoEl.style.position = 'absolute';
    videoEl.style.left = '50%';
    videoEl.style.transform = 'translateX(-50%)';
    videoEl.style.objectFit = 'contain';
    videoEl.style.margin = 0;
    videoEl.style.maxWidth = '100%';
    videoEl.style.maxHeight = '100%';
    videoEl.style.bottom = '0';
    
    // Video atributai
    videoEl.controls = false; // Slėpti video kontroles
    videoEl.autoplay = true;
    videoEl.muted = !window.VIDEO_SOUND; // Pagal konfiguraciją
    videoEl.playsInline = true;
    
    // Kai video baigsis, keičiame į sekančią mediją
    videoEl.onended = function() {
      clearInterval(progressIntervalId); // Sustabdome progreso juostą
      nextMedia();
    };
    
    // Jei video ilgesnis nei nustatyta, nustatome laikmatį
    videoEl.onloadedmetadata = function() {
      let duration = videoEl.duration;
      if (duration > window.VIDEO_DURATION) {
        setTimeout(() => {
          clearInterval(progressIntervalId);
          nextMedia();
        }, window.VIDEO_DURATION * 1000);
      }
    };
    
    display.appendChild(videoEl);
  } else {
    // Sukuriame naują <img> elementą nuotraukai
    let imgEl = document.createElement('img');
    imgEl.id = 'current-photo';
    imgEl.src = m.baseUrl + "=w1200-h800"; // reikiamo dydžio parametrai
    imgEl.style.position = 'absolute';
    imgEl.style.left = '50%';
    imgEl.style.transform = 'translateX(-50%)';
    imgEl.style.objectFit = 'contain';
    imgEl.style.margin = 0;

    // Kai paveikslas užsikraus, nustatome, ar plotis, ar aukštis turi tilpti
    imgEl.onload = function() {
      let w = imgEl.naturalWidth;
      let h = imgEl.naturalHeight;
      if (h > w) {
        // Vertikali nuotrauka
        imgEl.style.height = '100%';
        imgEl.style.width = 'auto';
        imgEl.style.top = '0';
        imgEl.style.bottom = '0';
      } else {
        // Horizontali
        imgEl.style.width = '100%';
        imgEl.style.height = 'auto';
        imgEl.style.bottom = '0';
        imgEl.style.top = 'auto';
      }
    };

    display.appendChild(imgEl);
  }

  // Parodome informacijos overlay (albumo pavadinimas, data, kiek liko nuotraukų)
  let remain = currentBatch.length - (currentIndex + 1);
  const overlay = document.getElementById('photo-overlay-content');
  if (overlay) {
    let text = currentAlbum + "<br>" 
             + m.photo_time.replace("T", " ").replace("Z", "") 
             + " (liko #" + remain + ")"
             + (m.mediaType === "video" ? " 📹" : "");
    overlay.innerHTML = text;
  }
  
  // Paleiskime progreso juostą tik nuotraukoms (video turi savo progresą)
  if (m.mediaType !== "video") {
    startProgressBar();
  }
}

// New function to log displayed media to server
function logMediaDisplay(mediaItem) {
  // Don't log error items
  if (mediaItem.mediaType === "error" || !mediaItem.filename) return;
  
  fetch('/log_media_display', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      album: currentAlbum,
      filename: mediaItem.filename,
      mediaType: mediaItem.mediaType,
      timestamp: new Date().toISOString()
    })
  })
  .catch(error => console.error('Error logging media display:', error));
}

function updatePhotoBatch() {
  fetch('/newphoto')
    .then(r => r.json())
    .then(d => {
      if (d.error) {
        console.error("Error:", d.error);
        return;
      }
      currentBatch = d.photos;
      currentAlbum = d.album_title;
      currentIndex = 0;
      if (currentBatch.length > 0) {
        showMedia(currentBatch[0]);
        startProgressBar();
      }
    })
    .catch(e => console.error('Error fetching new photo batch:', e));
}

/* ========================
   ORŲ ATNAUJINIMAS
   ======================== */
function updateWeather() {
  fetch('/newweather')
    .then(r => r.json())
    .then(d => {
      if (d.error) {
        console.error("Weather refresh error:", d.error);
        return;
      }
      let overlay = document.getElementById('weather-overlay');
      if (!overlay) return;

      let html = "";
      d.daily.forEach(day => {
        let dt = new Date(day.dt * 1000);
        let weekday = dt.toLocaleString('en-US', { weekday: 'short' });
        let code = day.weather[0].description;
        let tempMin = Math.round(day.main.temp_min);
        let tempMax = Math.round(day.main.temp_max);

        // Sudedame vieno dienos "stulpelio" HTML
        let iconUrl = `/static/meteo-icons/day/${code}.png`;
        html += `
          <div style="text-align: center; border-right: 1px solid rgba(255,255,255,0.3); padding: 0 10px;">
            <div style="font-size: 1em; font-weight: bold; margin-bottom: 0px;">${weekday}</div>
            <div><img src="${iconUrl}" alt="${code}" style="width: 60px; height: 60px;" /></div>
            <div style="font-size: 1.2em;">${tempMin}° / ${tempMax}°</div>
          </div>
        `;
      });
      overlay.innerHTML = html;
    })
    .catch(e => console.error("Error refreshing weather:", e));
}

/* ========================
   DISCORD ŽINUČIŲ ATNAUJINIMAS
   ======================== */
function updateDiscordMessages() {
  fetch('/discordmessages')
    .then(r => r.json())
    .then(d => {
      let overlay = document.getElementById('discord-overlay');
      if (!overlay) return;

      let html = "";
      const sixHoursAgo = Date.now() - 6 * 3600 * 1000;
      // Imame tik paskutines 6 val. žinutes
      const recentMessages = d.filter(msg => new Date(msg.timestamp) >= sixHoursAgo);

      if (recentMessages.length > 0) {
        // Imame tik 10 naujausių
        const lastMessages = recentMessages.slice(0, 10).reverse();
        lastMessages.forEach(msg => {
          const msgTime = new Date(msg.timestamp);
          // +2 val. (paprasta korekcija, neatsižvelgiant į DST)
          msgTime.setHours(msgTime.getHours() + 2);

          const hh = String(msgTime.getHours()).padStart(2, '0');
          const mm = String(msgTime.getMinutes()).padStart(2, '0');

          const shortUsername = msg.author.username.substring(0, 2);
          const usernameColor = msg.color;

          html += `
            <div style="margin-bottom: 10px; font-size: 1em;">
              ${hh}:${mm}
              <strong style="background-color: ${usernameColor};"> ${shortUsername}: </strong>
              ${msg.content}
            </div>
          `;
        });
      } else {
        html = "<div>No new messages in channel</div>";
      }
      overlay.innerHTML = html;
    })
    .catch(e => {
      console.error("Error fetching Discord messages:", e);
      let overlay = document.getElementById('discord-overlay');
      if (overlay) overlay.innerHTML = "Error loading messages.";
    });
}

/* ========================
   KALENDORIAUS ATNAUJINIMAS
   ======================== */
function updateCalendarEvents() {
  fetch('/calendarevents')
    .then(r => r.text())
    .then(html => {
      let container = document.getElementById('calendar-container');
      if (container) {
        container.innerHTML = html;
      }
    })
    .catch(e => console.error('Error fetching calendar events:', e));
}

/* ========================
   ŠIANDIENOS ĮVYKIŲ FRAGMENTAS
   ======================== */
function updateTodayEvents() {
  fetch('/todayevents')
    .then(r => r.text())
    .then(html => {
      let el = document.getElementById('today-events');
      if (el) {
        el.innerHTML = html;
      }
    })
    .catch(e => console.error("Error updating today's events:", e));
}

/* ========================
   SENSORIŲ (TEMPERATURE/HUMIDITY) ATNAUJINIMAS
   ======================== */
function updateSensorOverlay() {
  // Naudojame pilną URL, jei reikia (arba apibrėžkime base URL kintamąjį) 
  // Naudojame window.location.origin kad veiktų su bet kokiu hostu
  fetch(window.location.origin + '/newsensors')
    .then(r => r.json())
    .then(d => {
      let sensorDiv = document.getElementById('sensor-data');
      if (!sensorDiv) return;

      if (d.error) {
        // Show error but still display CPU temp if available
        let errorText = "Sensors error: " + d.error;
        if (d.cpu_temp) {
          errorText += ` | CPU: ${d.cpu_temp.toFixed(1)}°C`;
        }
        sensorDiv.innerText = errorText;
      } else {
        // Show both environmental sensor and CPU temperature
        let sensorText = "";
        
        // Add environmental temperature and humidity if available
        if (d.temperature !== undefined && d.humidity !== undefined) {
          sensorText = `${d.temperature}°C - ${d.humidity}%`;
        }
        
        // Add CPU temperature if available
        if (d.cpu_temp !== undefined) {
          if (sensorText) {
            sensorText += ` | CPU: ${d.cpu_temp.toFixed(1)}°C`;
          } else {
            sensorText = `CPU: ${d.cpu_temp.toFixed(1)}°C`;
          }
        }
        
        // If we have no data at all
        if (!sensorText) {
          sensorText = "No sensor data available";
        }
        
        console.log("Sensor data updated:", sensorText); // Debug log
        sensorDiv.innerText = sensorText;
      }
    })
    .catch(e => {
      console.error("Error fetching sensor data:", e);
      let sensorDiv = document.getElementById('sensor-data');
      if (sensorDiv) sensorDiv.innerText = "Sensor error";
    });
}

/* ========================
   LAIKRODIS / DATA
   ======================== */
function updateSchedule() {
  let now = new Date();
  let hh = String(now.getHours()).padStart(2, '0');
  let mm = String(now.getMinutes()).padStart(2, '0');
  let clockEl = document.getElementById('big-clock');
  if (clockEl) {
    clockEl.innerText = hh + ":" + mm;
  }

  let yyyy = now.getFullYear();
  let M = String(now.getMonth() + 1).padStart(2, '0');
  let d = String(now.getDate()).padStart(2, '0');
  let dateEl = document.getElementById('date');
  if (dateEl) {
    dateEl.innerText = yyyy + "." + M + "." + d;
  }
}

/* ========================
   PRADINIS PUSLAPIO UŽKROVIMAS
   ======================== */
document.addEventListener('DOMContentLoaded', () => {
  // 1) Nuotraukos (jei jau turime batch iš serverio)
  if (currentBatch.length > 0) {
    showMedia(currentBatch[0]);
    startProgressBar();
  }

  // 2) Orų atnaujinimas
  updateWeather();
  setInterval(updateWeather, WEATHER_REFRESH_INTERVAL * 1000);

  // 3) Discord žinutės
  updateDiscordMessages();
  setInterval(updateDiscordMessages, 60000);

  // 4) Kalendoriaus fragmentas
  setInterval(updateCalendarEvents, 60000);

  // 5) Šiandienos įvykių fragmentas
  setInterval(updateTodayEvents, 60000);

  // 6) Sensorių overlay
  updateSensorOverlay();
  setInterval(updateSensorOverlay, 60000);

  // 7) Laikrodis ir data
  updateSchedule();
  setInterval(updateSchedule, 1000);
});

