import asyncio
import aiosqlite
import json

async def populate_database():
    """Puebla la base de datos con photocards de K-pop con numeración"""
    
    # Datos de ejemplo - expande esto con tus propios datos
    # Formato de card_number: GRUPO-MIEMBRO-001
    photocards_data = [

        # TWICE - Numeración TWC-001 a TWC-009
        {'card_number': 'TWC-001', 'group': 'TWICE', 'member': 'Nayeon', 'era': 'Formula of Love', 'rarity': 'Uncommon', 'series': 'S1'},
        {'card_number': 'TWC-002', 'group': 'TWICE', 'member': 'Jeongyeon', 'era': 'Ready to Be', 'rarity': 'Common', 'series': 'S1'},
        {'card_number': 'TWC-003', 'group': 'TWICE', 'member': 'Momo', 'era': 'Taste of Love', 'rarity': 'Rare', 'series': 'S1'},
        {'card_number': 'TWC-004', 'group': 'TWICE', 'member': 'Sana', 'era': 'Formula of Love', 'rarity': 'Epic', 'series': 'S1'},
        {'card_number': 'TWC-005', 'group': 'TWICE', 'member': 'Jihyo', 'era': 'Between 1&2', 'rarity': 'Rare', 'series': 'S1'},
        {'card_number': 'TWC-006', 'group': 'TWICE', 'member': 'Mina', 'era': 'Ready to Be', 'rarity': 'Uncommon', 'series': 'S1'},
        {'card_number': 'TWC-007', 'group': 'TWICE', 'member': 'Dahyun', 'era': 'Taste of Love', 'rarity': 'Common', 'series': 'S1'},
        {'card_number': 'TWC-008', 'group': 'TWICE', 'member': 'Chaeyoung', 'era': 'Formula of Love', 'rarity': 'Rare', 'series': 'S1'},
        {'card_number': 'TWC-009', 'group': 'TWICE', 'member': 'Tzuyu', 'era': 'Between 1&2', 'rarity': 'Legendary', 'series': 'S1'},

    ]
    
    db = await aiosqlite.connect('kpop_bot.db')
    
    try:
        # Crear tabla si no existe con la nueva estructura
        await db.execute('''
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
        
        # Insertar photocards
        inserted = 0
        skipped = 0
        
        for card in photocards_data:
            # Generar ruta de imagen (ajusta según tu estructura)
            image_path = f"data/photocards/{card['group']}/{card['member']}_{card['era']}.jpg"
            
            try:
                await db.execute('''
                    INSERT INTO photocards 
                    (card_number, group_name, member_name, era, rarity, image_path, series)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (card['card_number'], card['group'], card['member'], 
                      card['era'], card['rarity'], image_path, card['series']))
                inserted += 1
            except Exception as e:
                print(f"⚠️  Skipped {card['card_number']} ({card['member']}): {e}")
                skipped += 1
        
        await db.commit()
        print(f"\n{'='*60}")
        print(f"✅ {inserted} photocards agregadas exitosamente!")
        if skipped > 0:
            print(f"⚠️  {skipped} photocards omitidas (duplicadas o error)")
        print(f"{'='*60}\n")
        
        # Mostrar estadísticas detalladas
        print("📊 ESTADÍSTICAS GENERALES:")
        async with db.execute('SELECT COUNT(*) FROM photocards') as cursor:
            total = (await cursor.fetchone())[0]
        print(f"   Total de cartas en DB: {total}")
        
        print("\n📈 POR RAREZA:")
        async with db.execute('''
            SELECT rarity, COUNT(*) as count 
            FROM photocards 
            GROUP BY rarity 
            ORDER BY 
                CASE rarity
                    WHEN 'Legendary' THEN 1
                    WHEN 'Epic' THEN 2
                    WHEN 'Rare' THEN 3
                    WHEN 'Uncommon' THEN 4
                    WHEN 'Common' THEN 5
                END
        ''') as cursor:
            rarities = await cursor.fetchall()
        
        rarity_emojis = {
            'Legendary': '🟡',
            'Epic': '🟣',
            'Rare': '🔵',
            'Uncommon': '🟢',
            'Common': '⚪'
        }
        
        for rarity, count in rarities:
            emoji = rarity_emojis.get(rarity, '⚪')
            percentage = (count / total * 100) if total > 0 else 0
            print(f"   {emoji} {rarity:12} : {count:3} ({percentage:5.1f}%)")
        
        print("\n🎤 POR GRUPO:")
        async with db.execute('''
            SELECT group_name, COUNT(*) as count 
            FROM photocards 
            GROUP BY group_name 
            ORDER BY count DESC
        ''') as cursor:
            groups = await cursor.fetchall()
        
        for group, count in groups:
            print(f"   {group:15} : {count:3} cartas")
        
        print("\n📦 POR SERIE:")
        async with db.execute('''
            SELECT series, COUNT(*) as count 
            FROM photocards 
            GROUP BY series 
            ORDER BY series
        ''') as cursor:
            series = await cursor.fetchall()
        
        for serie, count in series:
            print(f"   Serie {serie}: {count:3} cartas")
        
        print("\n" + "="*60)
        print("✨ Base de datos lista para usar!")
        print("="*60)
        
        # Mostrar ejemplos de numeración
        print("\n📝 EJEMPLOS DE NUMERACIÓN:")
        async with db.execute('''
            SELECT card_number, member_name, group_name, rarity, series
            FROM photocards 
            LIMIT 5
        ''') as cursor:
            examples = await cursor.fetchall()
        
        for card_num, member, group, rarity, serie in examples:
            print(f"   {serie}-{card_num:12} | {member:15} ({group}) - {rarity}")
    
    finally:
        await db.close()

if __name__ == '__main__':
    print("🎴 Iniciando población de base de datos de Photocards K-pop...\n")
    asyncio.run(populate_database())