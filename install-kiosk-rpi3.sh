#!/bin/bash

echo "Šaldytuvo ekrano diegimo skriptas"
echo "Reikalavimai:"
echo "- Raspberry Pi OS Lite"
echo "- Prijungtas vertikalus ekranas"
echo "- Interneto ryšys"
echo "----------------------------------------"
echo

# Patikrinkime ar paleista su sudo
if [ "$EUID" -ne 0 ]; then 
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
    
    # Kopijuojame visus reikalingus failus
    cp app.py "$APP_DIR/"
    cp config.py "$APP_DIR/"
    cp client_secret.json "$APP_DIR/"
    cp my_secrets.py "$APP_DIR/"
    cp -r static "$APP_DIR/"
    cp -r templates "$APP_DIR/"

    # Sukuriame tuščius failus
    touch "$APP_DIR/albums_cache.json"
    touch "$APP_DIR/log.log"

    # Sukuriame ir aktyvuojame virtualenv
    cd "$APP_DIR"
    python3 -m venv venv
    source venv/bin/activate

    # Įdiegiame reikalingus Python modulius
    pip install --no-cache-dir flask \
        google-auth-oauthlib \
        google-auth-httplib2 \
        google-api-python-client \
        requests \
        broadlink \
        pytz
else
    # Jei direktorija neegzistuoja, sukuriame ją
    if [ ! -d "$APP_DIR" ]; then
        echo "Kuriu naują aplikacijos direktoriją..."
        mkdir -p "$APP_DIR"
        
        # Kopijuojame visus reikalingus failus
        cp app.py "$APP_DIR/"
        cp config.py "$APP_DIR/"
        cp client_secret.json "$APP_DIR/"
        cp my_secrets.py "$APP_DIR/"
        cp -r static "$APP_DIR/"
        cp -r templates "$APP_DIR/"

        # Sukuriame tuščius failus
        touch "$APP_DIR/albums_cache.json"
        touch "$APP_DIR/log.log"

        # Sukuriame ir aktyvuojame virtualenv
        cd "$APP_DIR"
        python3 -m venv venv
        source venv/bin/activate

        # Įdiegiame reikalingus Python modulius
        pip install --no-cache-dir flask \
            google-auth-oauthlib \
            google-auth-httplib2 \
            google-api-python-client \
            requests \
            broadlink \
            pytz
    else
        echo "Aplikacijos direktorija jau egzistuoja, atnaujinu failus..."
        # Atnaujiname tik pagrindinius failus
        cp app.py "$APP_DIR/"
        cp config.py "$APP_DIR/"
        cp client_secret.json "$APP_DIR/"
        cp my_secrets.py "$APP_DIR/"
        cp -r static "$APP_DIR/"
        cp -r templates "$APP_DIR/"
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
chmod 600 "$APP_DIR/my_secrets.py"
chmod +x "$APP_DIR/app.py"
chmod 666 "$APP_DIR/albums_cache.json"
chmod 666 "$APP_DIR/log.log"

echo "Kuriu paleidimo skriptą..."
cat > /home/kiosk/start-kiosk.sh << 'EOL'
#!/bin/bash

# Paleidžiame dbus sesiją
if [ ! -e "$XDG_RUNTIME_DIR/bus" ]; then
    dbus-daemon --session --address="$DBUS_SESSION_BUS_ADDRESS" --nofork --nopidfile --syslog-only &
    sleep 1
fi

# Paleidžiame cage ir chromium
cage -m last -- chromium-browser \
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

# Bandome kelis kartus pasukti ekraną
for i in {1..3}; do
    if wlr-randr --output HDMI-A-1 --transform 270; then
        break
    fi
    sleep 2
done

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
Restart=always

[Install]
WantedBy=multi-user.target
EOL

cat > /etc/systemd/system/kiosk.service << 'EOL'
[Unit]
Description=Kiosk Mode Service
After=network.target fridge-app.service
Requires=fridge-app.service

[Service]
User=kiosk
RuntimeDirectory=user/%U
RuntimeDirectoryMode=0700
Environment="XDG_RUNTIME_DIR=%t/user/%U"
Environment="WAYLAND_DISPLAY=wayland-0"
Environment="QT_QPA_PLATFORM=wayland"
Environment="GDK_BACKEND=wayland"
Environment="WLR_DRM_NO_ATOMIC=1"
Environment="WLR_BACKENDS=drm"
Environment="WLR_DRM_DEVICES=/dev/dri/card0"
Environment="DISPLAY=:0"
Environment="DBUS_SESSION_BUS_ADDRESS=unix:path=%t/user/%U/bus"
ExecStart=/home/kiosk/start-kiosk.sh
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Perkrauname systemd konfigūraciją
systemctl daemon-reload

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
echo "SVARBU: Po pirmos instaliacijos perkraukite sistemą (sudo reboot)" 
