import discord
from discord.ext import commands, tasks
import random
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import os

# Agregar path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.image_processor import PhotocardProcessor

class Gacha(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spawn_channels = {}
        self.active_drops = {}
        self.grab_cooldowns = defaultdict(datetime)
        self.drop_cooldowns = defaultdict(datetime)
        self.auto_spawn.start()
        self.image_processor = PhotocardProcessor()
        
        self.rarities = {
            'Common': 0.50, 'Uncommon': 0.30, 'Rare': 0.15, 'Epic': 0.04, 'Legendary': 0.01
        }
        
        self.DROP_COOLDOWN = 900
        self.GRAB_COOLDOWN = 300
        self.DROP_EXPIRE_TIME = 45

    def cog_unload(self):
        self.auto_spawn.cancel()

    # ... [Métodos auto_spawn, before_auto_spawn, get_random_cards iguales que antes] ...
    # (Omito el código repetido para ahorrar espacio, asegúrate de mantener get_random_cards y auto_spawn)

    # Copia aquí tus métodos get_random_cards, auto_spawn y before_auto_spawn del archivo original...
    
    @tasks.loop(minutes=10)
    async def auto_spawn(self):
        # (Lógica original)
        for channel_id in list(self.spawn_channels.keys()):
            if channel_id in self.drop_cooldowns:
                time_since_drop = (datetime.utcnow() - self.drop_cooldowns[channel_id]).total_seconds()
                if time_since_drop < self.DROP_COOLDOWN:
                    continue
            if channel_id not in self.active_drops:
                channel = self.bot.get_channel(channel_id)
                if channel and random.random() < 0.6:
                    await self.spawn_card(channel)
    
    @auto_spawn.before_loop
    async def before_auto_spawn(self):
        await self.bot.wait_until_ready()

    async def get_random_cards(self, count=3):
        # (Lógica original, sin cambios)
        cards = []
        for _ in range(count):
            rand = random.random()
            cumulative = 0
            selected_rarity = 'Common'
            for rarity, prob in self.rarities.items():
                cumulative += prob
                if rand <= cumulative:
                    selected_rarity = rarity
                    break
            async with self.bot.db.execute('SELECT * FROM photocards WHERE rarity = ? ORDER BY RANDOM() LIMIT 1', (selected_rarity,)) as cursor:
                row = await cursor.fetchone()
            if row:
                cards.append({
                    'card_id': row[0], 'card_number': row[1], 'group': row[2],
                    'member': row[3], 'era': row[4], 'rarity': row[5],
                    'image_path': row[6], 'series': row[7] if len(row) > 7 else 'S1'
                })
        return cards

    async def spawn_card(self, channel):
        cards = await self.get_random_cards(3)
        if not cards or len(cards) < 3: return
        
        self.drop_cooldowns[channel.id] = datetime.utcnow()
        
        card_images = []
        for card in cards:
            try:
                # Pasamos los datos para generar la imagen
                img_bytes = self.image_processor.create_photocard(
                    card['image_path'],
                    {
                        'rarity': card['rarity'],
                        'card_number': card['card_number'],
                        'member': card['member'],
                        'group': card['group'],
                        'era': card['era'],
                        'serial': None # Drop genérico, sin serial aún
                    }
                )
                card_images.append(img_bytes)
            except Exception as e:
                print(f"Error generando imagen: {e}")
                card_images.append(None)
        
        # ... [Resto del código de spawn_card igual: Crear embeds, enviar archivos, reacciones] ...
        # (Lógica original de embed)
        rarity_colors = {'Common': discord.Color.light_gray(), 'Uncommon': discord.Color.green(), 'Rare': discord.Color.blue(), 'Epic': discord.Color.purple(), 'Legendary': discord.Color.gold()}
        rarity_order = ['Common', 'Uncommon', 'Rare', 'Epic', 'Legendary']
        highest_rarity = max(cards, key=lambda c: rarity_order.index(c['rarity']))['rarity']
        
        embed = discord.Embed(title="✨ 3 Photocards han aparecido! ✨", description=f"Reacciona con 1️⃣, 2️⃣ o 3️⃣ para elegir una carta!\n⏰ Tienes {self.DROP_EXPIRE_TIME} segundos", color=rarity_colors.get(highest_rarity, discord.Color.default()))
        
        number_emojis = ['1️⃣', '2️⃣', '3️⃣']
        rarity_emojis = {'Common': '⚪', 'Uncommon': '🟢', 'Rare': '🔵', 'Epic': '🟣', 'Legendary': '🟡'}
        
        for i, card in enumerate(cards):
            rarity_emoji = rarity_emojis.get(card['rarity'], '⚪')
            embed.add_field(name=f"{number_emojis[i]} {rarity_emoji} {card['member']}", value=f"**{card['group']}**\n{card['era'] or 'N/A'}\n`{card['rarity']}`", inline=True)
            
        embed.timestamp = datetime.utcnow()
        
        files = []
        if all(card_images):
            try:
                grid = self.image_processor.create_card_grid(card_images, cols=3)
                if grid:
                    files.append(discord.File(grid, filename='photocards.png'))
                    embed.set_image(url='attachment://photocards.png')
            except Exception as e:
                print(f"Error creando grid: {e}")
        
        if files: msg = await channel.send(embed=embed, files=files)
        else: msg = await channel.send(embed=embed)
        
        for emoji in number_emojis: await msg.add_reaction(emoji)
        
        self.active_drops[channel.id] = {'cards': cards, 'message_id': msg.id, 'message': msg, 'expires_at': datetime.utcnow() + timedelta(seconds=self.DROP_EXPIRE_TIME), 'claimed': False}
        
        await asyncio.sleep(self.DROP_EXPIRE_TIME)
        if channel.id in self.active_drops and not self.active_drops[channel.id]['claimed']:
            del self.active_drops[channel.id]
            try:
                await msg.clear_reactions()
                await msg.edit(embed=discord.Embed(title="⏰ Expirado", description="Nadie reclamó a tiempo.", color=discord.Color.dark_gray()))
            except: pass

    # ... [Método on_reaction_add igual que el original] ...
    # Asegúrate de mantenerlo para que funcione el grab

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # (Código original de on_reaction_add)
        if user.bot: return
        if reaction.message.channel.id not in self.active_drops: return
        drop_data = self.active_drops[reaction.message.channel.id]
        if reaction.message.id != drop_data['message_id']: return
        if drop_data['claimed']: return
        
        # Check Cooldown
        if user.id in self.grab_cooldowns:
            time_since_grab = (datetime.utcnow() - self.grab_cooldowns[user.id]).total_seconds()
            if time_since_grab < self.GRAB_COOLDOWN:
                try: await reaction.remove(user)
                except: pass
                return
                
        if datetime.utcnow() > drop_data['expires_at']:
            del self.active_drops[reaction.message.channel.id]
            return
            
        emoji_to_index = {'1️⃣': 0, '2️⃣': 1, '3️⃣': 2}
        if str(reaction.emoji) not in emoji_to_index: return
        
        card_index = emoji_to_index[str(reaction.emoji)]
        selected_card = drop_data['cards'][card_index]
        drop_data['claimed'] = True
        
        self.grab_cooldowns[user.id] = datetime.utcnow()
        
        # DB Logic
        await self.bot.db.execute('INSERT OR IGNORE INTO users (user_id, coins, drops_count) VALUES (?, 0, 0)', (user.id,))
        card_serial = f"{selected_card['card_number']}-{int(datetime.utcnow().timestamp())}-{user.id % 1000}"
        await self.bot.db.execute('INSERT INTO user_cards (user_id, card_id, card_serial) VALUES (?, ?, ?)', (user.id, selected_card['card_id'], card_serial))
        await self.bot.db.execute('UPDATE users SET drops_count = drops_count + 1 WHERE user_id = ?', (user.id,))
        await self.bot.db.commit()
        
        del self.active_drops[reaction.message.channel.id]
        
        # Confirmación
        await reaction.message.channel.send(f"🎉 {user.mention} reclamó a **{selected_card['member']}**!")
        try: await drop_data['message'].delete()
        except: pass

    # ... [Comandos drop, dropchannel, removedropchannel iguales] ...

    @commands.command(name='drop', aliases=['spawn'])
    async def force_drop(self, ctx):
        if ctx.channel.id in self.active_drops: return await ctx.send("❌ Drop activo.")
        if ctx.channel.id in self.drop_cooldowns:
            time_since = (datetime.utcnow() - self.drop_cooldowns[ctx.channel.id]).total_seconds()
            if time_since < self.DROP_COOLDOWN and not ctx.author.guild_permissions.administrator:
                remaining = int(self.DROP_COOLDOWN - time_since)
                return await ctx.send(f"⏳ Cooldown del canal: {remaining // 60}m {remaining % 60}s")
        await self.spawn_card(ctx.channel)

    @commands.command(name='dropchannel')
    @commands.has_permissions(administrator=True)
    async def set_drop_channel(self, ctx):
        self.spawn_channels[ctx.channel.id] = datetime.utcnow()
        await ctx.send("✅ Canal configurado para drops.")

    @commands.command(name='removedropchannel')
    @commands.has_permissions(administrator=True)
    async def remove_drop_channel(self, ctx):
        if ctx.channel.id in self.spawn_channels:
            del self.spawn_channels[ctx.channel.id]
            await ctx.send("✅ Canal removido.")
        else: await ctx.send("❌ No configurado.")

    @commands.command(name='cooldown', aliases=['cd'])
    async def check_cooldown(self, ctx):
        """Muestra cooldown de Grab (usuario) y Drop (canal)"""
        embed = discord.Embed(title="⏰ Estado de Cooldowns", color=discord.Color.orange())
        
        # 1. Grab Cooldown (Usuario)
        if ctx.author.id in self.grab_cooldowns:
            time_since = (datetime.utcnow() - self.grab_cooldowns[ctx.author.id]).total_seconds()
            if time_since < self.GRAB_COOLDOWN:
                rem = self.GRAB_COOLDOWN - time_since
                embed.add_field(name="✋ Grab (Tú)", value=f"**{int(rem // 60)}m {int(rem % 60)}s**", inline=True)
            else:
                embed.add_field(name="✋ Grab (Tú)", value="✅ ¡Listo!", inline=True)
        else:
            embed.add_field(name="✋ Grab (Tú)", value="✅ ¡Listo!", inline=True)
            
        # 2. Drop Cooldown (Canal)
        if ctx.channel.id in self.drop_cooldowns:
            time_since = (datetime.utcnow() - self.drop_cooldowns[ctx.channel.id]).total_seconds()
            if time_since < self.DROP_COOLDOWN:
                rem = self.DROP_COOLDOWN - time_since
                embed.add_field(name="🎲 Drop (Canal)", value=f"**{int(rem // 60)}m {int(rem % 60)}s**", inline=True)
            else:
                embed.add_field(name="🎲 Drop (Canal)", value="✅ ¡Listo!", inline=True)
        else:
            embed.add_field(name="🎲 Drop (Canal)", value="✅ ¡Listo!", inline=True)
            
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Gacha(bot))