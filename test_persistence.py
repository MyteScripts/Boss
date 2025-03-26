#!/usr/bin/env python3
"""
Test script to verify if settings are persisting correctly in the database
Specifically tests if level_up_coins value persists after it has been changed
"""

import asyncio
import os
import shutil
from datetime import datetime

async def test_persistence():
    """Test if the level_up_coins setting persists between loads"""
    print("\n===== Testing Level Up Coins Persistence =====")
    
    # Import our settings manager
    from leveling_settings_manager import load_settings, save_setting, get_setting
    
    # Create a backup of the database before we start
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if os.path.exists("leveling.db"):
        os.makedirs("backups", exist_ok=True)
        backup_path = f"backups/leveling_backup_before_test_{timestamp}.db"
        shutil.copy2("leveling.db", backup_path)
        print(f"✅ Created backup at {backup_path}")
    
    # Load current settings
    print("\n1. Loading current settings...")
    settings = await load_settings()
    current_coins = settings.get("level_up_coins", -1)
    print(f"Current level_up_coins setting: {current_coins}")
    
    # Set a test value
    test_value = 35  # The value the user wants
    print(f"\n2. Setting level_up_coins to {test_value}...")
    success = await save_setting("level_up_coins", test_value)
    if success:
        print(f"✅ Successfully saved level_up_coins = {test_value}")
    else:
        print(f"❌ Failed to save level_up_coins")
        return
    
    # Verify the setting was saved
    print("\n3. Verifying value was saved...")
    directly_from_db = await get_setting("level_up_coins")
    print(f"Value read directly from database: {directly_from_db}")
    
    # Simulate restarting the bot by reloading settings
    print("\n4. Simulating bot restart (reloading settings)...")
    new_settings = await load_settings()
    after_restart = new_settings.get("level_up_coins", -1)
    print(f"level_up_coins after simulated restart: {after_restart}")
    
    # Check results
    if after_restart == test_value:
        print(f"\n✅ SUCCESS! level_up_coins persisted correctly with value {after_restart}")
        return True
    else:
        print(f"\n❌ FAILED! level_up_coins changed from {test_value} to {after_restart}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_persistence())
    if result:
        print("\nYour level_up_coins setting should now persist between bot restarts!")
    else:
        print("\nThere's still an issue with your level_up_coins setting persistence.")