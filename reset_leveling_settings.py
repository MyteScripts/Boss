#!/usr/bin/env python3
import sqlite3
import asyncio
import aiosqlite

async def reset_leveling_settings():
    """Ensure the leveling_settings table exists with all required fields"""
    try:
        # First, check if the table exists and back up any existing settings
        existing_settings = {}
        try:
            async with aiosqlite.connect("leveling.db") as db:
                # Check if table exists
                cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='leveling_settings'")
                table_exists = await cursor.fetchone()
                
                if table_exists:
                    print("📋 leveling_settings table exists, backing up values...")
                    cursor = await db.execute('SELECT setting_name, value FROM leveling_settings')
                    rows = await cursor.fetchall()
                    if rows:
                        existing_settings = {name: value for name, value in rows}
                        print(f"📋 Backed up {len(existing_settings)} existing settings")
                        if 'level_up_coins' in existing_settings:
                            print(f"🔰 Existing level_up_coins = {existing_settings['level_up_coins']}")
        except Exception as e:
            print(f"⚠️ Warning checking existing table: {e}")
        
        # Default settings to use for missing values
        default_settings = [
            ("xp_min", 5),
            ("xp_max", 25),
            ("cooldown_seconds", 7),
            ("voice_xp_per_minute", 2),
            ("voice_coins_per_minute", 1),
            ("afk_xp_per_minute", 1),
            ("afk_coins_per_minute", 0),
            ("message_xp_min", 5),
            ("message_xp_max", 25),
            ("level_up_coins", 150),
            ("level_up_xp_base", 50),
            ("enabled", 1)
        ]
        
        # Now create/recreate the table
        async with aiosqlite.connect("leveling.db") as db:
            # Create the table if it doesn't exist
            await db.execute('''
                CREATE TABLE IF NOT EXISTS leveling_settings (
                    setting_name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
            ''')
            
            # Check if table has any data
            cursor = await db.execute('SELECT COUNT(*) FROM leveling_settings')
            count = await cursor.fetchone()
            
            if count and count[0] > 0:
                print(f"✅ Table already has {count[0]} settings, will preserve existing values")
            else:
                print("🆕 Empty table, will populate with default values")
                
                # Insert settings, using existing values where available
                for setting_name, default_value in default_settings:
                    # Use existing value if available
                    value = existing_settings.get(setting_name, default_value)
                    
                    await db.execute(
                        'INSERT OR REPLACE INTO leveling_settings (setting_name, value) VALUES (?, ?)',
                        (setting_name, value)
                    )
                
                await db.commit()
                print("✅ Successfully initialized leveling_settings table while preserving existing values")
                
                # Verify the data
                cursor = await db.execute('SELECT COUNT(*) FROM leveling_settings')
                count = await cursor.fetchone()
                print(f"✅ Verified table contains {count[0]} settings")
                
                # Specifically log level_up_coins
                cursor = await db.execute('SELECT value FROM leveling_settings WHERE setting_name = "level_up_coins"')
                luc = await cursor.fetchone()
                if luc:
                    print(f"💰 Current level_up_coins value: {luc[0]}")
    
    except Exception as e:
        print(f"❌ Error managing leveling settings table: {e}")

# For direct execution
if __name__ == "__main__":
    asyncio.run(reset_leveling_settings())