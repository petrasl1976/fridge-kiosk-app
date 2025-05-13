# Fridge Kiosk App

A Raspberry Pi based kiosk application for your refrigerator that displays:

- **Family photos and videos** from Google Photos (random album, random photo + adjustable sequence)
- **Family calendar** with events color-coded by person
- **Discord messages** and voice channel status
- **Weather forecast** for whole week
- **System status** indor temperature and humidity including CPU temperature monitoring
- **Time and date** 
- **Temperature monitoring** with auto-switching to photo-only mode when Pi gets hot

## Installation

### Prerequisites
- Raspberry Pi with Raspberry Pi OS Lite (64-bit)
- Vertical screen connected to Pi
- Internet connection
- Google Calendar and Discord account

### Installation Steps

1. **Initial setup**
   ```bash
   # Write Raspberry Pi OS Light (64-bit) to SD card
   # Create user "kiosk" during initial setup
   # Enable WiFi and SSH
   ```

2. **Connect to Pi and install**
   ```bash
   # Connect via SSH (with port forwarding for OAuth)
   ssh -A -L 8080:localhost:8080 kiosk@YOUR_PI_IP

   # Install Git and clone repo
   sudo apt install -y git
   git clone git@github.com:petrasl1976/fridge-kiosk-app.git
   cd fridge-kiosk-app
   
   # Set up configuration
   cp .env.example .env
   vi .env  # Edit configuration values

   # Create client_secret.json for Google API
   # (Follow the instructions in install-kiosk-rpi5.sh for getting credentials)
   vi client_secret.json
   
   # Run installer
   sudo ./install-kiosk-rpi5.sh
   
   # Reboot system
   sudo reboot
   ```

3. **First run and authorization**
   ```bash
   # Connect with port forwarding again
   ssh -A -L 8080:localhost:8080 kiosk@YOUR_PI_IP
   
   # Open in browser on your PC to authorize Google APIs
   # http://localhost:8080/
   
   # Restart kiosk service
   sudo systemctl restart kiosk
   ```

## Management

- **Service control:**
  ```bash
  sudo systemctl restart fridge-app.service  # Restart app
  sudo systemctl restart kiosk.service       # Restart display
  ```

- **Logs:**
  ```bash
  sudo journalctl -fu fridge-app.service     # App logs
  sudo journalctl -fu kiosk.service          # Display logs
  ```

## Configuration

Edit `.env` file for:
- Google Calendar ID
- Discord bot token and channel IDs

Edit `config.py` for:
- Display settings
- Media preferences
- Temperature thresholds
- UI customization

## Troubleshooting

If the screen is not rotating correctly, check the display connection and verify that the rotation settings in `start-kiosk.sh` match your setup.

For Google API issues, check that your `client_secret.json` is valid and that you've authorized the application.