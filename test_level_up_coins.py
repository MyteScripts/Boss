#!/usr/bin/env python3
"""
Simple test script to verify the leveling_settings table has the correct values
and the level_up_coins setting is being used properly.
"""
import sqlite3
import sys

def get_level_up_coins():
    """
    Get the current level_up_coins setting from the database.
    """
    try:
        print("Connecting to database...")
        conn = sqlite3.connect("leveling.db")
        cursor = conn.cursor()
        
        print("Checking leveling_settings table...")
        cursor.execute("SELECT value FROM leveling_settings WHERE setting_name = 'level_up_coins'")
        result = cursor.fetchone()
        
        if result:
            level_up_coins = result[0]
            print(f"✅ Found level_up_coins setting: {level_up_coins}")
            return level_up_coins
        else:
            print("❌ level_up_coins setting not found in the database")
            return None
            
    except Exception as e:
        print(f"❌ Error accessing database: {e}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

def update_level_up_coins(new_value):
    """
    Update the level_up_coins setting in the database.
    """
    try:
        print(f"Setting level_up_coins to {new_value}...")
        conn = sqlite3.connect("leveling.db")
        cursor = conn.cursor()
        
        cursor.execute("UPDATE leveling_settings SET value = ? WHERE setting_name = 'level_up_coins'", 
                     (new_value,))
        conn.commit()
        
        if cursor.rowcount > 0:
            print(f"✅ Successfully updated level_up_coins to {new_value}")
            return True
        else:
            print("❌ Failed to update level_up_coins (no rows affected)")
            return False
            
    except Exception as e:
        print(f"❌ Error updating database: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("======================================")
    print("Level Up Coins Setting Verification")
    print("======================================")
    
    current_value = get_level_up_coins()
    
    if current_value is not None:
        # If a command line argument is provided, update the value
        if len(sys.argv) > 1:
            try:
                new_value = int(sys.argv[1])
                if update_level_up_coins(new_value):
                    print(f"\n✅ level_up_coins setting has been updated to {new_value}")
                    print("\nRestart the bot for the changes to take effect!")
            except ValueError:
                print(f"\n❌ Invalid value: {sys.argv[1]}. Please provide a valid integer.")
        else:
            print("\nThe current level_up_coins value will be used when users level up.")
            print("To update this value, you can:")
            print("1. Use the /editleveling command in Discord")
            print("2. Run this script with a new value: python test_level_up_coins.py <new_value>")
    else:
        print("\n❌ Cannot verify level_up_coins setting. Please run fix_leveling_settings.py first.")