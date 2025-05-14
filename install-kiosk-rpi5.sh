#!/bin/bash

echo "=================================================="
echo "        FRIDGE KIOSK INSTALLATION SCRIPT          "
echo "=================================================="
echo
echo "REQUIREMENTS:"
echo "  • Raspberry Pi OS Lite (latest version recommended)"
echo "  • Connected vertical screen"
echo "  • Internet connection"
echo "  • User 'kiosk' must be created before running this script"
echo
echo "CONFIGURATION BEFORE INSTALLATION:"
echo "  1. Create required configuration files:"
echo
echo "  INSTRUCTIONS for obtaining client_secret.json:"
echo "   1. Open https://console.cloud.google.com"
echo "   2. Create a new project"
echo "   3. Enable Google Calendar API and Google Photos Library API"
echo "   4. Menu: 'APIs & Services' -> 'Credentials'"
echo "   5. Create OAuth client ID ('Create credentials' -> 'OAuth client ID')"
echo "   6. Authorized JavaScript origins: http://localhost:8080"
echo "   7. Authorized redirect URIs: http://localhost:8080/oauth2callback"
echo "   8. Select type 'Web application' and Download OAuth client"
echo "   9. Rename file to 'client_secret.json' and upload to fridge-kiosk-app folder"
echo
echo "  INSTRUCTIONS for setting up .env file:"
echo "   • Copy .env.example to .env and update with your values:"
echo
echo "  INSTRUCTIONS for obtaining calendar ID:"
echo "   1. Open https://calendar.google.com"
echo "   2. Find your calendar on the left, three dots -> 'Settings'"
echo "   3. Find 'Calendar ID' and copy to .env file (FAMILY_CALENDAR_ID=...)"
echo
echo "  INSTRUCTIONS for obtaining Discord bot token:"
echo "   1. Go to https://discord.com/developers/applications"
echo "   2. Click 'New Application' and give it a name"
echo "   3. Go to 'Bot' section and click 'Add Bot'"
echo "   4. Under TOKEN, click 'Copy' (or 'Reset Token' if needed)"
echo "   5. Enable 'Message Content Intent', 'Server Members Intent', and 'Voice States Intent'"
echo "   6. Paste token into .env file as DISCORD_BOT_TOKEN"
echo "   7. Go to OAuth2 -> URL Generator, select 'bot' scope with permissions:"
echo "      - Read Messages/View Channels"
echo "      - Send Messages"
echo "      - Connect (voice)"
echo "      - Speak (voice)"
echo "   8. Use generated URL to invite bot to your Discord server"
echo
echo "  INSTRUCTIONS for obtaining Discord channel IDs:"
echo "   1. Open Discord app settings -> Advanced -> Enable Developer Mode"
echo "   2. Right-click on a text channel -> Copy ID (for DISCORD_CHANNEL_ID)"
echo "   3. Right-click on a voice channel -> Copy ID (for DISCORD_VOICE_CHANNEL_ID)"
echo "   4. Paste these IDs into .env file"
echo
echo "USAGE:"
echo "  • Log in as kiosk user and run: sudo ./install-kiosk-rpi5.sh"
echo "  • You can run this script multiple times if needed - it's safe!"
echo
echo "IMPORTANT: This script must be run as the kiosk user via sudo"
echo "=================================================="
echo
echo "Press ENTER to continue or CTRL+C to cancel..."
read

# Check if running as kiosk user with sudo
if [ "$(logname)" != "kiosk" ]; then 
    echo "ERROR: This script must be run from the kiosk user's account with sudo"
    echo "Please login as 'kiosk' user and run: sudo ./install-kiosk-rpi5.sh"
    exit 1
fi

# Check if running with sudo/as root
if [ "$(id -u)" -ne 0 ]; then 
    echo "ERROR: This script must be run with sudo"
    echo "Please run: sudo ./install-kiosk-rpi5.sh"
    exit 1
fi

# Check if sudo is available
if ! command -v sudo &> /dev/null; then
    echo "ERROR: sudo is not installed"
    exit 1
fi

# Function for creating Python virtual environment and installing modules
setup_python_env() {
    local app_dir=$1
    
    echo "Creating virtual environment and setting permissions..."
    cd "$app_dir"
    python3 -m venv venv
    
    # Set permissions for the virtual environment
    chown -R kiosk:kiosk "$app_dir/venv"
    chmod -R 755 "$app_dir/venv/bin"
    # Ensure all files in bin directory are executable
    chmod +x "$app_dir/venv/bin/"*
    
    echo "Installing required Python modules..."
    sudo -u kiosk "$app_dir/venv/bin/pip" install --no-cache-dir flask \
        google-auth-oauthlib \
        google-auth-httplib2 \
        google-api-python-client \
        requests \
        broadlink \
        pytz \
        tzlocal \
        python-dotenv \
        py-cord \
        PyNaCl \
        pyaudio
        
    # Uninstall discord.py if it exists to avoid conflicts
    sudo -u kiosk "$app_dir/venv/bin/pip" uninstall -y discord.py discord
    
    # Install py-cord with voice support
    sudo -u kiosk "$app_dir/venv/bin/pip" install --no-cache-dir "py-cord[voice]"
}

echo "Checking and installing required packages..."
PACKAGES="chromium-browser cage dbus-x11 seatd python3-venv python3-pip wlr-randr ffmpeg alsa-utils pulseaudio"
NEW_PACKAGES=""

for pkg in $PACKAGES; do
    if ! dpkg -l | grep -q "^ii  $pkg "; then
        NEW_PACKAGES="$NEW_PACKAGES $pkg"
    fi
done

if [ ! -z "$NEW_PACKAGES" ]; then
    echo "Installing missing packages:$NEW_PACKAGES"
    apt update
    apt install -y $NEW_PACKAGES
else
    echo "All required packages already installed"
fi

echo "Creating required groups and adding kiosk user to them..."
groupadd -f seat
groupadd -f render
# Check if kiosk user exists
if ! id "kiosk" &>/dev/null; then
    echo "ERROR: User 'kiosk' does not exist!"
    echo "Please create the 'kiosk' user before running this script:"
    echo "  sudo useradd -m kiosk"
    exit 1
fi

# Add kiosk to required groups
usermod -aG video,input,seat,render,tty kiosk

# Set DRM permissions (overwrite rules, safe to do multiple times)
echo 'SUBSYSTEM=="drm", ACTION=="add", MODE="0660", GROUP="video"' > /etc/udev/rules.d/99-drm.rules
echo 'KERNEL=="renderD128", SUBSYSTEM=="drm", MODE="0666"' > /etc/udev/rules.d/99-renderD128.rules
udevadm control --reload-rules
udevadm trigger

echo "Enabling seatd service..."
systemctl enable --now seatd

echo "Preparing Python environment..."
# Get current project directory (should be where we are now)
CURRENT_DIR="$(pwd)"
KIOSK_APP_DIR="$CURRENT_DIR"

# Check if important configuration files exist
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "Could not find .env file, creating from example..."
    cp .env.example .env
    echo "Created .env file. Make sure to update settings according to your needs."
fi

if [ ! -f "client_secret.json" ]; then
    echo "WARNING: client_secret.json file not found!"
    echo "You will need to create Google API project credentials and upload client_secret.json file."
fi

# Create empty files needed for operation, if they don't exist
if [ ! -f "albums_cache.json" ]; then
    touch albums_cache.json
fi

if [ ! -f "log.log" ]; then
    touch log.log
fi

# Create virtual environment
setup_python_env "$KIOSK_APP_DIR"

# Update shebang
sed -i "1c #!$KIOSK_APP_DIR/venv/bin/python3" "$KIOSK_APP_DIR/app.py"

# Set permissions
chown -R kiosk:kiosk "$KIOSK_APP_DIR"
find "$KIOSK_APP_DIR" -type f -exec chmod 644 {} \;
find "$KIOSK_APP_DIR" -type d -exec chmod 755 {} \;
if [ -f "$KIOSK_APP_DIR/client_secret.json" ]; then
    chmod 600 "$KIOSK_APP_DIR/client_secret.json"
fi
chmod 600 "$KIOSK_APP_DIR/config.py"
chmod 600 "$KIOSK_APP_DIR/.env"
chmod +x "$KIOSK_APP_DIR/app.py"
chmod +x "$KIOSK_APP_DIR/audio_test.py"
chmod 666 "$KIOSK_APP_DIR/albums_cache.json"
chmod 666 "$KIOSK_APP_DIR/log.log"

# Ensure Python modules have correct permissions
chmod 644 "$KIOSK_APP_DIR/temp_monitor.py" 
if [ -f "$KIOSK_APP_DIR/discord_voice.py" ]; then
    chmod 644 "$KIOSK_APP_DIR/discord_voice.py"
fi

echo "Creating startup script..."
cat > /home/kiosk/start-kiosk.sh << 'EOL'
#!/bin/bash

# Set XDG_RUNTIME_DIR, which was missing before
export XDG_RUNTIME_DIR=/tmp/xdg-runtime-dir
mkdir -p $XDG_RUNTIME_DIR
chmod 700 $XDG_RUNTIME_DIR

# Start dbus session
if [ ! -e "$XDG_RUNTIME_DIR/bus" ]; then
    dbus-daemon --session --address="$DBUS_SESSION_BUS_ADDRESS" --nofork --nopidfile --syslog-only &
    sleep 1
fi

# Start cage and chromium
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

# Wait for cage to start and create Wayland session
sleep 5

# Check which monitors are connected and rotate the screen
OUTPUT=$(wlr-randr | grep -o -m 1 "^HDMI-[A-Za-z0-9\-]*")
if [ -n "$OUTPUT" ]; then
    echo "Found monitor: $OUTPUT"
    for i in {1..3}; do
        if wlr-randr --output "$OUTPUT" --transform 270; then
            echo "Screen rotated successfully"
            break
        fi
        sleep 2
    done
else
    echo "Monitor not found"
fi

# Wait for main process
wait
EOL

echo "Setting permissions for startup script..."
chmod +x /home/kiosk/start-kiosk.sh
chown kiosk:kiosk /home/kiosk/start-kiosk.sh

echo "Creating service files..."
cat > /etc/systemd/system/fridge-app.service << EOL
[Unit]
Description=Fridge Flask Application
After=network.target

[Service]
User=kiosk
WorkingDirectory=$KIOSK_APP_DIR
Environment="PATH=$KIOSK_APP_DIR/venv/bin"
ExecStart=$KIOSK_APP_DIR/venv/bin/python app.py
# Give more permissions to read temperature data
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

echo "Reloading systemd..."
systemctl daemon-reload

echo "Enabling services..."
systemctl enable fridge-app.service
systemctl enable kiosk.service

echo "Installation complete!"
echo
echo "After-installation steps:"
echo
echo "1. Service management:"
echo "   sudo systemctl restart fridge-app.service"
echo "   sudo systemctl restart kiosk.service"
echo
echo "2. Log viewing:"
echo "   sudo journalctl -fu fridge-app.service"
echo "   sudo journalctl -fu kiosk.service"
echo
echo "3. Grant access and start the app:"
echo "   ssh -A -L 8080:localhost:8080 kiosk@YOUR_PI_IP_ADDRESS"
echo "   open in browser: http://localhost:8080"
echo "   grant access to the app"
echo "   restart kiosk service: sudo systemctl restart kiosk"
echo
echo "4. Temperature monitoring:"
echo "   - System will automatically monitor CPU temperature"
echo "   - When temperature exceeds 65°C, system will temporarily switch to photo mode only"
echo
echo "5. Discord voice:"
echo "   - Make sure DISCORD_BOT_TOKEN and DISCORD_VOICE_CHANNEL_ID are set in .env file"
echo "   - Microphone and speaker status can be configured in config.py file (MIC_ENABLED and SOUND_ENABLED parameters)"
echo
echo "IMPORTANT: After first installation, restart the system (sudo reboot)"

exit 0 