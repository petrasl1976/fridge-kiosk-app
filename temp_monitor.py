import os
import time
import logging
import threading
import subprocess
from datetime import datetime

# Create logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('temp_monitor')

class TemperatureMonitor:
    def __init__(self, config):
        self.config = config
        self.running = False
        self.thread = None
        self.original_media_type = config.MEDIA_TYPES
        self.override_active = False
        self.last_temp = 0
        self.temp_history = []
        self.start_time = datetime.now()
        
    def get_cpu_temperature(self):
        """Gets CPU temperature on Raspberry Pi"""
        try:
            # Try to read from thermal_zone0
            if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = float(f.read()) / 1000.0
                    return temp
                    
            # Alternative method - using vcgencmd (Raspberry Pi only)
            result = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True)
            if result.returncode == 0:
                temp_text = result.stdout.strip()
                temp = float(temp_text.replace('temp=', '').replace('\'C', ''))
                return temp
                
            return 0  # Failed to get temperature
        except Exception as e:
            logger.error(f"Error getting temperature: {e}")
            return 0
    
    def log_temperature(self, temp):
        """Records temperature in history"""
        self.temp_history.append((datetime.now(), temp))
        # Keep only the last 24 hours
        cutoff = datetime.now().timestamp() - 24 * 60 * 60
        self.temp_history = [entry for entry in self.temp_history if entry[0].timestamp() > cutoff]
        self.last_temp = temp
    
    def handle_temperature(self, temp):
        """Handles temperature logic and protection"""
        from app import app  # Import here to avoid circular import
        
        if not hasattr(self.config, 'TEMP_WARNING') or not hasattr(self.config, 'TEMP_CRITICAL'):
            logger.warning("Temperature limits not set in config file")
            return
            
        # If temperature is above critical limit, try to reboot the system
        if temp >= self.config.TEMP_CRITICAL:
            logger.critical(f"CRITICAL TEMPERATURE: {temp}°C. Attempting to reboot the system.")
            try:
                # Reboot only if we have permissions
                if os.geteuid() == 0:  # Root privileges
                    subprocess.run(['reboot'])
                else:
                    logger.critical("No permissions to reboot. Manual reboot recommended!")
                    # Write message to file
                    with open('CRITICAL_TEMPERATURE.txt', 'w') as f:
                        f.write(f"CRITICAL TEMPERATURE: {temp}°C detected at {datetime.now()}. Manual reboot required!")
            except Exception as e:
                logger.error(f"Failed to reboot: {e}")
        
        # If temperature is above warning limit, switch to photo mode
        elif temp >= self.config.TEMP_WARNING and not self.override_active:
            logger.warning(f"Temperature reached {temp}°C. Switching to photo-only mode.")
            # Save original setting
            self.original_media_type = self.config.MEDIA_TYPES
            # Switch to photo-only mode
            self.config.MEDIA_TYPES = "photo"
            self.override_active = True
            
        # If temperature dropped, return to original mode
        elif temp <= self.config.TEMP_RECOVERY and self.override_active:
            logger.info(f"Temperature dropped to {temp}°C. Returning to normal mode.")
            # Restore original setting
            self.config.MEDIA_TYPES = self.original_media_type
            self.override_active = False
    
    def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Temperature monitoring started")
        while self.running:
            temp = self.get_cpu_temperature()
            if temp > 0:  # If successfully got temperature
                self.log_temperature(temp)
                logger.info(f"Current CPU temperature: {temp}°C")
                self.handle_temperature(temp)
            
            # Sleep until next check
            time.sleep(self.config.TEMP_CHECK_INTERVAL)
    
    def start(self):
        """Starts monitoring in a separate thread"""
        if not self.config.TEMP_MONITORING:
            logger.info("Temperature monitoring disabled in config file")
            return False
            
        if self.running:
            logger.warning("Temperature monitoring already running")
            return False
            
        self.running = True
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()
        return True
    
    def stop(self):
        """Stops monitoring"""
        if not self.running:
            return
            
        self.running = False
        if self.thread:
            self.thread.join(2.0)  # Wait max 2 seconds
        logger.info("Temperature monitoring stopped")
    
    def get_status(self):
        """Returns monitoring status as a dictionary"""
        return {
            'running': self.running,
            'last_temp': self.last_temp,
            'override_active': self.override_active,
            'original_media_type': self.original_media_type,
            'current_media_type': self.config.MEDIA_TYPES,
            'uptime': str(datetime.now() - self.start_time),
            'temp_history': [(t[0].isoformat(), t[1]) for t in self.temp_history[-10:]]  # Last 10 records
        } 