import discord
import logging
import asyncio
import threading
import traceback
import os
import time

class DiscordVoiceClient:
    def __init__(self, token, channel_id):
        self.token = token
        self.channel_id = channel_id
        self.logger = logging.getLogger('discord_voice')
        
        # Set audio device environment variables - force specific device
        os.environ['ALSA_CARD'] = '2'  # Jabra device from arecord -l
        os.environ['ALSA_PCM_DEVICE'] = '0'
        self.logger.info("Set audio device to card 2, device 0 (Jabra)")
        
        # State variables
        self.connected = False
        self.muted = False  # Start unmuted for debugging
        self.deafened = False  # Start undeafened for debugging
        self.audio_streaming = False
        
        # Discord client initialization
        self.client = None
        self.voice_client = None
        self.shutdown_event = threading.Event()
        
        # Create Discord intents
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.message_content = True
        
        self.logger.info(f"Initializing Discord client with channel ID: {channel_id}")
        self.logger.info(f"Bot token length: {len(token) if token else 0}")
        
        # Create client with our intents
        self.client = discord.Client(intents=intents)
        
        # Register event handlers
        @self.client.event
        async def on_ready():
            self.logger.info(f'Discord connected as {self.client.user}')
            self.logger.info(f'Attempting to connect to voice channel ID: {self.channel_id}')
            await self.connect_to_voice()
        
        @self.client.event
        async def on_voice_state_update(member, before, after):
            # When our presence in the voice channel changes
            if member.id == self.client.user.id:
                # Update state
                if after.channel is None:
                    self.connected = False
                    self.logger.info('Disconnected from voice channel')
                else:
                    self.connected = True
                    self.muted = after.self_mute
                    self.deafened = after.self_deaf
                    self.logger.info(f'Voice state updated: muted={self.muted}, deafened={self.deafened}')
    
    async def connect_to_voice(self):
        """Connects to voice channel"""
        try:
            # Find channel by ID
            self.logger.info(f"Looking for channel with ID: {self.channel_id}")
            channel = self.client.get_channel(int(self.channel_id))
            
            if not channel:
                # Try to get channel by ID via fetch_channel
                try:
                    self.logger.info("Channel not found via get_channel, trying fetch_channel...")
                    channel = await self.client.fetch_channel(int(self.channel_id))
                except Exception as fetch_error:
                    self.logger.error(f"Failed to fetch channel: {fetch_error}")
                    
            if not channel:
                self.logger.error(f'Failed to find voice channel with ID {self.channel_id}')
                return
            
            self.logger.info(f'Found channel: {channel.name} (Type: {channel.type})')
            self.logger.info(f'Attempting to connect to voice channel: {channel.name}')
            
            # If already connected to another channel, disconnect
            if self.voice_client and self.voice_client.is_connected():
                self.logger.info("Already connected to a channel, disconnecting first...")
                await self.voice_client.disconnect()
            
            # Connect to channel - py-cord uses different parameters than discord.py
            self.voice_client = await channel.connect(reconnect=True)
            self.connected = True
            self.logger.info(f'Connected to voice channel: {channel.name}')
            
            # Need to manually set mute and deafen state after connection
            # Import config here to avoid circular import
            try:
                from config import Config
                # Set initial state from config
                self.muted = not Config.DISCORD.get('MIC_ENABLED', False)  # Invert because true means muted
                self.deafened = not Config.DISCORD.get('SOUND_ENABLED', False)  # Invert because true means deafened
                
                self.logger.info(f'Setting initial voice states - muted: {self.muted}, deafened: {self.deafened}')
                if hasattr(self.voice_client, "set_mute"):
                    await self.voice_client.set_mute(self.muted)
                else:
                    # Fallback for py-cord if direct API not available
                    # Need to use Guild.voice_client methods
                    guild = channel.guild
                    if hasattr(guild, "change_voice_state"):
                        await guild.change_voice_state(
                            channel=channel,
                            self_mute=self.muted,
                            self_deaf=self.deafened
                        )
                
                self.logger.info(f'Initial state set - Microphone: {"disabled" if self.muted else "enabled"}, Sound: {"disabled" if self.deafened else "enabled"}')
                
                # Start audio stream after a brief delay if mic is enabled
                if not self.muted:
                    self.logger.info("Will start audio stream in 3 seconds...")
                    await asyncio.sleep(3)
                    await self.start_audio_stream()
            except Exception as config_e:
                self.logger.error(f'Error setting initial voice state: {config_e}')
                self.logger.error(f'Traceback: {traceback.format_exc()}')
                # Default to enabling everything
                self.muted = False
                self.deafened = False
                # Try to set defaults anyway
                try:
                    guild = channel.guild
                    if hasattr(guild, "change_voice_state"):
                        await guild.change_voice_state(
                            channel=channel,
                            self_mute=self.muted,
                            self_deaf=self.deafened
                        )
                except Exception as voice_e:
                    self.logger.error(f'Error setting voice state: {voice_e}')
                
                # Always try to start audio stream in default case
                await asyncio.sleep(3)
                await self.start_audio_stream()
                
        except Exception as e:
            self.logger.error(f'Error connecting to voice channel: {e}')
            self.logger.error(f'Traceback: {traceback.format_exc()}')
    
    async def start_audio_stream(self):
        """Starts audio streaming from microphone to Discord"""
        if not self.connected or not self.voice_client:
            self.logger.warning("Cannot start audio stream: not connected to voice channel")
            return False
            
        try:
            # Try different audio formats
            sources = [
                # Try direct ALSA input first
                ("direct ALSA", lambda: discord.PCMAudio(source='alsa:hw:2,0')),
                # Backup option using arecord as external process
                ("arecord via pipe", lambda: discord.FFmpegPCMAudio(
                    source="-",
                    pipe=True,
                    before_options="-f alsa -i hw:2,0 -ac 1 -ar 48000",
                    options="-loglevel error"
                ))
            ]
            
            # Try each source until one works
            for source_name, source_factory in sources:
                try:
                    self.logger.info(f"Trying audio source: {source_name}")
                    source = source_factory()
                    
                    # If we have a running audio stream, stop it first
                    if hasattr(self.voice_client, "source") and self.voice_client.source:
                        self.voice_client.stop()
                        self.logger.info("Stopped existing audio stream")
                    
                    # Play audio from mic to Discord
                    self.voice_client.play(source, after=lambda e: 
                        self.logger.error(f"Audio stream stopped: {e}") if e else 
                        self.logger.info("Audio stream ended normally")
                    )
                    
                    self.audio_streaming = True
                    self.logger.info(f"Audio stream started successfully using {source_name}")
                    return True
                except Exception as src_e:
                    self.logger.error(f"Failed to start audio with {source_name}: {src_e}")
                    continue
            
            self.logger.error("All audio source methods failed")
            return False
        except Exception as e:
            self.logger.error(f"Failed to start audio stream: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    async def stop_audio_stream(self):
        """Stops the audio stream"""
        if not self.audio_streaming:
            return
            
        try:
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
                self.logger.info("Audio stream stopped")
            self.audio_streaming = False
        except Exception as e:
            self.logger.error(f"Error stopping audio stream: {e}")
            
    def start(self):
        """Starts Discord client in a separate thread"""
        def run_client():
            try:
                self.logger.info("Starting Discord client...")
                # Run asynchronous Discord client
                asyncio.run(self.client.start(self.token))
            except Exception as e:
                self.logger.error(f'Error starting Discord client: {e}')
                self.logger.error(f'Traceback: {traceback.format_exc()}')
        
        # Start a new thread for Discord client
        self.thread = threading.Thread(target=run_client, daemon=True)
        self.thread.start()
        self.logger.info('Discord client started in separate thread')
    
    def stop(self):
        """Stops Discord client"""
        if self.client:
            # Set shutdown event so we know when we're done
            self.logger.info("Shutting down Discord client...")
            self.shutdown_event.set()
            
            # Create asynchronous function that will disconnect from voice and close client
            async def shutdown():
                # Stop audio streaming if active
                await self.stop_audio_stream()
                
                if self.voice_client:
                    self.logger.info("Disconnecting from voice channel...")
                    try:
                        await self.voice_client.disconnect()
                        self.logger.info("Successfully disconnected from voice channel")
                    except Exception as e:
                        self.logger.error(f"Error disconnecting from voice: {e}")
                
                self.logger.info("Closing Discord client...")
                try:
                    await self.client.close()
                    self.logger.info("Discord client closed successfully")
                except Exception as e:
                    self.logger.error(f"Error closing Discord client: {e}")
            
            # Run disconnect function
            try:
                self.logger.info("Creating event loop for shutdown...")
                loop = asyncio.get_event_loop()
                loop.run_until_complete(shutdown())
                self.logger.info("Shutdown completed via event loop")
            except Exception as e:
                self.logger.error(f'Error stopping Discord client: {e}')
                self.logger.error(f'Traceback: {traceback.format_exc()}')
        
        self.logger.info('Discord client stopped')
    
    async def toggle_mute_async(self):
        """Asynchronous function for microphone toggling"""
        if not self.connected or not self.voice_client:
            self.logger.warning("Cannot toggle mute: not connected to voice channel")
            return False
        
        try:
            self.logger.info(f"Toggling microphone from {self.muted} to {not self.muted}")
            self.muted = not self.muted
            
            # Different ways to toggle mute depending on the library we're using
            try:
                # Try direct method first
                if hasattr(self.voice_client, "set_mute"):
                    await self.voice_client.set_mute(self.muted)
                # Fallback to guild voice state
                else:
                    channel = self.voice_client.channel
                    guild = channel.guild
                    await guild.change_voice_state(
                        channel=channel,
                        self_mute=self.muted,
                        self_deaf=self.deafened
                    )
            except Exception as toggle_e:
                self.logger.error(f"Error setting mute state: {toggle_e}")
                
            # When unmuting, start audio stream; when muting, stop it
            if not self.muted and not self.audio_streaming:
                await self.start_audio_stream()
            elif self.muted and self.audio_streaming:
                await self.stop_audio_stream()
                
            self.logger.info(f'Microphone {"disabled" if self.muted else "enabled"}')
            return True
        except Exception as e:
            self.logger.error(f'Error toggling microphone: {e}')
            self.logger.error(f'Traceback: {traceback.format_exc()}')
            return False
    
    async def toggle_deafen_async(self):
        """Asynchronous function for sound toggling"""
        if not self.connected or not self.voice_client:
            self.logger.warning("Cannot toggle deafen: not connected to voice channel")
            return False
        
        try:
            self.logger.info(f"Toggling sound from {self.deafened} to {not self.deafened}")
            self.deafened = not self.deafened
            
            # Different ways to toggle deafen depending on the library
            try:
                # Try direct method first
                if hasattr(self.voice_client, "set_deaf"):
                    await self.voice_client.set_deaf(self.deafened)
                # Fallback to guild voice state
                else:
                    channel = self.voice_client.channel
                    guild = channel.guild
                    await guild.change_voice_state(
                        channel=channel,
                        self_mute=self.muted,
                        self_deaf=self.deafened
                    )
            except Exception as toggle_e:
                self.logger.error(f"Error setting deafen state: {toggle_e}")
                
            self.logger.info(f'Sound {"disabled" if self.deafened else "enabled"}')
            return True
        except Exception as e:
            self.logger.error(f'Error toggling sound: {e}')
            self.logger.error(f'Traceback: {traceback.format_exc()}')
            return False
    
    def toggle_mute(self):
        """Toggles microphone state (for calling from Flask)"""
        if not self.connected:
            self.logger.warning("Cannot toggle mute from Flask: not connected to voice channel")
            return {"success": False, "message": "Not connected to voice channel"}
        
        # Create a new event loop
        self.logger.info("Creating new event loop for toggling microphone")
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.toggle_mute_async())
            if result:
                self.logger.info(f"Successfully toggled microphone to: {self.muted}")
                return {"success": True, "muted": self.muted}
            
            self.logger.warning("Failed to toggle microphone")
            return {"success": False, "message": "Failed to toggle microphone"}
        except Exception as e:
            self.logger.error(f'Error in toggle_mute: {e}')
            self.logger.error(f'Traceback: {traceback.format_exc()}')
            return {"success": False, "message": str(e)}
        finally:
            loop.close()
            self.logger.info("Closed event loop after toggling microphone")
    
    def toggle_deafen(self):
        """Toggles sound state (for calling from Flask)"""
        if not self.connected:
            self.logger.warning("Cannot toggle deafen from Flask: not connected to voice channel")
            return {"success": False, "message": "Not connected to voice channel"}
        
        # Create a new event loop
        self.logger.info("Creating new event loop for toggling sound")
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.toggle_deafen_async())
            if result:
                self.logger.info(f"Successfully toggled sound to: {self.deafened}")
                return {"success": True, "deafened": self.deafened}
            
            self.logger.warning("Failed to toggle sound")
            return {"success": False, "message": "Failed to toggle sound"}
        except Exception as e:
            self.logger.error(f'Error in toggle_deafen: {e}')
            self.logger.error(f'Traceback: {traceback.format_exc()}')
            return {"success": False, "message": str(e)}
        finally:
            loop.close()
            self.logger.info("Closed event loop after toggling sound")
    
    def get_status(self):
        """Returns current state"""
        state = {
            "connected": self.connected,
            "muted": self.muted,
            "deafened": self.deafened,
            "audio_streaming": self.audio_streaming
        }
        self.logger.info(f"Current Discord voice status: {state}")
        return state 