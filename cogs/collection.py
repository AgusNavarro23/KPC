import discord
from discord.ext import commands
from collections import defaultdict

class Collection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='collection', aliases=['col', 'c'])
    async def view_collection(self, ctx, user: discord.Member = None):
        """Muestra la colección de photocards de un usuario"""
        target = user or ctx.author
        
        # Obtener todas las cartas del usuario
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
        
        # Agrupar por grupo
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
        
        # Crear embeds paginados
        embeds = []
        rarity_emojis = {
            'Common': '⚪',
            'Uncommon': '🟢',
            'Rare': '🔵',
            'Epic': '🟣',
            'Legendary': '🟡'
        }
        
        for group_name, members in groups.items():
            embed = discord.Embed(
                title=f"📸 Colección de {target.display_name}",
                description=f"**{group_name}**",
                color=discord.Color.blue()
            )
            
            for card in members[:10]:  # Máximo 10 por página
                rarity_emoji = rarity_emojis.get(card['rarity'], '⚪')
                embed.add_field(
                    name=f"{rarity_emoji} {card['member']}",
                    value=f"Era: {card['era']}\nCantidad: {card['quantity']}",
                    inline=True
                )
            
            embed.set_footer(text=f"Total de cartas: {total_cards}")
            embeds.append(embed)
        
        # Enviar primera página
        if embeds:
            await ctx.send(embed=embeds[0])
    
    @commands.command(name='inventory', aliases=['inv'])
    async def inventory(self, ctx):
        """Muestra un resumen de tu inventario"""
        async with self.bot.db.execute('''
            SELECT 
                COUNT(DISTINCT uc.card_id) as unique_cards,
                COUNT(*) as total_cards,
                u.coins,
                u.drops_count
            FROM users u
            LEFT JOIN user_cards uc ON u.user_id = uc.user_id
            WHERE u.user_id = ?
        ''', (ctx.author.id,)) as cursor:
            data = await cursor.fetchone()
        
        if not data:
            return await ctx.send("No tienes un inventario todavía. ¡Empieza a coleccionar!")
        
        unique, total, coins, drops = data
        
        # Obtener raridades
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
        
        # Agregar contador por rareza
        if rarity_counts:
            rarity_text = "\n".join([f"{rarity}: {count}" for rarity, count in rarity_counts])
            embed.add_field(name="📈 Por Rareza", value=rarity_text, inline=False)
        
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        
        await ctx.send(embed=embed)
    
    @commands.command(name='view', aliases=['v'])
    async def view_card(self, ctx, *, search: str):
        """Busca y muestra información de una photocard específica"""
        # Buscar por nombre de miembro o grupo
        async with self.bot.db.execute('''
            SELECT card_id, group_name, member_name, era, rarity, image_path
            FROM photocards
            WHERE LOWER(member_name) LIKE ? OR LOWER(group_name) LIKE ?
            LIMIT 5
        ''', (f'%{search.lower()}%', f'%{search.lower()}%')) as cursor:
            results = await cursor.fetchall()
        
        if not results:
            return await ctx.send(f"❌ No se encontraron photocards con '{search}'")
        
        # Mostrar resultados
        for card_id, group, member, era, rarity, img_path in results:
            # Verificar si el usuario tiene esta carta
            async with self.bot.db.execute('''
                SELECT COUNT(*) FROM user_cards
                WHERE user_id = ? AND card_id = ?
            ''', (ctx.author.id, card_id)) as cursor:
                owned = (await cursor.fetchone())[0]
            
            rarity_colors = {
                'Common': discord.Color.light_gray(),
                'Uncommon': discord.Color.green(),
                'Rare': discord.Color.blue(),
                'Epic': discord.Color.purple(),
                'Legendary': discord.Color.gold()
            }
            
            embed = discord.Embed(
                title=f"{member} - {group}",
                description=f"**Era:** {era or 'N/A'}\n**Rareza:** {rarity}",
                color=rarity_colors.get(rarity, discord.Color.default())
            )
            
            if owned:
                embed.add_field(name="Posesión", value=f"Tienes {owned} de esta carta")
            else:
                embed.add_field(name="Posesión", value="No tienes esta carta")
            
            embed.add_field(name="ID", value=f"`{card_id}`")
            
            await ctx.send(embed=embed)
            break  # Solo mostrar la primera
    
    @commands.command(name='gift')
    async def gift_card(self, ctx, user: discord.Member, card_id: int):
        """Regala una photocard a otro usuario"""
        if user.bot:
            return await ctx.send("❌ No puedes regalar cartas a bots.")
        
        if user == ctx.author:
            return await ctx.send("❌ No puedes regalarte cartas a ti mismo.")
        
        # Verificar que el usuario tiene la carta
        async with self.bot.db.execute('''
            SELECT uc.id, p.group_name, p.member_name, p.rarity
            FROM user_cards uc
            JOIN photocards p ON uc.card_id = p.card_id
            WHERE uc.user_id = ? AND uc.card_id = ?
            LIMIT 1
        ''', (ctx.author.id, card_id)) as cursor:
            card_data = await cursor.fetchone()
        
        if not card_data:
            return await ctx.send("❌ No tienes esta carta en tu colección.")
        
        user_card_id, group, member, rarity = card_data
        
        # Transferir la carta
        await self.bot.db.execute(
            'DELETE FROM user_cards WHERE id = ?',
            (user_card_id,)
        )
        
        await self.bot.db.execute(
            'INSERT OR IGNORE INTO users (user_id) VALUES (?)',
            (user.id,)
        )
        
        await self.bot.db.execute(
            'INSERT INTO user_cards (user_id, card_id) VALUES (?, ?)',
            (user.id, card_id)
        )
        
        await self.bot.db.commit()
        
        embed = discord.Embed(
            title="🎁 Regalo enviado!",
            description=f"{ctx.author.mention} le regaló una photocard a {user.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Carta", value=f"{member} ({group})")
        embed.add_field(name="Rareza", value=rarity)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Collection(bot))