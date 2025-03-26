"""
Enhanced leveling settings manager for persistence between bot restarts
This module provides reliable loading and saving of leveling settings
"""

import os
import aiosqlite 
import shutil
from datetime import datetime

# Default settings used when database is empty or corrupted
DEFAULT_SETTINGS = [
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

# Convert to dictionary for easier access
DEFAULT_SETTINGS_DICT = {name: value for name, value in DEFAULT_SETTINGS}


async def backup_database():
    """Create a timestamped backup of the leveling database"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if os.path.exists("leveling.db"):
            os.makedirs("backups", exist_ok=True)
            backup_path = f"backups/leveling_backup_{timestamp}.db"
            shutil.copy2("leveling.db", backup_path)
            print(f"✅ Created settings backup at {backup_path}")
            return backup_path
        else:
            print("⚠️ No database file found to backup")
            return None
    except Exception as e:
        print(f"⚠️ Warning: Could not backup settings: {e}")
        return None


async def ensure_settings_table():
    """Create the settings table if it doesn't exist"""
    try:
        async with aiosqlite.connect("leveling.db") as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS leveling_settings (
                    setting_name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
            ''')
            await db.commit()
            print("✅ Ensured leveling_settings table exists")
            return True
    except Exception as e:
        print(f"❌ Error creating settings table: {e}")
        return False


async def populate_default_settings():
    """Populate the settings table with default values if empty"""
    try:
        async with aiosqlite.connect("leveling.db") as db:
            # Check if table is empty
            cursor = await db.execute('SELECT COUNT(*) FROM leveling_settings')
            count = await cursor.fetchone()
            
            if count is None or count[0] == 0:
                print("ℹ️ Settings table empty, inserting default values...")
                
                for setting_name, value in DEFAULT_SETTINGS:
                    await db.execute(
                        'INSERT INTO leveling_settings (setting_name, value) VALUES (?, ?)',
                        (setting_name, value)
                    )
                
                await db.commit()
                print("✅ Inserted default settings")
                return True
            else:
                print(f"ℹ️ Settings table already has {count[0]} entries")
                return False
    except Exception as e:
        print(f"❌ Error populating default settings: {e}")
        return False


async def load_settings():
    """Load settings from database with robust error handling"""
    try:
        # First try to create/ensure the table exists
        await ensure_settings_table()
        
        # Then make sure there are default values if needed
        await populate_default_settings()
        
        # Now load the settings
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute('SELECT setting_name, value FROM leveling_settings')
            all_settings = await cursor.fetchall()
            
            if not all_settings:
                print("⚠️ No settings found in the database, using defaults")
                return DEFAULT_SETTINGS_DICT.copy()
            
            # Convert to dictionary and add detailed logging
            settings_dict = {name: int(value) for name, value in all_settings}
            
            # Log each setting for debugging
            for name, value in settings_dict.items():
                print(f"🔍 Loaded setting: {name} = {value}")
            
            # Specifically check for level_up_coins
            if 'level_up_coins' in settings_dict:
                print(f"🔔 Found level_up_coins in database: {settings_dict['level_up_coins']}")
            else:
                print("⚠️ level_up_coins NOT found in database, will use default")
                settings_dict['level_up_coins'] = DEFAULT_SETTINGS_DICT['level_up_coins']
            
            print(f"✅ Successfully loaded {len(settings_dict)} settings from database")
            return settings_dict
            
    except Exception as e:
        print(f"❌ Error loading settings, using defaults: {e}")
        return DEFAULT_SETTINGS_DICT.copy()


async def save_setting(setting_name, value):
    """Save a single setting to the database"""
    try:
        # Ensure the table exists first
        await ensure_settings_table()
        
        print(f"📝 Attempting to save setting: {setting_name} = {value}")
        
        async with aiosqlite.connect("leveling.db") as db:
            # Update with UPSERT pattern - update if exists, insert if not
            await db.execute('''
                INSERT INTO leveling_settings (setting_name, value) 
                VALUES (?, ?) 
                ON CONFLICT(setting_name) DO UPDATE SET value = ?
            ''', (setting_name, value, value))
            
            await db.commit()
            
            # Verify the setting was actually saved
            cursor = await db.execute('SELECT value FROM leveling_settings WHERE setting_name = ?', (setting_name,))
            result = await cursor.fetchone()
            if result:
                print(f"✅ Successfully verified setting {setting_name} = {result[0]} in database")
            else:
                print(f"⚠️ Could not verify setting {setting_name} in database after save")
            
            print(f"✅ Successfully saved setting {setting_name} = {value}")
            return True
    except Exception as e:
        print(f"❌ Error saving setting {setting_name}: {e}")
        return False


async def reset_settings():
    """Reset all settings to default values"""
    try:
        # First backup the current database
        await backup_database()
        
        async with aiosqlite.connect("leveling.db") as db:
            # Delete all existing settings
            await db.execute('DELETE FROM leveling_settings')
            
            # Insert default settings
            for setting_name, value in DEFAULT_SETTINGS:
                await db.execute(
                    'INSERT INTO leveling_settings (setting_name, value) VALUES (?, ?)',
                    (setting_name, value)
                )
            
            await db.commit()
            print("✅ Reset all settings to default values")
            return True
    except Exception as e:
        print(f"❌ Error resetting settings: {e}")
        return False


async def get_setting(setting_name, default_value=None):
    """Get a single setting by name with a default fallback"""
    try:
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute(
                'SELECT value FROM leveling_settings WHERE setting_name = ?', 
                (setting_name,)
            )
            result = await cursor.fetchone()
            
            if result:
                return int(result[0])
            else:
                # If not found, return the default from our defaults dict
                # or the provided default value if specified
                if default_value is not None:
                    return default_value
                return DEFAULT_SETTINGS_DICT.get(setting_name)
    except Exception as e:
        print(f"❌ Error getting setting {setting_name}: {e}")
        # Return the default if available
        if default_value is not None:
            return default_value
        return DEFAULT_SETTINGS_DICT.get(setting_name)