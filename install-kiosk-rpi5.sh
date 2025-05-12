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

# Funkcija pagrindinių reikalingų failų kopijavimui
copy_required_files() {
    local dest_dir=$1
    
    echo "Kopijuoju reikalingus failus į $dest_dir..."
    # Pagrindiniai failai
    cp app.py "$dest_dir/"
    cp config.py "$dest_dir/"
    
    # Python moduliai
    if [ -f "temp_monitor.py" ]; then
        cp temp_monitor.py "$dest_dir/"
    else
        echo "ĮSPĖJIMAS: temp_monitor.py failas nerastas"
    fi
    
    if [ -f "discord_voice.py" ]; then
        cp discord_voice.py "$dest_dir/"
    else
        echo "ĮSPĖJIMAS: discord_voice.py failas nerastas"
    fi
    
    # Slapti failai, jei jie egzistuoja
    if [ -f "client_secret.json" ]; then
        cp client_secret.json "$dest_dir/"
    else
        echo "ĮSPĖJIMAS: client_secret.json failas nerastas, jį reikės sukurti rankiniu būdu"
    fi
    
    # Kopijuojame arba sukuriame .env failą
    if [ -f ".env" ]; then
        cp .env "$dest_dir/"
    elif [ -f ".env.example" ]; then
        cp .env.example "$dest_dir/.env"
        echo "Sukurtas .env failas iš pavyzdžio. Būtinai pakeiskite nustatymus pagal savo poreikius!"
    else
        echo "ĮSPĖJIMAS: .env failai nerasti, juos reikės sukurti rankiniu būdu"
    fi
    
    # Kopijuojame statinius failus ir šablonus
    cp -r static "$dest_dir/"
    cp -r templates "$dest_dir/"
    
    # Sukuriame tuščius failus, reikalingus darbui
    touch "$dest_dir/albums_cache.json"
    touch "$dest_dir/log.log"
    
    echo "Visi failai nukopijuoti sėkmingai."
}

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
# Sukuriame projekto direktoriją
APP_DIR="/home/kiosk/fridge-kiosk-app"
if [ $CLEAR_APP -eq 1 ]; then
    if [ -d "$APP_DIR" ]; then
        echo "Šalinu seną aplikacijos direktoriją..."
        rm -rf "$APP_DIR"
    fi
    mkdir -p "$APP_DIR"
    
    # Kopijuojame failus ir sukuriame virtualią aplinką
    copy_required_files "$APP_DIR"
    setup_python_env "$APP_DIR"
    
else
    # Jei direktorija neegzistuoja, sukuriame ją
    if [ ! -d "$APP_DIR" ]; then
        echo "Kuriu naują aplikacijos direktoriją..."
        mkdir -p "$APP_DIR"
        
        # Kopijuojame failus ir sukuriame virtualią aplinką
        copy_required_files "$APP_DIR"
        setup_python_env "$APP_DIR"
        
    else
        echo "Aplikacijos direktorija jau egzistuoja, atnaujinu failus..."
        
        # Atnaujiname tik pagrindinius failus
        cp app.py "$APP_DIR/"
        cp config.py "$APP_DIR/"
        cp client_secret.json "$APP_DIR/"
        cp .env "$APP_DIR/"
        cp .env.example "$APP_DIR/"
        cp -r static "$APP_DIR/"
        cp -r templates "$APP_DIR/"
        
        # Kopijuojame Python modulius
        if [ -f "temp_monitor.py" ]; then
            cp temp_monitor.py "$APP_DIR/"
        else
            echo "ĮSPĖJIMAS: temp_monitor.py failas nerastas"
        fi
        
        if [ -f "discord_voice.py" ]; then
            cp discord_voice.py "$APP_DIR/"
        else
            echo "ĮSPĖJIMAS: discord_voice.py failas nerastas"
        fi
        
        # Įsitikiname, kad visi reikalingi moduliai yra įdiegti
        echo "Atnaujiname Python modulius..."
        setup_python_env "$APP_DIR"
    fi
fi

# Atnaujiname shebang
sed -i "1c #!$APP_DIR/venv/bin/python3" "$APP_DIR/app.py"

# Nustatome teises
chown -R kiosk:kiosk "$APP_DIR"
find "$APP_DIR" -type f -exec chmod 644 {} \;
find "$APP_DIR" -type d -exec chmod 755 {} \;
chmod 600 "$APP_DIR/client_secret.json"
chmod 600 "$APP_DIR/config.py"
chmod 600 "$APP_DIR/.env"
chmod +x "$APP_DIR/app.py"
chmod 666 "$APP_DIR/albums_cache.json"
chmod 666 "$APP_DIR/log.log"

# Užtikriname, kad Python moduliai turi teisingas teises
chmod 644 "$APP_DIR/temp_monitor.py" 
chmod 644 "$APP_DIR/discord_voice.py"

# Patikrinkime, ar visi būtini failai egzistuoja
echo "Tikrinu, ar visi būtini failai egzistuoja..."
MISSING_FILES=0
for file in "$APP_DIR/app.py" "$APP_DIR/config.py" "$APP_DIR/temp_monitor.py" "$APP_DIR/discord_voice.py"; do
    if [ ! -f "$file" ]; then
        echo "ĮSPĖJIMAS: Būtinas failas '$file' neegzistuoja!"
        MISSING_FILES=1
    fi
done

if [ $MISSING_FILES -eq 1 ]; then
    echo "Trūksta kai kurių būtinų failų. Aplikacija gali neveikti tinkamai."
else
    echo "Visi būtini failai egzistuoja."
fi

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
cat > /etc/systemd/system/fridge-app.service << 'EOL'
[Unit]
Description=Fridge Flask Application
After=network.target

[Service]
User=kiosk
WorkingDirectory=/home/kiosk/fridge-kiosk-app
Environment="PATH=/home/kiosk/fridge-kiosk-app/venv/bin"
ExecStart=/home/kiosk/fridge-kiosk-app/venv/bin/python app.py
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

# Perkrauname systemd konfigūraciją
systemctl daemon-reload

# Testuojame Python importus
echo "Testuojame Python importus..."
if sudo -u kiosk "$APP_DIR/venv/bin/python" -c "import flask; import requests; import google.oauth2.credentials; import broadlink; import dotenv; import discord; print('Visi Python moduliai sėkmingai importuoti!'); import discord_voice; import temp_monitor; print('Lokali moduliai sėkmingai importuoti!')"; then
    echo "Visi moduliai sėkmingai įdiegti."
else
    echo "KLAIDA: Nepavyko importuoti modulių, prašome patikrinti log.log failą"
fi

echo "Diegimas baigtas!"
echo
echo "Tolimesni žingsniai:"
echo "1. Įjunkite servisus:"
echo "   sudo systemctl enable fridge-app.service"
echo "   sudo systemctl enable kiosk.service"
echo
echo "2. Suteikite teises Google Photos ir Calendar:"
echo "   - Kompiuteryje paleiskite: ssh -A -L 8080:localhost:8080 puk@192.168.88.55"
echo "   - Naršyklėje atidarykite: http://localhost:8080"
echo "   - Suteikite reikiamas teises"
echo
echo "3. Paleiskite servisus:"
echo "   sudo systemctl start fridge-app.service"
echo "   sudo systemctl start kiosk.service"
echo
echo "4. Konfigūracija:"
echo "   - Slapti parametrai (.env failas): API raktai, tokenai ir kiti slapti duomenys"
echo "   - Visi kiti parametrai (config.py failas): rodymo trukmė, rodymo tipai, temperatūros ribos"
echo
echo "5. Temperatūros stebėjimas:"
echo "   - Sistema automatiškai stebės CPU temperatūrą"
echo "   - Kai temperatūra viršys 65°C, sistema laikinai perjungs tik į foto režimą"
echo
echo "SVARBU: Po pirmos instaliacijos perkraukite sistemą (sudo reboot)"

exit 0 