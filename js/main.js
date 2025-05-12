// static/js/main.js

console.log("main.js loaded");

// Iš index.html paimame globalius kintamuosius
let currentBatch = window.PHOTO_BATCH || [];
let currentIndex = 0;
let currentAlbum = window.ALBUM_TITLE || "";
const PHOTO_DURATION = window.PHOTO_DURATION || 30;
const VIDEO_DURATION = window.VIDEO_DURATION || 60;
const MEDIA_TYPES = window.MEDIA_TYPES || "all";
const VIDEO_SOUND = window.VIDEO_SOUND !== undefined ? window.VIDEO_SOUND : false;
const WEATHER_REFRESH_INTERVAL = window.WEATHER_REFRESH_INTERVAL || 3600;
const MAX_VIDEO_DURATION = window.VIDEO_DURATION || 60;

let progressIntervalId = null;

let temperatureMonitoring = {
  isActive: window.TEMP_CONFIG && window.TEMP_CONFIG.monitoring,
  lastTemp: 0,
  overrideActive: false,
  checkInterval: (window.TEMP_CONFIG && window.TEMP_CONFIG.checkInterval) || 60,
  warningShown: false
};

/* ========================
   NUOTRAUKŲ RODYMO FUNKCIJOS
   ======================== */

function startProgressBar() {
  // Sustabdome ankstesnį intervalą, jei buvo
  if (progressIntervalId) {
    clearInterval(progressIntervalId);
  }

  // Patikriname, ar dabartinis media elementas nėra video
  const currentMedia = currentBatch[currentIndex];
  if (currentMedia && currentMedia.mediaType === "video") {
    // Jei tai video, nereikia progreso juostos, nes video turi savo atkūrimo laiką
    return;
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
  // Pirmiausia sustabdome bet kokius laikmačius
  if (progressIntervalId) {
    clearInterval(progressIntervalId);
    progressIntervalId = null;
  }
  
  // Taip pat turime sustabdyti bet kokius grojančius video
  const currentVideo = document.getElementById('current-video');
  if (currentVideo) {
    currentVideo.pause();
  }
  
  // Pereiti prie kitos medijos
  if (currentBatch && currentIndex < currentBatch.length - 1) {
    currentIndex++;
    showMedia(currentBatch[currentIndex]);
  } else {
    updatePhotoBatch();
  }
}

function updatePhotoInfo(m) {
  // Parodome informacijos overlay (albumo pavadinimas, data, kiek liko nuotraukų)
  let remain = currentBatch.length - (currentIndex + 1);
  const overlay = document.getElementById('photo-overlay-content');
  if (overlay) {
    let mediaTypeIcon = m.mediaType === "video" ? "🎬 " : "";
    let text = mediaTypeIcon + currentAlbum + "<br>" 
             + (m.photo_time ? m.photo_time.replace("T", " ").replace("Z", "") : "") 
             + " #" + remain;
    overlay.innerHTML = text;
  }
}

function showMedia(m) {
  const display = document.getElementById('photo-display');
  if (!display) return;

  // Tikriname, ar objekte yra klaidos pranešimas
  if (m.error || m.mediaType === "error") {
    // Rodome klaidos pranešimą
    display.innerHTML = '';
    
    let errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.style.position = 'absolute';
    errorDiv.style.top = '50%';
    errorDiv.style.left = '50%';
    errorDiv.style.transform = 'translate(-50%, -50%)';
    errorDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
    errorDiv.style.color = 'white';
    errorDiv.style.padding = '20px';
    errorDiv.style.borderRadius = '10px';
    errorDiv.style.fontSize = '24px';
    errorDiv.style.textAlign = 'center';
    errorDiv.style.maxWidth = '80%';
    
    errorDiv.innerHTML = `
      <h2 style="color: #ff5555;">Klaida gaunant nuotraukas</h2>
      <p>${m.error || 'Nepavyko įkelti nuotraukų'}</p>
      <p style="font-size: 18px; margin-top: 20px;">Bandysime dar kartą po 5 minučių...</p>
    `;
    
    display.appendChild(errorDiv);
    
    // Po 5 minučių bandome iš naujo
    setTimeout(() => {
      updatePhotoBatch();
    }, 5 * 60 * 1000);
    
    return;
  }

  // Patikriname, ar galima rodyti šio tipo mediją
  const allowedMediaTypes = MEDIA_TYPES.toLowerCase();
  if (allowedMediaTypes !== "all" && m.mediaType !== allowedMediaTypes) {
    console.warn(`Skipping media of type ${m.mediaType} as only ${allowedMediaTypes} is allowed`);
    nextMedia(); // Pereiti prie kitos medijos
    return;
  }

  // Išvalome seną nuotrauką/video
  display.innerHTML = '';

  if (m.mediaType === "video") {
    // Jei tai video, sukuriame video elementą
    let videoEl = document.createElement('video');
    videoEl.id = 'current-video';
    
    // Naudojame baseUrl su parametrais video atkūrimui
    // dv=1 - nurodo, kad norime video formato
    // Papildomai galime pridėti dydžio nustatymus: w1280-h720
    videoEl.src = m.baseUrl + "=dv-w1280-h720";
    
    // Stiliaus nustatymai video elementui
    videoEl.style.position = 'absolute';
    videoEl.style.left = '50%';
    videoEl.style.transform = 'translateX(-50%)';
    videoEl.style.maxWidth = '100%';
    videoEl.style.maxHeight = '100%';
    videoEl.style.objectFit = 'contain';
    videoEl.style.margin = 0;
    
    // Video nustatymai
    videoEl.controls = false; // Nerodyti standartinių kontrolių
    videoEl.autoplay = true;  // Automatiškai pradėti atkūrimą
    videoEl.muted = !VIDEO_SOUND;    // Garso nustatymas pagal konfigūraciją
    videoEl.playsInline = true; // Atkurti tiesiai elemente, be pilno ekrano
    videoEl.loop = false;     // Neatkartoti video
    
    // Nustatome, kad po 60 sekundžių arba kai video baigiasi, pereinama prie kitos medijos
    let videoTimeout = null;
    
    videoEl.onloadedmetadata = function() {
      console.log("Video loaded, duration:", videoEl.duration);
      // Jei video ilgesnis nei MAX_VIDEO_DURATION, nustatome laikmatį
      if (videoEl.duration > MAX_VIDEO_DURATION) {
        videoTimeout = setTimeout(() => {
          console.log("Video timeout reached, moving to next media");
          nextMedia();
        }, MAX_VIDEO_DURATION * 1000);
      }
    };
    
    videoEl.onended = function() {
      console.log("Video ended naturally");
      // Jei video baigėsi anksčiau nei suveikė laikmatis, išvalome laikmatį
      if (videoTimeout) {
        clearTimeout(videoTimeout);
        videoTimeout = null;
      }
      nextMedia();
    };
    
    videoEl.onerror = function() {
      console.error("Error playing video:", videoEl.error);
      // Jei įvyko klaida atkuriant video, pereiti prie kitos medijos po trumpo atidėjimo
      setTimeout(() => {
        nextMedia();
      }, 2000);
    };
    
    // Jei po 5 sekundžių video nepradeda groti, pereiti prie kitos medijos
    setTimeout(() => {
      if (videoEl.readyState === 0 || videoEl.error) {
        console.error("Video failed to load after 5 seconds, skipping to next media");
        if (videoTimeout) {
          clearTimeout(videoTimeout);
          videoTimeout = null;
        }
        nextMedia();
      }
    }, 5000);
    
    display.appendChild(videoEl);
    
    // Pridedame video atkūrimo indikatoriaus ikoną
    let playIndicator = document.createElement('div');
    playIndicator.className = 'video-play-indicator';
    playIndicator.innerHTML = '▶️';
    playIndicator.style.position = 'absolute';
    playIndicator.style.top = '50%';
    playIndicator.style.left = '50%';
    playIndicator.style.transform = 'translate(-50%, -50%)';
    playIndicator.style.fontSize = '48px';
    playIndicator.style.opacity = '0.8';
    playIndicator.style.zIndex = '10';
    playIndicator.style.pointerEvents = 'none';
    display.appendChild(playIndicator);
    
    // Po 2 sekundžių paslepiame play indikatorių
    setTimeout(() => {
      playIndicator.style.opacity = '0';
      playIndicator.style.transition = 'opacity 0.5s ease-out';
    }, 2000);
  } else {
    // Tai nuotrauka, elgiamės kaip ir anksčiau
    let imgEl = document.createElement('img');
    imgEl.id = 'current-photo';
    imgEl.src = m.baseUrl + "=w1200-h800"; // reikiamo dydžio parametrai
    imgEl.style.position = 'absolute';
    imgEl.style.left = '50%';
    imgEl.style.transform = 'translateX(-50%)';
    imgEl.style.objectFit = 'contain';
    imgEl.style.margin = 0;

    // Nustatome, kas nutiks, kai nuotrauka bus užkrauta
    imgEl.onload = function() {
      console.log("Image loaded successfully");
    };

    imgEl.onerror = function() {
      console.error("Error loading image:", m.baseUrl);
      // Jei nepavyko užkrauti nuotraukos, pereiti prie kitos po trumpo atidėjimo
      setTimeout(() => {
        nextMedia();
      }, 2000);
    };

    display.appendChild(imgEl);
  }
  
  // Atnaujinama informacija apie nuotrauką
  updatePhotoInfo(m);
  
  // Jei tai video, sustabdome progreso juostą, nes video turi savo atkūrimo laiką
  if (m.mediaType === "video") {
    if (progressIntervalId) {
      clearInterval(progressIntervalId);
      progressIntervalId = null;
    }
    const progressEl = document.getElementById('photo-progress');
    if (progressEl) {
      progressEl.style.width = '66%';
    }
  } else {
    // Jei tai nuotrauka, pradedame progreso juostą
    startProgressBar();
  }
}

function updatePhotoBatch() {
  console.log("Updating photo batch");
  fetch('/newphoto')
    .then(response => response.json())
    .then(data => {
      console.log("Photo batch response:", data);

      // Patikriname, ar gavome klaidos pranešimą
      if (data.error) {
        console.error("Error getting photos:", data.error);
        // Jei turime 'photos' masyvą su klaidos objektais, juos naudojame
        if (data.photos && data.photos.length > 0) {
          currentBatch = data.photos;
          currentIndex = 0;
          currentAlbum = data.album_title || "Error";
          showMedia(currentBatch[currentIndex]);
        } else {
          // Sukuriame klaidos objektą, jei nėra 'photos' masyvo
          currentBatch = [{ 
            error: data.error, 
            mediaType: "error" 
          }];
          currentIndex = 0;
          currentAlbum = "Error";
          showMedia(currentBatch[currentIndex]);
        }
        return;
      }

      // Jei viskas gerai, naudojame gautus duomenis
      if (data.photos && data.photos.length > 0) {
        currentBatch = data.photos;
        currentIndex = 0;
        currentAlbum = data.album_title || "";
        showMedia(currentBatch[currentIndex]);
      } else {
        console.error("No photos in response");
        // Sukuriame klaidos objektą
        currentBatch = [{ 
          error: "No photos available", 
          mediaType: "error" 
        }];
        currentIndex = 0;
        currentAlbum = "No Photos";
        showMedia(currentBatch[currentIndex]);
      }
    })
    .catch(error => {
      console.error("Error fetching photo batch:", error);
      // Sukuriame klaidos objektą, jei įvyko tinklo klaida
      currentBatch = [{ 
        error: "Network error: " + error.message, 
        mediaType: "error" 
      }];
      currentIndex = 0;
      currentAlbum = "Error";
      showMedia(currentBatch[currentIndex]);
    });
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
            <div style="font-size: 1.2em;">${tempMin}°|${tempMax}°</div>
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
      
      // Naudojame vidinį scrollable div elementą
      let contentDiv = overlay.querySelector('div > div');
      if (!contentDiv) {
        // Jei nėra vidinio div, sukuriame jį
        let scrollableDiv = document.createElement('div');
        scrollableDiv.style.height = '100%';
        scrollableDiv.style.overflowY = 'auto';
        scrollableDiv.style.scrollbarWidth = 'none';
        scrollableDiv.style.msOverflowStyle = 'none';
        
        contentDiv = document.createElement('div');
        contentDiv.style.paddingRight = '15px';
        
        scrollableDiv.appendChild(contentDiv);
        overlay.innerHTML = '';
        overlay.appendChild(scrollableDiv);
      }

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

          let messageContent = msg.content;
          let attachmentHtml = '';
          
          // Tikriname, ar yra attachments (pridėti failai)
          if (msg.attachments && msg.attachments.length > 0) {
            msg.attachments.forEach(attachment => {
              // Jei pridėtas failas yra paveikslėlis, rodome jį
              if (attachment.content_type && attachment.content_type.startsWith('image/')) {
                attachmentHtml += `
                  <div class="discord-image-container">
                    <img src="${attachment.url}" alt="Attachment" style="display: block; margin-left: 0; width: auto; height: auto;" />
                  </div>
                `;
              }
            });
          }
          
          // Tikriname, ar yra embeds (įterpti elementai, pvz. nuorodos su paveikslėliais)
          if (msg.embeds && msg.embeds.length > 0) {
            msg.embeds.forEach(embed => {
              // Jei įterptame elemente yra paveikslėlis, rodome jį
              if (embed.image && embed.image.url) {
                attachmentHtml += `
                  <div class="discord-image-container">
                    <img src="${embed.image.url}" alt="Embed image" style="display: block; margin-left: 0; width: auto; height: auto;" />
                  </div>
                `;
              } else if (embed.thumbnail && embed.thumbnail.url) {
                attachmentHtml += `
                  <div class="discord-image-container">
                    <img src="${embed.thumbnail.url}" alt="Embed thumbnail" style="display: block; margin-left: 0; width: auto; height: auto;" />
                  </div>
                `;
              }
            });
          }

          html += `
            <div style="margin-bottom: 20px; font-size: 1em;">
              ${hh}:${mm}
              <strong style="background-color: ${usernameColor};"> ${shortUsername}: </strong>
              ${messageContent}
              ${attachmentHtml}
            </div>
          `;
        });
      } else {
        html = "<div>No new messages in channel</div>";
      }
      contentDiv.innerHTML = html;
      
      // Automatiškai scrolliname į apačią, kad matytųsi naujausios žinutės
      let scrollableDiv = overlay.querySelector('div');
      if (scrollableDiv) {
        scrollableDiv.scrollTop = scrollableDiv.scrollHeight;
      }
    })
    .catch(e => {
      console.error("Error fetching Discord messages:", e);
      let overlay = document.getElementById('discord-overlay');
      if (overlay) {
        let contentDiv = overlay.querySelector('div > div') || overlay;
        contentDiv.innerHTML = "Error loading messages.";
      }
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
  fetch('/newsensors')
    .then(r => r.json())
    .then(d => {
      let sensorDiv = document.getElementById('sensor-data');
      if (!sensorDiv) return;

      if (d.error && !d.cpu_temp) {
        sensorDiv.innerText = "Sensors error: " + d.error;
      } else {
        // Suformuojame sensoriaus tekstą
        let sensorText = '';
        
        // Pridedame oro temperatūrą ir drėgmę kompaktiškesniu formatu
        if (d.temperature !== undefined && d.humidity !== undefined) {
          sensorText += `${d.temperature}° | ${d.humidity}% `;
        }
        
        // Pridedame CPU temperatūrą, jei yra
        if (d.cpu_temp !== undefined && d.cpu_temp > 0) {
          // CPU temperatūros spalva priklauso nuo jos aukščio
          let cpuTemp = d.cpu_temp.toFixed(1);
          let cpuClass = 'temp-normal'; // Dabar visada naudosim spalvą
          
          if (d.cpu_temp >= (window.TEMP_CONFIG?.warning || 65)) {
            cpuClass = 'temp-warning';
          } else if (d.cpu_temp >= (window.TEMP_CONFIG?.recovery || 60)) {
            cpuClass = 'temp-attention';
          } 
          
          sensorText += `| <span class="${cpuClass}">${cpuTemp}°</span>`;
        }
        
        // Jei nėra duomenų, rodome klaidos žinutę
        if (!sensorText) {
          sensorText = "No sensor data";
        }
        
        sensorDiv.innerHTML = sensorText;
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
  
  // Pradedame stebėti temperatūrą
  if (temperatureMonitoring.isActive) {
    monitorSystemStatus();
  }
});

// Periodiškai tikriname temperatūrą
function monitorSystemStatus() {
  if (!temperatureMonitoring.isActive) {
    return;
  }
  
  fetch('/systemstatus')
    .then(r => r.json())
    .then(status => {
      const tempStatus = status.temperature;
      temperatureMonitoring.lastTemp = tempStatus.last_temp;
      temperatureMonitoring.overrideActive = tempStatus.override_active;
      
      // Rodome įspėjimo pranešimą, jei temperatūra aukšta ir dar neparodyta
      if (temperatureMonitoring.lastTemp >= window.TEMP_CONFIG.warning && !temperatureMonitoring.warningShown) {
        const display = document.getElementById('photo-display');
        if (display) {
          const warningDiv = document.createElement('div');
          warningDiv.id = 'temp-warning';
          warningDiv.style.cssText = `
            position: absolute; 
            top: 10px; 
            right: 10px; 
            background-color: rgba(255, 0, 0, 0.7); 
            color: white; 
            padding: 10px; 
            border-radius: 5px; 
            z-index: 1000;
            font-size: 14px;
          `;
          warningDiv.innerHTML = `
            <h3>Aukšta CPU temperatūra: ${temperatureMonitoring.lastTemp.toFixed(1)}°C</h3>
            <p>Sistema perjungta į foto režimą, kol temperatūra normalizuosis.</p>
          `;
          display.appendChild(warningDiv);
          temperatureMonitoring.warningShown = true;
          
          // Po 10 sekundžių paslepiame įspėjimą
          setTimeout(() => {
            const warning = document.getElementById('temp-warning');
            if (warning) {
              warning.style.opacity = '0';
              warning.style.transition = 'opacity 1s';
              setTimeout(() => {
                if (warning && warning.parentNode) {
                  warning.parentNode.removeChild(warning);
                }
              }, 1000);
            }
          }, 10000);
        }
      } else if (temperatureMonitoring.lastTemp < window.TEMP_CONFIG.recovery) {
        // Resetiname įspėjimą, jei temperatūra nukrito
        temperatureMonitoring.warningShown = false;
      }
      
      // Priverstinai atnaujiname sensoriaus duomenis, kad iškart atsinaujintų CPU temperatūra
      updateSensorOverlay();
    })
    .catch(e => {
      console.error('Klaida tikrinant sistemos būseną:', e);
    })
    .finally(() => {
      // Nustato kitą tikrinimą
      setTimeout(monitorSystemStatus, temperatureMonitoring.checkInterval * 1000);
    });
}

/* ========================
   VOICE STATUS FUNKCIJOS
   ======================== */

function updateVoiceStatus() {
  fetch('/voice_status')
    .then(response => response.json())
    .then(status => {
      const overlay = document.getElementById('voice-overlay');
      if (!overlay) return;

      // Rodyti overlay tik jei yra prisijungęs prie voice kanalo
      if (status.connected) {
        overlay.style.display = 'block';
      } else {
        overlay.style.display = 'none';
        return;
      }

      // Atnaujinti mikrofono būseną
      const micIcon = overlay.querySelector('.mic-status');
      if (micIcon) {
        const micText = micIcon.querySelector('.status-text');
        micIcon.className = `voice-icon mic-status ${status.muted ? 'inactive' : 'active'}`;
        if (micText) {
          micText.textContent = status.muted ? 'MIC OFF' : 'MIC ON';
        }
      }

      // Atnaujinti garso būseną
      const soundIcon = overlay.querySelector('.sound-status');
      if (soundIcon) {
        const soundText = soundIcon.querySelector('.status-text');
        soundIcon.className = `voice-icon sound-status ${status.deafened ? 'inactive' : 'active'}`;
        if (soundText) {
          soundText.textContent = status.deafened ? 'SOUND OFF' : 'SOUND ON';
        }
      }
    })
    .catch(error => {
      console.error('Klaida gaunant voice statusą:', error);
    });
}

function toggleMic() {
  fetch('/voice_control', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ action: 'mute' })
  })
  .then(response => response.json())
  .then(result => {
    if (result.success) {
      console.log(`Mikrofono būsena pakeista į ${result.muted ? 'OFF' : 'ON'}`);
      updateVoiceStatus(); // Atnaujiname UI
    } else {
      console.error('Klaida keičiant mikrofono būseną:', result.message);
    }
  })
  .catch(error => {
    console.error('Klaida siunčiant užklausą:', error);
  });
}

function toggleSound() {
  fetch('/voice_control', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ action: 'deafen' })
  })
  .then(response => response.json())
  .then(result => {
    if (result.success) {
      console.log(`Garso būsena pakeista į ${result.deafened ? 'OFF' : 'ON'}`);
      updateVoiceStatus(); // Atnaujiname UI
    } else {
      console.error('Klaida keičiant garso būseną:', result.message);
    }
  })
  .catch(error => {
    console.error('Klaida siunčiant užklausą:', error);
  });
}

// Funkcija, kuri periodiškai atnaujina voice statusą
function startVoiceMonitoring() {
  // Iš karto atnaujiname statusą
  updateVoiceStatus();
  
  // Tada nustatome periodinį atnaujinimą kas 5 sekundes
  setInterval(updateVoiceStatus, 5000);
}

// Pridedame voice monitoringo startą prie window.onload
document.addEventListener('DOMContentLoaded', function() {
    startVoiceMonitoring();
});