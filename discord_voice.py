import discord
import logging
import asyncio
import threading

class DiscordVoiceClient:
    def __init__(self, token, channel_id):
        self.token = token
        self.channel_id = channel_id
        self.logger = logging.getLogger('discord_voice')
        
        # Būsenos kintamieji
        self.connected = False
        self.muted = True
        self.deafened = True
        
        # Discord kliento inicijavimas
        self.client = None
        self.voice_client = None
        self.shutdown_event = threading.Event()
        
        # Kuriame Discord intents
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.message_content = True
        
        # Sukuriame klientą su mūsų intents
        self.client = discord.Client(intents=intents)
        
        # Registruojame event handler'ius
        @self.client.event
        async def on_ready():
            self.logger.info(f'Discord prisijungė kaip {self.client.user}')
            await self.connect_to_voice()
        
        @self.client.event
        async def on_voice_state_update(member, before, after):
            # Kai pasikeičia mūsų buvimas voice kanale
            if member.id == self.client.user.id:
                # Atnaujiname būseną
                if after.channel is None:
                    self.connected = False
                    self.logger.info('Atsijungta nuo voice kanalo')
                else:
                    self.connected = True
                    self.muted = after.self_mute
                    self.deafened = after.self_deaf
                    self.logger.info(f'Voice būsena atnaujinta: muted={self.muted}, deafened={self.deafened}')
    
    async def connect_to_voice(self):
        """Prisijungia prie voice kanalo"""
        try:
            # Randam kanalą pagal ID
            channel = self.client.get_channel(int(self.channel_id))
            if not channel:
                self.logger.error(f'Nepavyko rasti voice kanalo su ID {self.channel_id}')
                return
            
            self.logger.info(f'Bandoma prisijungti prie voice kanalo: {channel.name}')
            
            # Jei jau esame prisijungę prie kito kanalo, atsijungiame
            if self.voice_client and self.voice_client.is_connected():
                await self.voice_client.disconnect()
            
            # Prisijungiame prie kanalo
            self.voice_client = await channel.connect()
            self.connected = True
            self.logger.info(f'Prisijungta prie voice kanalo: {channel.name}')
            
            # Nustatome pradinę būseną - muted ir deafened
            await self.voice_client.set_mute(True)
            await self.voice_client.set_deaf(True)
            self.muted = True
            self.deafened = True
        
        except Exception as e:
            self.logger.error(f'Klaida jungiantis prie voice kanalo: {e}')
    
    def start(self):
        """Paleidžia Discord klientą atskirame thread'e"""
        def run_client():
            try:
                # Paleidžiame asynchroninį Discord klientą
                asyncio.run(self.client.start(self.token))
            except Exception as e:
                self.logger.error(f'Klaida paleidžiant Discord klientą: {e}')
        
        # Pradedame naują thread'ą Discord klientui
        self.thread = threading.Thread(target=run_client, daemon=True)
        self.thread.start()
        self.logger.info('Discord klientas paleistas')
    
    def stop(self):
        """Sustabdo Discord klientą"""
        if self.client:
            # Nustatome shutdown event, kad žinotume kada baigiame darbą
            self.shutdown_event.set()
            
            # Sukuriame asynchroninę funkciją, kuri atsijungs nuo voice ir išjungs klientą
            async def shutdown():
                if self.voice_client:
                    await self.voice_client.disconnect()
                await self.client.close()
            
            # Paleidžiame atsijungimo funkciją
            try:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(shutdown())
            except Exception as e:
                self.logger.error(f'Klaida stabdant Discord klientą: {e}')
        
        self.logger.info('Discord klientas sustabdytas')
    
    async def toggle_mute_async(self):
        """Asynchroninė funkcija mikrofono perjungimui"""
        if not self.connected or not self.voice_client:
            return False
        
        try:
            self.muted = not self.muted
            await self.voice_client.set_mute(self.muted)
            self.logger.info(f'Mikrofonas {"išjungtas" if self.muted else "įjungtas"}')
            return True
        except Exception as e:
            self.logger.error(f'Klaida perjungiant mikrofoną: {e}')
            return False
    
    async def toggle_deafen_async(self):
        """Asynchroninė funkcija garso perjungimui"""
        if not self.connected or not self.voice_client:
            return False
        
        try:
            self.deafened = not self.deafened
            await self.voice_client.set_deaf(self.deafened)
            self.logger.info(f'Garsas {"išjungtas" if self.deafened else "įjungtas"}')
            return True
        except Exception as e:
            self.logger.error(f'Klaida perjungiant garsą: {e}')
            return False
    
    def toggle_mute(self):
        """Perjungia mikrofono būseną (skirta iškvietimui iš Flask)"""
        if not self.connected:
            return {"success": False, "message": "Neprisijungta prie voice kanalo"}
        
        # Sukuriame naują event loop'ą
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.toggle_mute_async())
            if result:
                return {"success": True, "muted": self.muted}
            return {"success": False, "message": "Nepavyko perjungti mikrofono"}
        except Exception as e:
            self.logger.error(f'Klaida: {e}')
            return {"success": False, "message": str(e)}
        finally:
            loop.close()
    
    def toggle_deafen(self):
        """Perjungia garso būseną (skirta iškvietimui iš Flask)"""
        if not self.connected:
            return {"success": False, "message": "Neprisijungta prie voice kanalo"}
        
        # Sukuriame naują event loop'ą
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.toggle_deafen_async())
            if result:
                return {"success": True, "deafened": self.deafened}
            return {"success": False, "message": "Nepavyko perjungti garso"}
        except Exception as e:
            self.logger.error(f'Klaida: {e}')
            return {"success": False, "message": str(e)}
        finally:
            loop.close()
    
    def get_status(self):
        """Grąžina dabartinę būseną"""
        return {
            "connected": self.connected,
            "muted": self.muted,
            "deafened": self.deafened
        } 