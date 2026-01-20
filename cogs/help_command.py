import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='help', aliases=['h', 'ayuda'])
    async def help_command(self, ctx, category: str = None):
        """Muestra la ayuda del bot"""
        
        if category is None:
            # Menú principal
            embed = discord.Embed(
                title="📚 Ayuda - K-pop Photocard Bot",
                description="¡Colecciona photocards de tus artistas favoritos de K-pop!",
                color=discord.Color.purple()
            )
            
            embed.add_field(
                name="🎲 Gacha",
                value="`k!help gacha` - Comandos de drops y spawns",
                inline=False
            )
            
            embed.add_field(
                name="📸 Colección",
                value="`k!help collection` - Comandos de inventario",
                inline=False
            )
            
            embed.add_field(
                name="💰 Economía",
                value="`k!help economy` - Comandos de monedas y compras",
                inline=False
            )
            
            embed.set_footer(text="Usa k!help <categoría> para más información")
            
        elif category.lower() == 'gacha':
            embed = discord.Embed(
                title="🎲 Comandos de Gacha",
                description="**NUEVO:** Ahora reaccionas con 1️⃣, 2️⃣ o 3️⃣ para elegir cartas!",
                color=discord.Color.blue()
            )
            
            commands_list = [
                ("Reacciones", "Reacciona con 1️⃣, 2️⃣ o 3️⃣ en un drop para elegir una carta"),
                ("k!cooldown (cd)", "Verifica tu cooldown de grab (5 min)"),
                ("k!dropinfo", "Información detallada del sistema de drops"),
                ("k!drop", "Fuerza un drop (solo admins, ignora cooldown)"),
                ("k!dropchannel", "Establece el canal para drops automáticos (solo admins)"),
                ("k!removedropchannel", "Remueve el canal de drops (solo admins)")
            ]
            
            for cmd, desc in commands_list:
                embed.add_field(name=cmd, value=desc, inline=False)
            
            embed.set_footer(text="⏰ Cooldown grab: 5 min | Cooldown drop: 15 min")
        
        elif category.lower() == 'collection':
            embed = discord.Embed(
                title="📸 Comandos de Colección",
                color=discord.Color.green()
            )
            
            commands_list = [
                ("k!collection (col, c) [@usuario]", "Muestra tu colección o la de otro usuario"),
                ("k!inventory (inv)", "Muestra un resumen de tu inventario"),
                ("k!view (v) <búsqueda>", "Busca información de una photocard"),
                ("k!gift <@usuario> <card_id>", "Regala una photocard a otro usuario")
            ]
            
            for cmd, desc in commands_list:
                embed.add_field(name=cmd, value=desc, inline=False)
        
        elif category.lower() == 'economy':
            embed = discord.Embed(
                title="💰 Comandos de Economía",
                color=discord.Color.gold()
            )
            
            commands_list = [
                ("k!daily", "Reclama tu recompensa diaria"),
                ("k!balance (bal) [@usuario]", "Verifica tu balance de monedas"),
                ("k!buy <tipo>", "Compra un pack de photocards\nTipos: basic, premium, deluxe"),
                ("k!sell <card_id>", "Vende una photocard por monedas"),
                ("k!leaderboard (lb, top) <categoría>", "Muestra el ranking\nCategorías: coins, cards, drops")
            ]
            
            for cmd, desc in commands_list:
                embed.add_field(name=cmd, value=desc, inline=False)
        
        else:
            embed = discord.Embed(
                title="❌ Categoría no encontrada",
                description="Usa `k!help` para ver las categorías disponibles",
                color=discord.Color.red()
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))