#!/home/kiosk/fridge-kiosk-app/venv/bin/python3
"""
Audio Diagnostics for Fridge Kiosk
----------------------------------
This script tests audio configuration and helps diagnose issues with Discord voice chat.
Run it with: python3 audio_test.py
"""

import os
import sys
import time
import subprocess
import argparse
import logging
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('audio_test')

def check_audio_devices():
    """Check available audio devices"""
    logger.info("=== Checking audio devices ===")
    
    try:
        # Check audio input devices (microphones)
        logger.info("Audio input devices (microphones):")
        input_result = subprocess.run(['arecord', '-l'], capture_output=True, text=True)
        print(input_result.stdout)
        
        # Check audio output devices (speakers)
        logger.info("Audio output devices (speakers):")
        output_result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
        print(output_result.stdout)
        
        # Check loaded sound modules
        logger.info("Loaded sound modules:")
        modules_cmd = "lsmod | grep snd"
        modules_result = subprocess.run(modules_cmd, shell=True, capture_output=True, text=True)
        print(modules_result.stdout)
        
        return True
    except Exception as e:
        logger.error(f"Error checking audio devices: {e}")
        return False

def test_microphone(device_id=2, duration=5):
    """Record from microphone and play back to test it works"""
    logger.info(f"=== Testing microphone (card {device_id}) for {duration} seconds ===")
    
    try:
        # Record audio
        temp_file = "microphone_test.wav"
        logger.info(f"Recording {duration} seconds of audio...")
        record_cmd = f"arecord -D hw:{device_id},0 -f S16_LE -c1 -r44100 -d {duration} {temp_file}"
        subprocess.run(record_cmd, shell=True)
        
        # Play back the recorded audio
        logger.info("Playing back recorded audio...")
        play_cmd = f"aplay {temp_file}"
        subprocess.run(play_cmd, shell=True)
        
        # Clean up
        os.remove(temp_file)
        logger.info("Microphone test completed!")
        return True
    except Exception as e:
        logger.error(f"Error testing microphone: {e}")
        return False

def test_installed_packages():
    """Check that required Python packages are installed"""
    logger.info("=== Checking installed packages ===")
    
    try:
        # Check pip list
        pip_cmd = f"{sys.executable} -m pip list"
        result = subprocess.run(pip_cmd, shell=True, capture_output=True, text=True)
        
        # Look for key packages
        packages = {
            "py-cord": False,
            "PyNaCl": False,
            "discord.py": False,
            "pyaudio": False
        }
        
        for line in result.stdout.splitlines():
            for pkg in packages:
                if line.lower().startswith(pkg.lower()):
                    packages[pkg] = True
                    logger.info(f"Found package: {line}")
        
        # Report missing packages
        missing = [pkg for pkg, found in packages.items() if not found]
        if missing:
            logger.warning(f"Missing packages: {', '.join(missing)}")
        else:
            logger.info("All required packages are installed!")
            
        return True
    except Exception as e:
        logger.error(f"Error checking packages: {e}")
        return False

async def test_discord_audio():
    """Test Discord audio connection"""
    logger.info("=== Testing Discord audio connection ===")
    
    try:
        # Import Discord module
        try:
            import discord
            logger.info("Successfully imported Discord module")
        except ImportError:
            logger.error("Failed to import Discord module")
            return False
        
        # Check for PyNaCl
        try:
            import nacl
            logger.info("Successfully imported PyNaCl module")
        except ImportError:
            logger.error("Failed to import PyNaCl, voice won't work without it")
            return False
            
        # Try to create PCMAudio
        try:
            audio = discord.PCMAudio(source="alsa:hw:2,0")
            logger.info("Successfully created PCMAudio object")
        except Exception as e:
            logger.error(f"Failed to create PCMAudio: {e}")
            return False
            
        logger.info("Discord audio setup looks good!")
        return True
    except Exception as e:
        logger.error(f"Error testing Discord audio: {e}")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Audio diagnostics for Fridge Kiosk")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--devices", action="store_true", help="Check audio devices")
    parser.add_argument("--mic", action="store_true", help="Test microphone")
    parser.add_argument("--packages", action="store_true", help="Check installed packages")
    parser.add_argument("--discord", action="store_true", help="Test Discord audio")
    args = parser.parse_args()
    
    # If no args or --all, run all tests
    run_all = args.all or not (args.devices or args.mic or args.packages or args.discord)
    
    if run_all or args.devices:
        check_audio_devices()
        print("\n")
    
    if run_all or args.packages:
        test_installed_packages()
        print("\n")
    
    if run_all or args.mic:
        test_microphone()
        print("\n")
    
    if run_all or args.discord:
        asyncio.run(test_discord_audio())
        print("\n")
    
    logger.info("Audio diagnostics completed!")

if __name__ == "__main__":
    main() 