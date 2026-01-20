import discord
from discord.ext import commands, tasks
import random
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import os
import time  # Importación necesaria para el serial

# Agregar la carpeta utils al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.image_processor import PhotocardProcessor

class Gacha(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spawn_channels = {}  # {channel_id: cooldown_time}
        self.active_drops = {}    # {channel_id: {cards: [], message_id, expires_at}}
        self.grab_cooldowns = defaultdict(datetime)  # {user_id: last_grab_time}
        self.drop_cooldowns = defaultdict(datetime)  # {channel_id: last_drop_time}
        self.auto_spawn.start()
        self.image_processor = PhotocardProcessor()  # Procesador de imágenes
        
        # Raridades y sus probabilidades
        self.rarities = {
            'Common': 0.50,      # 50%
            'Uncommon': 0.30,    # 30%
            'Rare': 0.15,        # 15%
            'Epic': 0.04,        # 4%
            'Legendary': 0.01    # 1%
        }
        
        # Cooldowns en segundos
        self.DROP_COOLDOWN = 900   # 15 minutos
        self.GRAB_COOLDOWN = 300   # 5 minutos
        self.DROP_EXPIRE_TIME = 45 # 45 segundos para elegir
    
    def cog_unload(self):
        self.auto_spawn.cancel()
    
    @tasks.loop(minutes=10)
    async def auto_spawn(self):
        """Genera drops automáticamente cada 10 minutos"""
        for channel_id in list(self.spawn_channels.keys()):
            # Verificar cooldown del canal
            if channel_id in self.drop_cooldowns:
                time_since_drop = (datetime.utcnow() - self.drop_cooldowns[channel_id]).total_seconds()
                if time_since_drop < self.DROP_COOLDOWN:
                    continue
            
            if channel_id not in self.active_drops:
                channel = self.bot.get_channel(channel_id)
                if channel and random.random() < 0.6:  # 60% de probabilidad
                    await self.spawn_card(channel)
    
    @auto_spawn.before_loop
    async def before_auto_spawn(self):
        await self.bot.wait_until_ready()
    
    async def get_random_cards(self, count=3):
        """Obtiene múltiples photocards aleatorias de la base de datos"""
        cards = []
        
        for _ in range(count):
            # Determinar raridad basada en probabilidades
            rand = random.random()
            cumulative = 0
            selected_rarity = 'Common'
            
            for rarity, prob in self.rarities.items():
                cumulative += prob
                if rand <= cumulative:
                    selected_rarity = rarity
                    break
            
            # Obtener una carta de esa raridad
            async with self.bot.db.execute(
                'SELECT * FROM photocards WHERE rarity = ? ORDER BY RANDOM() LIMIT 1',
                (selected_rarity,)
            ) as cursor:
                row = await cursor.fetchone()
                
            if row:
                cards.append({
                    'card_id': row[0],
                    'card_number': row[1],
                    'group': row[2],
                    'member': row[3],
                    'era': row[4],
                    'rarity': row[5],
                    'image_path': row[6],
                    'series': row[7] if len(row) > 7 else 'S1'
                })
        
        return cards
    
    async def spawn_card(self, channel):
        """Genera un drop de 3 photocards en el canal"""
        cards = await self.get_random_cards(3)
        if not cards or len(cards) < 3:
            return
        
        # Registrar cooldown del canal
        self.drop_cooldowns[channel.id] = datetime.utcnow()
        
        # Generar imágenes de las 3 cartas
        card_images = []
        for card in cards:
            try:
                img_bytes = self.image_processor.create_photocard(
                    card['image_path'],
                    {
                        'rarity': card['rarity'],
                        'card_number': card['card_number'],
                        'member': card['member'],
                        'group': card['group'],
                        'era': card['era'],
                        'series': card.get('series', 'S1')
                    }
                )
                card_images.append(img_bytes)
            except Exception as e:
                print(f"Error generando imagen: {e}")
                # Continuar sin imagen si hay error
                card_images.append(None)
        
        # Crear embed
        rarity_colors = {
            'Common': discord.Color.light_gray(),
            'Uncommon': discord.Color.green(),
            'Rare': discord.Color.blue(),
            'Epic': discord.Color.purple(),
            'Legendary': discord.Color.gold()
        }
        
        # Determinar color basado en la carta de mayor rareza
        rarity_order = ['Common', 'Uncommon', 'Rare', 'Epic', 'Legendary']
        highest_rarity = max(cards, key=lambda c: rarity_order.index(c['rarity']))['rarity']
        
        embed = discord.Embed(
            title="✨ 3 Photocards han aparecido! ✨",
            description=f"Reacciona con 1️⃣, 2️⃣ o 3️⃣ para elegir una carta!\n⏰ Tienes {self.DROP_EXPIRE_TIME} segundos",
            color=rarity_colors.get(highest_rarity, discord.Color.default())
        )
        
        # Emojis de rareza
        rarity_emojis = {
            'Common': '⚪',
            'Uncommon': '🟢',
            'Rare': '🔵',
            'Epic': '🟣',
            'Legendary': '🟡'
        }
        
        # Agregar las 3 cartas
        number_emojis = ['1️⃣', '2️⃣', '3️⃣']
        for i, card in enumerate(cards):
            rarity_emoji = rarity_emojis.get(card['rarity'], '⚪')
            card_num = card.get('card_number', 'N/A')
            series = card.get('series', 'S1')
            embed.add_field(
                name=f"{number_emojis[i]} {rarity_emoji} {card['member']}",
                value=f"**{card['group']}**\n{card['era'] or 'N/A'}\n`{series}-{card_num}` • `{card['rarity']}`",
                inline=True
            )
        
        embed.set_footer(text=f"Cooldown de grab: 5 min | Cooldown de drop: 15 min")
        embed.timestamp = datetime.utcnow()
        
        # Enviar mensaje con imagen(s)
        files = []
        if all(card_images):
            # Si todas las imágenes se generaron, crear una cuadrícula
            try:
                grid = self.image_processor.create_card_grid(card_images, cols=3)
                if grid:
                    files.append(discord.File(grid, filename='photocards.png'))
                    embed.set_image(url='attachment://photocards.png')
            except Exception as e:
                print(f"Error creando grid: {e}")
        
        if files:
            msg = await channel.send(embed=embed, files=files)
        else:
            msg = await channel.send(embed=embed)
        
        # Agregar reacciones
        for emoji in number_emojis:
            await msg.add_reaction(emoji)
        
        # Guardar drop activo
        self.active_drops[channel.id] = {
            'cards': cards,
            'message_id': msg.id,
            'message': msg,
            'expires_at': datetime.utcnow() + timedelta(seconds=self.DROP_EXPIRE_TIME),
            'claimed': False
        }
        
        # Auto-eliminar después del tiempo límite
        await asyncio.sleep(self.DROP_EXPIRE_TIME)
        if channel.id in self.active_drops and not self.active_drops[channel.id]['claimed']:
            del self.active_drops[channel.id]
            
            expire_embed = discord.Embed(
                title="⏰ El tiempo ha expirado",
                description="Las photocards han desaparecido...",
                color=discord.Color.dark_gray()
            )
            
            try:
                await msg.clear_reactions()
                await msg.edit(embed=expire_embed)
            except:
                pass
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Detecta cuando un usuario reacciona para elegir una carta"""
        # Ignorar bots
        if user.bot:
            return
        
        # Verificar si hay un drop activo en este canal
        if reaction.message.channel.id not in self.active_drops:
            return
        
        drop_data = self.active_drops[reaction.message.channel.id]
        
        # Verificar que sea el mensaje correcto
        if reaction.message.id != drop_data['message_id']:
            return
        
        # Verificar que la carta no haya sido reclamada
        if drop_data['claimed']:
            return
        
        # Verificar cooldown del usuario
        if user.id in self.grab_cooldowns:
            time_since_grab = (datetime.utcnow() - self.grab_cooldowns[user.id]).total_seconds()
            if time_since_grab < self.GRAB_COOLDOWN:
                remaining = self.GRAB_COOLDOWN - time_since_grab
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                
                try:
                    await user.send(
                        f"⏰ **Cooldown activo!**\n"
                        f"Debes esperar {minutes}m {seconds}s antes de reclamar otra photocard."
                    )
                except:
                    pass
                
                # Remover la reacción
                try:
                    await reaction.remove(user)
                except:
                    pass
                return
        
        # Verificar si ya expiró
        if datetime.utcnow() > drop_data['expires_at']:
            del self.active_drops[reaction.message.channel.id]
            return
        
        # Mapear emoji a índice de carta
        emoji_to_index = {
            '1️⃣': 0,
            '2️⃣': 1,
            '3️⃣': 2
        }
        
        if str(reaction.emoji) not in emoji_to_index:
            try:
                await reaction.remove(user)
            except:
                pass
            return
        
        card_index = emoji_to_index[str(reaction.emoji)]
        selected_card = drop_data['cards'][card_index]
        
        # Marcar como reclamada
        drop_data['claimed'] = True
        
        # Registrar cooldown del usuario
        self.grab_cooldowns[user.id] = datetime.utcnow()
        
        # Registrar usuario si no existe
        await self.bot.db.execute(
            'INSERT OR IGNORE INTO users (user_id, coins, drops_count) VALUES (?, 0, 0)',
            (user.id,)
        )
        
        # Generar número serial único para esta instancia de la carta
        card_serial = f"{selected_card['card_number']}-{int(time.time())}-{user.id % 10000}"
        
        # Agregar carta a la colección del usuario
        await self.bot.db.execute(
            'INSERT INTO user_cards (user_id, card_id, card_serial) VALUES (?, ?, ?)',
            (user.id, selected_card['card_id'], card_serial)
        )
        
        # Actualizar contador de drops
        await self.bot.db.execute(
            'UPDATE users SET drops_count = drops_count + 1 WHERE user_id = ?',
            (user.id,)
        )
        
        await self.bot.db.commit()
        
        # Eliminar el drop activo
        del self.active_drops[reaction.message.channel.id]
        
        # Actualizar el mensaje original
        rarity_colors = {
            'Common': discord.Color.light_gray(),
            'Uncommon': discord.Color.green(),
            'Rare': discord.Color.blue(),
            'Epic': discord.Color.purple(),
            'Legendary': discord.Color.gold()
        }
        
        claim_embed = discord.Embed(
            title="🎉 Photocard reclamada!",
            description=f"{user.mention} eligió la carta {card_index + 1}!",
            color=rarity_colors.get(selected_card['rarity'], discord.Color.green())
        )
        claim_embed.add_field(name="📝 Número", value=f"`{selected_card.get('series', 'S1')}-{selected_card.get('card_number', 'N/A')}`", inline=True)
        claim_embed.add_field(name="👤 Miembro", value=selected_card['member'], inline=True)
        claim_embed.add_field(name="🎤 Grupo", value=selected_card['group'], inline=True)
        claim_embed.add_field(name="✨ Rareza", value=selected_card['rarity'], inline=True)
        
        if selected_card['era']:
            claim_embed.add_field(name="🎵 Era", value=selected_card['era'], inline=True)
        
        claim_embed.add_field(name="🔖 Serial", value=f"`{card_serial}`", inline=True)
        claim_embed.set_footer(text=f"Próximo grab disponible en 5 minutos")
        
        # -------------------------------------------------------------
        # NUEVO: Enviar mensaje nuevo al canal confirmando el grab
        # -------------------------------------------------------------
        try:
            rarity_emojis = {'Common': '⚪', 'Uncommon': '🟢', 'Rare': '🔵', 'Epic': '🟣', 'Legendary': '🟡'}
            emoji = rarity_emojis.get(selected_card['rarity'], '✨')
            
            await reaction.message.channel.send(
                f"🎉 **¡Felicidades {user.mention}!** Has reclamado a **{selected_card['member']}** del grupo **{selected_card['group']}**! {emoji}"
            )
        except Exception as e:
            print(f"No se pudo enviar mensaje de confirmación: {e}")

        try:
            await drop_data['message'].clear_reactions()
            await drop_data['message'].edit(embed=claim_embed)
        except:
            pass
    
    @commands.command(name='grab', aliases=['g', 'claim'])
    async def grab_card(self, ctx):
        """COMANDO OBSOLETO - Ahora usa reacciones para reclamar cartas"""
        await ctx.send(
            "ℹ️ **Sistema actualizado!**\n"
            "Ahora debes reaccionar con 1️⃣, 2️⃣ o 3️⃣ en el mensaje del drop para elegir tu carta.\n"
            "Este comando ya no está disponible."
        )
    
    @commands.command(name='drop', aliases=['spawn'])
    # Se eliminó el permiso de administrador para que todos puedan usarlo
    async def force_drop(self, ctx):
        """Fuerza un drop en el canal (respeta cooldown para usuarios, admin puede forzar)"""
        
        # Verificar si ya hay un drop activo
        if ctx.channel.id in self.active_drops:
            return await ctx.send("❌ Ya hay un drop activo en este canal. Espera a que termine.")
        
        # Lógica de Cooldown
        if ctx.channel.id in self.drop_cooldowns:
            time_since = (datetime.utcnow() - self.drop_cooldowns[ctx.channel.id]).total_seconds()
            
            if time_since < self.DROP_COOLDOWN:
                # Si el usuario es admin, puede saltarse el cooldown
                if ctx.author.guild_permissions.administrator:
                    remaining = self.DROP_COOLDOWN - time_since
                    minutes = int(remaining // 60)
                    await ctx.send(f"⚠️ Cooldown activo ({minutes} min restantes), pero forzando drop como admin...")
                else:
                    # Si es usuario normal, se le bloquea
                    remaining = self.DROP_COOLDOWN - time_since
                    minutes = int(remaining // 60)
                    seconds = int(remaining % 60)
                    return await ctx.send(f"⏳ **El canal está en enfriamiento.**\nPróximo drop disponible en: **{minutes}m {seconds}s**")
        
        await self.spawn_card(ctx.channel)
    
    @commands.command(name='dropchannel')
    @commands.has_permissions(administrator=True)
    async def set_drop_channel(self, ctx):
        """Establece el canal actual como canal de drops"""
        self.spawn_channels[ctx.channel.id] = datetime.utcnow()
        await ctx.send(
            f"✅ Este canal ahora recibirá drops automáticos de photocards!\n"
            f"🔄 Frecuencia: cada 10 minutos (60% probabilidad)\n"
            f"⏰ Cooldown entre drops: 15 minutos"
        )
    
    @commands.command(name='removedropchannel')
    @commands.has_permissions(administrator=True)
    async def remove_drop_channel(self, ctx):
        """Remueve el canal actual de los canales de drops"""
        if ctx.channel.id in self.spawn_channels:
            del self.spawn_channels[ctx.channel.id]
            await ctx.send("✅ Canal removido de los drops automáticos.")
        else:
            await ctx.send("❌ Este canal no está configurado para drops.")
    
    @commands.command(name='cooldown', aliases=['cd'])
    async def check_cooldown(self, ctx):
        """Verifica tu cooldown de grab"""
        if ctx.author.id not in self.grab_cooldowns:
            return await ctx.send("✅ No tienes cooldown activo. ¡Puedes reclamar cartas!")
        
        time_since = (datetime.utcnow() - self.grab_cooldowns[ctx.author.id]).total_seconds()
        
        if time_since >= self.GRAB_COOLDOWN:
            return await ctx.send("✅ Tu cooldown ha expirado. ¡Puedes reclamar cartas!")
        
        remaining = self.GRAB_COOLDOWN - time_since
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        
        embed = discord.Embed(
            title="⏰ Cooldown de Grab",
            description=f"Tiempo restante: **{minutes}m {seconds}s**",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Podrás reclamar otra photocard cuando el cooldown expire")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='dropinfo')
    async def drop_info(self, ctx):
        """Muestra información sobre el sistema de drops"""
        embed = discord.Embed(
            title="📋 Sistema de Drops",
            description="Información sobre cómo funcionan los drops de photocards",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎲 Drops Automáticos",
            value="• Cada 10 minutos en canales configurados\n• 60% de probabilidad de spawn\n• 15 minutos de cooldown entre drops",
            inline=False
        )
        
        embed.add_field(
            name="🎯 Cómo Reclamar",
            value="• Aparecen 3 cartas por drop\n• Reacciona con 1️⃣, 2️⃣ o 3️⃣ para elegir\n• Tienes 45 segundos para decidir\n• Escribe `!drop` para invocar cartas (si no hay cooldown)",
            inline=False
        )
        
        embed.add_field(
            name="⏰ Cooldowns",
            value=f"• **Grab:** {self.GRAB_COOLDOWN // 60} minutos\n• **Drop:** {self.DROP_COOLDOWN // 60} minutos",
            inline=False
        )
        
        embed.add_field(
            name="📊 Raridades",
            value="⚪ Common (50%)\n🟢 Uncommon (30%)\n🔵 Rare (15%)\n🟣 Epic (4%)\n🟡 Legendary (1%)",
            inline=False
        )
        
        # Verificar si hay un drop activo
        if ctx.channel.id in self.active_drops:
            drop = self.active_drops[ctx.channel.id]
            remaining = (drop['expires_at'] - datetime.utcnow()).total_seconds()
            if remaining > 0:
                embed.add_field(
                    name="🔴 Drop Activo en Este Canal",
                    value=f"Quedan {int(remaining)} segundos",
                    inline=False
                )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Gacha(bot))