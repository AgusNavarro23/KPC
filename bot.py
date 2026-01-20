import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import aiosqlite

load_dotenv()

# Configuración de intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class KpopPhotocardBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=os.getenv('PREFIX', 'k!'),
            intents=intents,
            help_command=None
        )
        self.db = None
        
    async def setup_hook(self):
        # Inicializar base de datos
        self.db = await aiosqlite.connect('kpop_bot.db')
        await self.init_db()
        
        # Cargar cogs
        await self.load_extension('cogs.gacha')
        await self.load_extension('cogs.collection')
        await self.load_extension('cogs.economy')
        
        print("Bot inicializado correctamente")
    
    async def init_db(self):
        """Inicializa las tablas de la base de datos"""
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 0,
                drops_count INTEGER DEFAULT 0,
                last_daily TIMESTAMP
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS photocards (
                card_id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_number TEXT NOT NULL UNIQUE,
                group_name TEXT NOT NULL,
                member_name TEXT NOT NULL,
                era TEXT,
                rarity TEXT,
                image_path TEXT,
                series TEXT DEFAULT 'S1'
            )
        ''')
        
        await self.db.execute('''
            CREATE TABLE IF NOT EXISTS user_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                card_id INTEGER,
                obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                card_serial TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (card_id) REFERENCES photocards(card_id)
            )
        ''')
        
        await self.db.commit()
    
    async def on_ready(self):
        print(f'{self.user} ha iniciado sesión')
        print(f'ID: {self.user.id}')
        await self.change_presence(
            activity=discord.Game(name=f"{self.command_prefix}help | Colecciona photocards!")
        )
    
    async def close(self):
        await self.db.close()
        await super().close()

async def main():
    bot = KpopPhotocardBot()
    async with bot:
        await bot.start(os.getenv('DISCORD_TOKEN'))

if __name__ == '__main__':
    asyncio.run(main())