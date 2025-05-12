#!/bin/bash

echo "Šaldytuvo ekrano diegimo skriptas"
echo "Reikalavimai:"
echo "- Raspberry Pi OS Lite"
echo "- Prijungtas vertikalus ekranas"
echo "- Interneto ryšys"
echo "----------------------------------------"
echo

# Patikrinkime ar paleista su sudo
if [ "$(id -u)" -ne 0 ]; then 
    echo "Paleiskite su sudo"
    exit 1
fi

# Parametrų apdorojimas
CLEAR_APP=0
while getopts "c" opt; do
    case $opt in
        c)
            CLEAR_APP=1
            ;;
        \?)
            echo "Nežinomas parametras: -$OPTARG"
            echo "Galimi parametrai:"
            echo "  -c    Išvalyti aplikacijos direktoriją ir perdiegti iš naujo"
            exit 1
            ;;
    esac
done

# Funkcija Python virtualios aplinkos sukūrimui ir modulių įdiegimui
setup_python_env() {
    local app_dir=$1
    
    echo "Kuriu virtualią aplinką ir nustatau teises..."
    cd "$app_dir"
    python3 -m venv venv
    
    # Nustatome teises virtualiai aplinkai
    chown -R kiosk:kiosk "$app_dir/venv"
    chmod -R 755 "$app_dir/venv/bin"
    # Užtikriname, kad visi failai bin kataloge būtų vykdomi
    chmod +x "$app_dir/venv/bin/"*
    
    echo "Įdiegiu reikalingus Python modulius..."
    sudo -u kiosk "$app_dir/venv/bin/pip" install --no-cache-dir flask \
        google-auth-oauthlib \
        google-auth-httplib2 \
        google-api-python-client \
        requests \
        broadlink \
        pytz \
        tzlocal \
        python-dotenv \
        discord \
        "discord.py[voice]" \
        PyNaCl
}

echo "Tikrinu ir diegiu reikalingus paketus..."
PACKAGES="chromium-browser cage dbus-x11 seatd python3-venv python3-pip wlr-randr"
NEW_PACKAGES=""

for pkg in $PACKAGES; do
    if ! dpkg -l | grep -q "^ii  $pkg "; then
        NEW_PACKAGES="$NEW_PACKAGES $pkg"
    fi
done

if [ ! -z "$NEW_PACKAGES" ]; then
    echo "Diegiu trūkstamus paketus:$NEW_PACKAGES"
    apt update
    apt install -y $NEW_PACKAGES
else
    echo "Visi reikalingi paketai jau įdiegti"
fi

echo "Kuriu seat grupę ir kiosk vartotoją..."
groupadd -f seat
groupadd -f render
if ! id "kiosk" &>/dev/null; then
    useradd -m kiosk
fi
usermod -aG video,input,seat,render,tty kiosk

# Nustatome DRM teises (perrašome taisykles, saugu daryti kelis kartus)
echo 'SUBSYSTEM=="drm", ACTION=="add", MODE="0660", GROUP="video"' > /etc/udev/rules.d/99-drm.rules
echo 'KERNEL=="renderD128", SUBSYSTEM=="drm", MODE="0666"' > /etc/udev/rules.d/99-renderD128.rules
udevadm control --reload-rules
udevadm trigger

echo "Įjungiu seatd servisą..."
systemctl enable --now seatd

echo "Ruošiu Python aplinką..."
# Gauname esamo projekto direktoriją (ji turėtų būti ta, kurioje dabar esame)
CURRENT_DIR="$(pwd)"
KIOSK_APP_DIR="$CURRENT_DIR"

# Tikriname, ar yra svarbūs konfigūracijos failai
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "Neradau .env failo, kuriu iš pavyzdžio..."
    cp .env.example .env
    echo "Sukurtas .env failas. Būtinai pakeiskite nustatymus pagal savo poreikius."
fi

if [ ! -f "client_secret.json" ]; then
    echo "ĮSPĖJIMAS: Nerastas client_secret.json failas!"
    echo "Jums reikės sukurti Google API projekto kredencialus ir įkelti client_secret.json failą."
fi

# Sukuriame tuščius failus, reikalingus darbui, jei jų nėra
if [ ! -f "albums_cache.json" ]; then
    touch albums_cache.json
fi

if [ ! -f "log.log" ]; then
    touch log.log
fi

# Sukuriame virtualią aplinką
setup_python_env "$KIOSK_APP_DIR"

# Atnaujiname shebang
sed -i "1c #!$KIOSK_APP_DIR/venv/bin/python3" "$KIOSK_APP_DIR/app.py"

# Nustatome teises
chown -R kiosk:kiosk "$KIOSK_APP_DIR"
find "$KIOSK_APP_DIR" -type f -exec chmod 644 {} \;
find "$KIOSK_APP_DIR" -type d -exec chmod 755 {} \;
if [ -f "$KIOSK_APP_DIR/client_secret.json" ]; then
    chmod 600 "$KIOSK_APP_DIR/client_secret.json"
fi
chmod 600 "$KIOSK_APP_DIR/config.py"
chmod 600 "$KIOSK_APP_DIR/.env"
chmod +x "$KIOSK_APP_DIR/app.py"
chmod 666 "$KIOSK_APP_DIR/albums_cache.json"
chmod 666 "$KIOSK_APP_DIR/log.log"

# Užtikriname, kad Python moduliai turi teisingas teises
chmod 644 "$KIOSK_APP_DIR/temp_monitor.py" 
chmod 644 "$KIOSK_APP_DIR/discord_voice.py"



echo "Kuriu paleidimo skriptą..."
cat > /home/kiosk/start-kiosk.sh << 'EOL'
#!/bin/bash

# Nustatome XDG_RUNTIME_DIR, kurio trūko anksčiau
export XDG_RUNTIME_DIR=/tmp/xdg-runtime-dir
mkdir -p $XDG_RUNTIME_DIR
chmod 700 $XDG_RUNTIME_DIR

# Paleidžiame dbus sesiją
if [ ! -e "$XDG_RUNTIME_DIR/bus" ]; then
    dbus-daemon --session --address="$DBUS_SESSION_BUS_ADDRESS" --nofork --nopidfile --syslog-only &
    sleep 1
fi

# Paleidžiame cage ir chromium
cage -d -- chromium-browser \
    --kiosk \
    --disable-gpu \
    --disable-software-rasterizer \
    --disable-dev-shm-usage \
    --no-sandbox \
    --disable-dbus \
    --incognito \
    --disable-extensions \
    --disable-plugins \
    --disable-popup-blocking \
    --disable-notifications \
    http://localhost:8080 &

# Laukiame kol cage pasileis ir sukurs Wayland sesiją
sleep 5

# Tikrinkime kokie monitoriai yra prijungti ir pasukame ekraną
OUTPUT=$(wlr-randr | grep -o -m 1 "^HDMI-[A-Za-z0-9\-]*")
if [ -n "$OUTPUT" ]; then
    echo "Rastas monitorius: $OUTPUT"
    for i in {1..3}; do
        if wlr-randr --output "$OUTPUT" --transform 270; then
            echo "Ekranas pasuktas sėkmingai"
            break
        fi
        sleep 2
    done
else
    echo "Monitorius nerastas"
fi

# Laukiame pagrindinio proceso
wait
EOL

echo "Nustatau teises paleidimo skriptui..."
chmod +x /home/kiosk/start-kiosk.sh
chown kiosk:kiosk /home/kiosk/start-kiosk.sh

echo "Kuriu servisų failus..."
cat > /etc/systemd/system/fridge-app.service << EOL
[Unit]
Description=Fridge Flask Application
After=network.target

[Service]
User=kiosk
WorkingDirectory=$KIOSK_APP_DIR
Environment="PATH=$KIOSK_APP_DIR/venv/bin"
ExecStart=$KIOSK_APP_DIR/venv/bin/python app.py
# Suteikiame daugiau teisių, kad galėtume skaityti temperatūros duomenis
ReadWritePaths=/sys/class/thermal/thermal_zone0
ProtectSystem=true
Restart=always

[Install]
WantedBy=multi-user.target
EOL

cat > /etc/systemd/system/kiosk.service << 'EOL'
[Unit]
Description=Kiosk Mode Service
After=network.target fridge-app.service
Requires=fridge-app.service
BindsTo=fridge-app.service

[Service]
User=kiosk
SupplementaryGroups=video render input seat tty
RuntimeDirectory=user/%U
RuntimeDirectoryMode=0700
Environment="XDG_RUNTIME_DIR=/tmp/xdg-runtime-dir"
Environment="WAYLAND_DISPLAY=wayland-0"
Environment="QT_QPA_PLATFORM=wayland"
Environment="GDK_BACKEND=wayland"
Environment="WLR_DRM_NO_ATOMIC=1"
Environment="WLR_RENDERER=pixman"
Environment="WLR_BACKENDS=drm"
Environment="DISPLAY=:0"
Environment="DBUS_SESSION_BUS_ADDRESS=unix:path=%t/user/%U/bus"
ExecStartPre=/bin/mkdir -p /tmp/xdg-runtime-dir
ExecStartPre=/bin/chmod 700 /tmp/xdg-runtime-dir
ExecStartPre=/bin/chown kiosk:kiosk /tmp/xdg-runtime-dir
ExecStartPre=/bin/bash -c "until curl -s http://localhost:8080 > /dev/null 2>&1; do sleep 2; done"
ExecStart=/home/kiosk/start-kiosk.sh
Restart=always

[Install]
WantedBy=multi-user.target
EOL

echo "Perkraunu systemd..."
systemctl daemon-reload

echo "Įjungiu servisus..."
systemctl enable fridge-app.service
systemctl enable kiosk.service

echo "Diegimas baigtas!"
echo
echo "Instrukcijos:"
echo
echo "1. Servisų valdymas:"
echo "   sudo systemctl restart fridge-app.service"
echo "   sudo systemctl restart kiosk.service"
echo
echo "2. Logų peržiūra:"
echo "   sudo journalctl -fu fridge-app.service"
echo "   sudo journalctl -fu kiosk.service"
echo
echo "3. Konfigūracija:"
echo "   - Slapti parametrai (.env failas): API raktai, tokenai ir kiti slapti duomenys"
echo "   - Visi kiti parametrai (config.py failas): rodymo trukmė, rodymo tipai, temperatūros ribos"
echo
echo "4. Temperatūros stebėjimas:"
echo "   - Sistema automatiškai stebės CPU temperatūrą"
echo "   - Kai temperatūra viršys 65°C, sistema laikinai perjungs tik į foto režimą"
echo
echo "5. Discord balsas:"
echo "   - Įsitikinkite, kad .env faile nustatyti DISCORD_BOT_TOKEN ir DISCORD_VOICE_CHANNEL_ID"
echo "   - Mikrofono ir garsiakalbio būseną galima konfigūruoti config.py faile (MIC_ENABLED ir SOUND_ENABLED parametrai)"
echo
echo "SVARBU: Po pirmos instaliacijos perkraukite sistemą (sudo reboot)"

exit 0 