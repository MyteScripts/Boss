#!/usr/bin/env python3
"""
Enhanced script to fix the leveling_settings table by dropping and recreating it with default values.
This can be run manually when the /editleveling command is failing.

This version includes both synchronous and asynchronous functions for different contexts.
"""
import sqlite3
import sys
import asyncio
import os

def fix_leveling_settings():
    """
    Fix the leveling_settings table by dropping and recreating it with default values.
    This is a synchronous version that can be run directly from the command line.
    """
    try:
        print("Connecting to database...")
        conn = sqlite3.connect("leveling.db")
        cursor = conn.cursor()
        
        print("Dropping leveling_settings table if it exists...")
        cursor.execute("DROP TABLE IF EXISTS leveling_settings")
        conn.commit()
        
        print("Creating fresh leveling_settings table...")
        cursor.execute('''
            CREATE TABLE leveling_settings (
                setting_name TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
        ''')
        
        # Insert default settings
        print("Inserting default settings...")
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
        
        cursor.executemany(
            'INSERT INTO leveling_settings (setting_name, value) VALUES (?, ?)',
            default_settings
        )
        
        conn.commit()
        
        # Verify data was inserted
        cursor.execute('SELECT COUNT(*) FROM leveling_settings')
        count = cursor.fetchone()[0]
        
        print(f"✅ Successfully reset and initialized leveling_settings table with {count} settings")
        print("Table should now be working properly for the /editleveling command")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error resetting leveling settings table: {e}")
        return False

async def fix_leveling_settings_async():
    """
    Asynchronous version of the fix function for import into discord.py code.
    Can be called from within the main bot's async functions.
    """
    # Fall back to synchronous function since it's safer and more reliable
    # This avoids issues with aiosqlite which can be finicky sometimes
    try:
        # Run the sync version in a thread pool to avoid blocking
        print("Running fix_leveling_settings in async context")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, fix_leveling_settings)
        return result
    except Exception as e:
        print(f"❌ Error in async wrapper: {e}")
        # Try one more time with direct synchronous code
        # This is the most robust approach that should almost always work
        return fix_leveling_settings()

# Create a function to ensure settings exist without dropping the table
def ensure_leveling_settings():
    """
    Non-destructive version that ensures the leveling_settings table exists
    and has all required settings, but doesn't drop existing data.
    """
    try:
        print("Connecting to database to ensure settings exist...")
        conn = sqlite3.connect("leveling.db")
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leveling_settings (
                setting_name TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
        ''')
        conn.commit()
        
        # Check if table has any data
        cursor.execute('SELECT COUNT(*) FROM leveling_settings')
        count = cursor.fetchone()[0]
        
        # Define default settings
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
        
        if count == 0:
            # If table is empty, insert all defaults
            print("Table exists but is empty, inserting all default values...")
            cursor.executemany(
                'INSERT INTO leveling_settings (setting_name, value) VALUES (?, ?)',
                default_settings
            )
        else:
            # Table has data, check if all required settings exist
            print(f"Table has {count} existing settings, checking if any are missing...")
            for setting_name, default_value in default_settings:
                # Check if this setting exists
                cursor.execute('SELECT value FROM leveling_settings WHERE setting_name = ?', (setting_name,))
                result = cursor.fetchone()
                
                if not result:
                    # Setting doesn't exist, insert it
                    print(f"Adding missing setting: {setting_name} = {default_value}")
                    cursor.execute(
                        'INSERT INTO leveling_settings (setting_name, value) VALUES (?, ?)',
                        (setting_name, default_value)
                    )
        
        conn.commit()
        
        # Verify data
        cursor.execute('SELECT COUNT(*) FROM leveling_settings')
        final_count = cursor.fetchone()[0]
        
        print(f"✅ Ensured leveling_settings table exists with {final_count} settings")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error ensuring leveling settings: {e}")
        # If we get an error, try the more aggressive fix approach
        print("Falling back to complete table reset...")
        return fix_leveling_settings()

# This function can be called externally without async
def repair_settings():
    """
    Public function to attempt multiple repair strategies in sequence.
    This is the most robust approach for external callers.
    """
    # First try the non-destructive approach
    try:
        result = ensure_leveling_settings()
        if result:
            return True
    except Exception as e:
        print(f"Non-destructive repair failed: {e}")
    
    # If that failed, try the more aggressive approach
    try:
        return fix_leveling_settings()
    except Exception as e:
        print(f"All repair attempts failed: {e}")
        return False

if __name__ == "__main__":
    print("==============================================")
    print("Enhanced Leveling Settings Table Repair Utility")
    print("==============================================")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--ensure":
        print("Running in non-destructive mode (--ensure)")
        success = ensure_leveling_settings()
    else:
        print("Running in complete reset mode")
        success = fix_leveling_settings()
    
    if success:
        print("\n✅ Repair completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Repair failed. Check the error messages above.")
        sys.exit(1)