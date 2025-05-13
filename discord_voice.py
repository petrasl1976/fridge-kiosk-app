import discord
import logging
import asyncio
import threading

class DiscordVoiceClient:
    def __init__(self, token, channel_id):
        self.token = token
        self.channel_id = channel_id
        self.logger = logging.getLogger('discord_voice')
        
        # State variables
        self.connected = False
        self.muted = True
        self.deafened = True
        
        # Discord client initialization
        self.client = None
        self.voice_client = None
        self.shutdown_event = threading.Event()
        
        # Create Discord intents
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.message_content = True
        
        # Create client with our intents
        self.client = discord.Client(intents=intents)
        
        # Register event handlers
        @self.client.event
        async def on_ready():
            self.logger.info(f'Discord connected as {self.client.user}')
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
            channel = self.client.get_channel(int(self.channel_id))
            if not channel:
                self.logger.error(f'Failed to find voice channel with ID {self.channel_id}')
                return
            
            self.logger.info(f'Attempting to connect to voice channel: {channel.name}')
            
            # If already connected to another channel, disconnect
            if self.voice_client and self.voice_client.is_connected():
                await self.voice_client.disconnect()
            
            # Connect to channel
            self.voice_client = await channel.connect()
            self.connected = True
            self.logger.info(f'Connected to voice channel: {channel.name}')
            
            # Set initial state - muted and deafened
            await self.voice_client.set_mute(True)
            await self.voice_client.set_deaf(True)
            self.muted = True
            self.deafened = True
        
        except Exception as e:
            self.logger.error(f'Error connecting to voice channel: {e}')
    
    def start(self):
        """Starts Discord client in a separate thread"""
        def run_client():
            try:
                # Run asynchronous Discord client
                asyncio.run(self.client.start(self.token))
            except Exception as e:
                self.logger.error(f'Error starting Discord client: {e}')
        
        # Start a new thread for Discord client
        self.thread = threading.Thread(target=run_client, daemon=True)
        self.thread.start()
        self.logger.info('Discord client started')
    
    def stop(self):
        """Stops Discord client"""
        if self.client:
            # Set shutdown event so we know when we're done
            self.shutdown_event.set()
            
            # Create asynchronous function that will disconnect from voice and close client
            async def shutdown():
                if self.voice_client:
                    await self.voice_client.disconnect()
                await self.client.close()
            
            # Run disconnect function
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(shutdown())
            except Exception as e:
                self.logger.error(f'Error stopping Discord client: {e}')
        
        self.logger.info('Discord client stopped')
    
    async def toggle_mute_async(self):
        """Asynchronous function for microphone toggling"""
        if not self.connected or not self.voice_client:
            return False
        
        try:
            self.muted = not self.muted
            await self.voice_client.set_mute(self.muted)
            self.logger.info(f'Microphone {"disabled" if self.muted else "enabled"}')
            return True
        except Exception as e:
            self.logger.error(f'Error toggling microphone: {e}')
            return False
    
    async def toggle_deafen_async(self):
        """Asynchronous function for sound toggling"""
        if not self.connected or not self.voice_client:
            return False
        
        try:
            self.deafened = not self.deafened
            await self.voice_client.set_deaf(self.deafened)
            self.logger.info(f'Sound {"disabled" if self.deafened else "enabled"}')
            return True
        except Exception as e:
            self.logger.error(f'Error toggling sound: {e}')
            return False
    
    def toggle_mute(self):
        """Toggles microphone state (for calling from Flask)"""
        if not self.connected:
            return {"success": False, "message": "Not connected to voice channel"}
        
        # Create a new event loop
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.toggle_mute_async())
            if result:
                return {"success": True, "muted": self.muted}
            return {"success": False, "message": "Failed to toggle microphone"}
        except Exception as e:
            self.logger.error(f'Error: {e}')
            return {"success": False, "message": str(e)}
        finally:
            loop.close()
    
    def toggle_deafen(self):
        """Toggles sound state (for calling from Flask)"""
        if not self.connected:
            return {"success": False, "message": "Not connected to voice channel"}
        
        # Create a new event loop
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.toggle_deafen_async())
            if result:
                return {"success": True, "deafened": self.deafened}
            return {"success": False, "message": "Failed to toggle sound"}
        except Exception as e:
            self.logger.error(f'Error: {e}')
            return {"success": False, "message": str(e)}
        finally:
            loop.close()
    
    def get_status(self):
        """Returns current state"""
        return {
            "connected": self.connected,
            "muted": self.muted,
            "deafened": self.deafened
        } 