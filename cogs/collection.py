import discord
from discord.ext import commands
from collections import defaultdict
import sys
import os

# Agregamos la ruta para poder importar utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.image_processor import PhotocardProcessor

class Collection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Inicializamos el procesador de imágenes
        self.image_processor = PhotocardProcessor()
    
    @commands.command(name='collection', aliases=['col', 'c'])
    async def view_collection(self, ctx, user: discord.Member = None):
        """Muestra la colección de photocards de un usuario"""
        target = user or ctx.author
        
        async with self.bot.db.execute('''
            SELECT p.group_name, p.member_name, p.era, p.rarity, COUNT(*) as quantity
            FROM user_cards uc
            JOIN photocards p ON uc.card_id = p.card_id
            WHERE uc.user_id = ?
            GROUP BY p.card_id
            ORDER BY p.rarity DESC, p.group_name, p.member_name
        ''', (target.id,)) as cursor:
            cards = await cursor.fetchall()
        
        if not cards:
            return await ctx.send(f"{'Tu' if target == ctx.author else f'{target.display_name}'} no tiene photocards todavía.")
        
        groups = defaultdict(list)
        total_cards = 0
        
        for group, member, era, rarity, qty in cards:
            groups[group].append({
                'member': member,
                'era': era or 'N/A',
                'rarity': rarity,
                'quantity': qty
            })
            total_cards += qty
        
        embeds = []
        rarity_emojis = {
            'Common': '⚪', 'Uncommon': '🟢', 'Rare': '🔵', 
            'Epic': '🟣', 'Legendary': '🟡'
        }
        
        for group_name, members in groups.items():
            embed = discord.Embed(
                title=f"📸 Colección de {target.display_name}",
                description=f"**{group_name}**",
                color=discord.Color.blue()
            )
            
            for card in members[:10]:
                rarity_emoji = rarity_emojis.get(card['rarity'], '⚪')
                embed.add_field(
                    name=f"{rarity_emoji} {card['member']}",
                    value=f"Era: {card['era']}\nCantidad: {card['quantity']}",
                    inline=True
                )
            
            embed.set_footer(text=f"Total de cartas: {total_cards}")
            embeds.append(embed)
        
        if embeds:
            await ctx.send(embed=embeds[0])
    
    @commands.command(name='inventory', aliases=['inv'])
    async def inventory(self, ctx):
        """Muestra un resumen de tu inventario"""
        async with self.bot.db.execute('''
            SELECT COUNT(DISTINCT uc.card_id), COUNT(*), u.coins, u.drops_count
            FROM users u
            LEFT JOIN user_cards uc ON u.user_id = uc.user_id
            WHERE u.user_id = ?
        ''', (ctx.author.id,)) as cursor:
            data = await cursor.fetchone()
        
        if not data:
            return await ctx.send("No tienes un inventario todavía.")
        
        unique, total, coins, drops = data
        
        async with self.bot.db.execute('''
            SELECT p.rarity, COUNT(*) as count
            FROM user_cards uc
            JOIN photocards p ON uc.card_id = p.card_id
            WHERE uc.user_id = ?
            GROUP BY p.rarity
        ''', (ctx.author.id,)) as cursor:
            rarity_counts = await cursor.fetchall()
        
        embed = discord.Embed(
            title=f"🎒 Inventario de {ctx.author.display_name}",
            color=discord.Color.purple()
        )
        
        embed.add_field(name="💳 Total de Cartas", value=total or 0, inline=True)
        embed.add_field(name="✨ Cartas Únicas", value=unique or 0, inline=True)
        embed.add_field(name="🪙 Monedas", value=coins or 0, inline=True)
        embed.add_field(name="📊 Drops Reclamados", value=drops or 0, inline=True)
        
        if rarity_counts:
            rarity_text = "\n".join([f"{rarity}: {count}" for rarity, count in rarity_counts])
            embed.add_field(name="📈 Por Rareza", value=rarity_text, inline=False)
        
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='view', aliases=['v', 'show'])
    async def view_card(self, ctx, *, search: str):
        """Busca y muestra la imagen de una photocard específica"""
        
        # 1. Buscamos la carta con todos los datos necesarios para dibujarla
        # Agregamos 'card_number' y 'series' a la consulta
        async with self.bot.db.execute('''
            SELECT card_id, card_number, group_name, member_name, era, rarity, image_path, series
            FROM photocards
            WHERE LOWER(member_name) LIKE ? OR LOWER(group_name) LIKE ?
            LIMIT 1
        ''', (f'%{search.lower()}%', f'%{search.lower()}%')) as cursor:
            result = await cursor.fetchone()
        
        if not result:
            return await ctx.send(f"❌ No se encontraron photocards con '{search}'")
        
        # Desempaquetamos los datos
        card_id, card_number, group, member, era, rarity, img_path, series = result
        
        # 2. Verificamos si el usuario la tiene (para mostrar info de posesión)
        async with self.bot.db.execute('''
            SELECT COUNT(*) FROM user_cards
            WHERE user_id = ? AND card_id = ?
        ''', (ctx.author.id, card_id)) as cursor:
            owned_count = (await cursor.fetchone())[0]
        
        # 3. Generamos la imagen
        try:
            img_bytes = self.image_processor.create_photocard(
                img_path,
                {
                    'rarity': rarity,
                    'card_number': card_number,
                    'member': member,
                    'group': group,
                    'era': era,
                    'series': series if series else 'S1',
                    'serial': None # No mostramos serial en una vista genérica
                }
            )
        except Exception as e:
            print(f"Error generando imagen en view: {e}")
            return await ctx.send("❌ Error generando la imagen de la carta.")

        # 4. Creamos el Embed y enviamos la imagen
        rarity_colors = {
            'Common': discord.Color.light_gray(), 'Uncommon': discord.Color.green(),
            'Rare': discord.Color.blue(), 'Epic': discord.Color.purple(),
            'Legendary': discord.Color.gold()
        }
        
        embed = discord.Embed(
            title=f"{member} - {group}",
            description=f"**Era:** {era or 'N/A'}\n**Rareza:** {rarity}",
            color=rarity_colors.get(rarity, discord.Color.default())
        )
        
        if owned_count > 0:
            embed.add_field(name="📦 En inventario", value=f"Tienes **{owned_count}** copias")
        else:
            embed.add_field(name="📦 En inventario", value="No tienes esta carta")
            
        embed.set_footer(text=f"ID: {card_number} | Serie: {series or 'S1'}")
        
        # Adjuntamos el archivo
        filename = "card_view.png"
        file = discord.File(img_bytes, filename=filename)
        embed.set_image(url=f"attachment://{filename}")
        
        await ctx.send(embed=embed, file=file)
    
    @commands.command(name='gift')
    async def gift_card(self, ctx, user: discord.Member, card_id: int):
        """Regala una photocard a otro usuario"""
        if user.bot or user == ctx.author:
            return await ctx.send("❌ Destinatario inválido.")
        
        async with self.bot.db.execute('''
            SELECT uc.id, p.group_name, p.member_name, p.rarity
            FROM user_cards uc
            JOIN photocards p ON uc.card_id = p.card_id
            WHERE uc.user_id = ? AND uc.card_id = ?
            LIMIT 1
        ''', (ctx.author.id, card_id)) as cursor:
            card_data = await cursor.fetchone()
        
        if not card_data:
            return await ctx.send("❌ No tienes esta carta (o el ID es incorrecto).")
        
        user_card_id, group, member, rarity = card_data
        
        await self.bot.db.execute('DELETE FROM user_cards WHERE id = ?', (user_card_id,))
        await self.bot.db.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user.id,))
        await self.bot.db.execute('INSERT INTO user_cards (user_id, card_id) VALUES (?, ?)', (user.id, card_id))
        await self.bot.db.commit()
        
        embed = discord.Embed(
            title="🎁 Regalo enviado!",
            description=f"{ctx.author.mention} le regaló **{member}** ({group}) a {user.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Collection(bot))