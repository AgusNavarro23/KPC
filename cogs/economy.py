import discord
from discord.ext import commands
from datetime import datetime, timedelta
import random

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='daily')
    async def daily_reward(self, ctx):
        """Reclama tu recompensa diaria de monedas"""
        async with self.bot.db.execute(
            'SELECT last_daily FROM users WHERE user_id = ?',
            (ctx.author.id,)
        ) as cursor:
            result = await cursor.fetchone()
        
        if result and result[0]:
            last_daily = datetime.fromisoformat(result[0])
            next_daily = last_daily + timedelta(days=1)
            
            if datetime.utcnow() < next_daily:
                remaining = next_daily - datetime.utcnow()
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                
                return await ctx.send(
                    f"⏰ Ya reclamaste tu recompensa diaria.\n"
                    f"Vuelve en {hours}h {minutes}m"
                )
        
        # Dar recompensa
        reward = random.randint(50, 150)
        bonus = random.randint(0, 50) if random.random() < 0.3 else 0  # 30% de bonus
        total = reward + bonus
        
        await self.bot.db.execute(
            '''INSERT INTO users (user_id, coins, last_daily) 
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET 
               coins = coins + ?,
               last_daily = ?''',
            (ctx.author.id, total, datetime.utcnow().isoformat(),
             total, datetime.utcnow().isoformat())
        )
        await self.bot.db.commit()
        
        embed = discord.Embed(
            title="🎁 Recompensa Diaria",
            description=f"Has recibido **{reward}** monedas!",
            color=discord.Color.gold()
        )
        
        if bonus:
            embed.add_field(
                name="🎉 Bonus!",
                value=f"+{bonus} monedas extra!"
            )
            embed.description += f"\n**Total: {total} monedas**"
        
        await ctx.send(embed=embed)
    
    @commands.command(name='balance', aliases=['bal'])
    async def check_balance(self, ctx, user: discord.Member = None):
        """Verifica el balance de monedas"""
        target = user or ctx.author
        
        async with self.bot.db.execute(
            'SELECT coins FROM users WHERE user_id = ?',
            (target.id,)
        ) as cursor:
            result = await cursor.fetchone()
        
        coins = result[0] if result else 0
        
        embed = discord.Embed(
            title=f"💰 Balance de {target.display_name}",
            description=f"**{coins:,}** monedas",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='buy')
    async def buy_pack(self, ctx, pack_type: str = 'basic'):
        """Compra un pack de photocards
        
        Tipos disponibles:
        - basic (100 monedas) - 3 cartas
        - premium (500 monedas) - 5 cartas, mejor probabilidad
        - deluxe (1000 monedas) - 10 cartas, mejores probabilidades
        """
        packs = {
            'basic': {
                'cost': 100,
                'cards': 3,
                'rarity_boost': 0
            },
            'premium': {
                'cost': 500,
                'cards': 5,
                'rarity_boost': 0.1
            },
            'deluxe': {
                'cost': 1000,
                'cards': 10,
                'rarity_boost': 0.2
            }
        }
        
        if pack_type not in packs:
            return await ctx.send(
                "❌ Tipo de pack inválido. Usa: `basic`, `premium`, o `deluxe`"
            )
        
        pack = packs[pack_type]
        
        # Verificar balance
        async with self.bot.db.execute(
            'SELECT coins FROM users WHERE user_id = ?',
            (ctx.author.id,)
        ) as cursor:
            result = await cursor.fetchone()
        
        if not result or result[0] < pack['cost']:
            return await ctx.send(
                f"❌ No tienes suficientes monedas. Necesitas {pack['cost']}, "
                f"tienes {result[0] if result else 0}"
            )
        
        # Deducir monedas
        await self.bot.db.execute(
            'UPDATE users SET coins = coins - ? WHERE user_id = ?',
            (pack['cost'], ctx.author.id)
        )
        
        # Generar cartas
        obtained_cards = []
        rarities = ['Common', 'Uncommon', 'Rare', 'Epic', 'Legendary']
        rarity_chances = [0.50, 0.30, 0.15, 0.04, 0.01]
        
        # Ajustar probabilidades según el pack
        if pack['rarity_boost'] > 0:
            boost = pack['rarity_boost']
            rarity_chances[0] -= boost  # Reducir Common
            rarity_chances[2] += boost * 0.5  # Aumentar Rare
            rarity_chances[3] += boost * 0.3  # Aumentar Epic
            rarity_chances[4] += boost * 0.2  # Aumentar Legendary
        
        for _ in range(pack['cards']):
            rarity = random.choices(rarities, weights=rarity_chances)[0]
            
            async with self.bot.db.execute(
                'SELECT card_id, group_name, member_name FROM photocards WHERE rarity = ? ORDER BY RANDOM() LIMIT 1',
                (rarity,)
            ) as cursor:
                card = await cursor.fetchone()
            
            if card:
                card_id, group, member = card
                
                # Agregar a la colección del usuario
                await self.bot.db.execute(
                    'INSERT INTO user_cards (user_id, card_id) VALUES (?, ?)',
                    (ctx.author.id, card_id)
                )
                
                obtained_cards.append({
                    'group': group,
                    'member': member,
                    'rarity': rarity
                })
        
        await self.bot.db.commit()
        
        # Mostrar resultados
        embed = discord.Embed(
            title=f"📦 Pack {pack_type.capitalize()} abierto!",
            description=f"Has obtenido {len(obtained_cards)} photocards:",
            color=discord.Color.blue()
        )
        
        rarity_emojis = {
            'Common': '⚪',
            'Uncommon': '🟢',
            'Rare': '🔵',
            'Epic': '🟣',
            'Legendary': '🟡'
        }
        
        for i, card in enumerate(obtained_cards, 1):
            emoji = rarity_emojis.get(card['rarity'], '⚪')
            embed.add_field(
                name=f"{emoji} {card['member']}",
                value=f"{card['group']}\n{card['rarity']}",
                inline=True
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='sell')
    async def sell_card(self, ctx, card_id: int):
        """Vende una photocard por monedas"""
        # Verificar que el usuario tiene la carta
        async with self.bot.db.execute('''
            SELECT uc.id, p.member_name, p.group_name, p.rarity
            FROM user_cards uc
            JOIN photocards p ON uc.card_id = p.card_id
            WHERE uc.user_id = ? AND uc.card_id = ?
            LIMIT 1
        ''', (ctx.author.id, card_id)) as cursor:
            card_data = await cursor.fetchone()
        
        if not card_data:
            return await ctx.send("❌ No tienes esta carta.")
        
        user_card_id, member, group, rarity = card_data
        
        # Calcular precio según rareza
        prices = {
            'Common': 10,
            'Uncommon': 25,
            'Rare': 75,
            'Epic': 200,
            'Legendary': 500
        }
        
        price = prices.get(rarity, 10)
        
        # Eliminar carta y dar monedas
        await self.bot.db.execute(
            'DELETE FROM user_cards WHERE id = ?',
            (user_card_id,)
        )
        
        await self.bot.db.execute(
            'UPDATE users SET coins = coins + ? WHERE user_id = ?',
            (price, ctx.author.id)
        )
        
        await self.bot.db.commit()
        
        embed = discord.Embed(
            title="💵 Carta vendida!",
            description=f"Has vendido **{member}** ({group}) por **{price}** monedas",
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='leaderboard', aliases=['lb', 'top'])
    async def leaderboard(self, ctx, category: str = 'coins'):
        """Muestra el ranking de usuarios
        
        Categorías: coins, cards, drops
        """
        if category == 'coins':
            query = 'SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT 10'
            title = "💰 Top 10 - Monedas"
        elif category == 'cards':
            query = '''
                SELECT user_id, COUNT(*) as count 
                FROM user_cards 
                GROUP BY user_id 
                ORDER BY count DESC 
                LIMIT 10
            '''
            title = "📸 Top 10 - Colección"
        elif category == 'drops':
            query = 'SELECT user_id, drops_count FROM users ORDER BY drops_count DESC LIMIT 10'
            title = "🎯 Top 10 - Drops"
        else:
            return await ctx.send("❌ Categoría inválida. Usa: coins, cards, o drops")
        
        async with self.bot.db.execute(query) as cursor:
            results = await cursor.fetchall()
        
        if not results:
            return await ctx.send("No hay datos suficientes para el ranking.")
        
        embed = discord.Embed(
            title=title,
            color=discord.Color.purple()
        )
        
        medals = ['🥇', '🥈', '🥉']
        
        for i, (user_id, value) in enumerate(results, 1):
            user = self.bot.get_user(user_id)
            name = user.display_name if user else f"Usuario {user_id}"
            medal = medals[i-1] if i <= 3 else f"#{i}"
            
            embed.add_field(
                name=f"{medal} {name}",
                value=f"{value:,}",
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))