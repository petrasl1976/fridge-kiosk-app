import os
import time
import logging
import threading
import subprocess
from datetime import datetime

# Sukuriame logger'į
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
        """Gauna CPU temperatūrą Raspberry Pi"""
        try:
            # Bandome skaityti iš thermal_zone0
            if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = float(f.read()) / 1000.0
                    return temp
                    
            # Alternatyvus būdas - per vcgencmd (tik Raspberry Pi)
            result = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True)
            if result.returncode == 0:
                temp_text = result.stdout.strip()
                temp = float(temp_text.replace('temp=', '').replace('\'C', ''))
                return temp
                
            return 0  # Nepavyko gauti temperatūros
        except Exception as e:
            logger.error(f"Klaida gaunant temperatūrą: {e}")
            return 0
    
    def log_temperature(self, temp):
        """Registruoja temperatūrą į istoriją"""
        self.temp_history.append((datetime.now(), temp))
        # Išlaikome tik paskutines 24 valandas
        cutoff = datetime.now().timestamp() - 24 * 60 * 60
        self.temp_history = [entry for entry in self.temp_history if entry[0].timestamp() > cutoff]
        self.last_temp = temp
    
    def handle_temperature(self, temp):
        """Tvarko temperatūros logiką ir apsaugą"""
        from app import app  # Importuojame čia, kad išvengtume ciklinio importo
        
        if not hasattr(self.config, 'TEMP_WARNING') or not hasattr(self.config, 'TEMP_CRITICAL'):
            logger.warning("Temperatūros ribos nenustatytos config faile")
            return
            
        # Jei temperatūra virš kritinės ribos, bandome perkrauti sistemą
        if temp >= self.config.TEMP_CRITICAL:
            logger.critical(f"KRITINĖ TEMPERATŪRA: {temp}°C. Bandoma perkrauti sistemą.")
            try:
                # Perkrauname tik jei turime teises
                if os.geteuid() == 0:  # Root teisės
                    subprocess.run(['reboot'])
                else:
                    logger.critical("Neturime teisių perkrauti. Rekomenduojama rankinis perkrovimas!")
                    # Įrašome žinutę į failą
                    with open('CRITICAL_TEMPERATURE.txt', 'w') as f:
                        f.write(f"KRITINĖ TEMPERATŪRA: {temp}°C aptikta {datetime.now()}. Reikalingas rankinis perkrovimas!")
            except Exception as e:
                logger.error(f"Nepavyko perkrauti: {e}")
        
        # Jei temperatūra virš įspėjimo ribos, perjungiame į foto režimą
        elif temp >= self.config.TEMP_WARNING and not self.override_active:
            logger.warning(f"Temperatūra pasiekė {temp}°C. Perjungiama į tik foto režimą.")
            # Išsaugome originalų nustatymą
            self.original_media_type = self.config.MEDIA_TYPES
            # Perjungiame į tik photo režimą
            self.config.MEDIA_TYPES = "photo"
            self.override_active = True
            
        # Jei temperatūra nukrito, grįžtame į originalų režimą
        elif temp <= self.config.TEMP_RECOVERY and self.override_active:
            logger.info(f"Temperatūra nukrito iki {temp}°C. Grįžtama į normalų režimą.")
            # Grąžiname originalų nustatymą
            self.config.MEDIA_TYPES = self.original_media_type
            self.override_active = False
    
    def monitor_loop(self):
        """Pagrindinis stebėjimo ciklas"""
        logger.info("Temperatūros stebėjimas pradėtas")
        while self.running:
            temp = self.get_cpu_temperature()
            if temp > 0:  # Jei pavyko gauti temperatūrą
                self.log_temperature(temp)
                logger.info(f"Dabartinė CPU temperatūra: {temp}°C")
                self.handle_temperature(temp)
            
            # Miegame iki kito patikrinimo
            time.sleep(self.config.TEMP_CHECK_INTERVAL)
    
    def start(self):
        """Pradeda stebėjimą atskirame gije"""
        if not self.config.TEMP_MONITORING:
            logger.info("Temperatūros stebėjimas išjungtas config faile")
            return False
            
        if self.running:
            logger.warning("Temperatūros stebėjimas jau veikia")
            return False
            
        self.running = True
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()
        return True
    
    def stop(self):
        """Sustabdo stebėjimą"""
        if not self.running:
            return
            
        self.running = False
        if self.thread:
            self.thread.join(2.0)  # Laukiame maks. 2 sekundes
        logger.info("Temperatūros stebėjimas sustabdytas")
    
    def get_status(self):
        """Grąžina stebėjimo būseną kaip žodyną"""
        return {
            'running': self.running,
            'last_temp': self.last_temp,
            'override_active': self.override_active,
            'original_media_type': self.original_media_type,
            'current_media_type': self.config.MEDIA_TYPES,
            'uptime': str(datetime.now() - self.start_time),
            'temp_history': [(t[0].isoformat(), t[1]) for t in self.temp_history[-10:]]  # Paskutiniai 10 įrašų
        } 