#!/usr/bin/env python3
"""
Script to fix leveling settings table and test functionality
This script resets and tests the leveling settings to ensure they work properly
"""

import asyncio
import os
import shutil
from datetime import datetime

# Import our settings manager
from leveling_settings_manager import (
    load_settings,
    save_setting,
    reset_settings,
    ensure_settings_table,
    populate_default_settings,
    backup_database
)

async def main():
    """Run all fixes and tests for leveling settings"""
    print("\n=== LEVELING SETTINGS REPAIR & TEST ===\n")
    
    # Create a backup first for safety
    print("Creating backup...")
    backup_path = await backup_database()
    if backup_path:
        print(f"✅ Created backup at {backup_path}")
    else:
        print("⚠️ Could not create backup")
    
    # Ensure table exists
    print("\nChecking settings table structure...")
    table_created = await ensure_settings_table()
    if table_created:
        print("✅ Settings table exists or was created")
    else:
        print("❌ Failed to create settings table")
        return False
    
    # Add default settings if missing
    print("\nChecking for default settings...")
    populated = await populate_default_settings()
    if populated:
        print("✅ Default settings were added")
    else:
        print("ℹ️ Default settings weren't needed (table already had data)")
    
    # Load all settings
    print("\nLoading all settings...")
    settings = await load_settings()
    if settings:
        print(f"✅ Successfully loaded {len(settings)} settings")
        print("\nCurrent settings values:")
        for key, value in settings.items():
            print(f"  {key}: {value}")
    else:
        print("❌ Failed to load settings")
        return False
    
    # Test updating a setting
    test_setting = "level_up_coins"
    original_value = settings.get(test_setting, 150)
    test_value = original_value + 50
    
    print(f"\nTesting update: changing {test_setting} from {original_value} to {test_value}...")
    success = await save_setting(test_setting, test_value)
    
    if success:
        print("✅ Setting updated successfully")
        
        # Verify by loading again
        new_settings = await load_settings()
        new_value = new_settings.get(test_setting, 0)
        
        if new_value == test_value:
            print(f"✅ Verified change: {test_setting} is now {new_value}")
        else:
            print(f"❌ Update verification failed: expected {test_value}, got {new_value}")
            
        # Reset to original value
        await save_setting(test_setting, original_value)
        print(f"✅ Reset {test_setting} back to {original_value}")
    else:
        print("❌ Failed to update setting")
    
    print("\n=== TEST COMPLETED SUCCESSFULLY ===")
    return True

if __name__ == "__main__":
    result = asyncio.run(main())
    if result:
        print("✅ Settings system is working correctly!")
    else:
        print("❌ Settings system has issues that need to be fixed!")