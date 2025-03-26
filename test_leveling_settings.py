"""
Test script for the leveling settings manager module
"""

import asyncio
from leveling_settings_manager import (
    backup_database,
    ensure_settings_table,
    populate_default_settings,
    load_settings,
    save_setting,
    get_setting,
    reset_settings
)

async def test_all_functions():
    """Run through all functionality to test it works"""
    print("\n=== Testing Leveling Settings Manager ===\n")
    
    # Step 1: Backup current database
    print("\n--- Test Database Backup ---")
    backup_path = await backup_database()
    print(f"Backup created at: {backup_path}")
    
    # Step 2: Ensure settings table exists
    print("\n--- Test Ensure Settings Table ---")
    table_exists = await ensure_settings_table()
    print(f"Settings table exists: {table_exists}")
    
    # Step 3: Populate with default settings if needed
    print("\n--- Test Populate Default Settings ---")
    populated = await populate_default_settings()
    print(f"Default settings populated: {populated}")
    
    # Step 4: Load all settings
    print("\n--- Test Load Settings ---")
    settings = await load_settings()
    print(f"Loaded {len(settings)} settings:")
    for name, value in settings.items():
        print(f"  {name}: {value}")
    
    # Step 5: Save a single setting
    print("\n--- Test Save Setting ---")
    new_value = settings.get("level_up_coins", 150) + 50  # Increase by 50
    saved = await save_setting("level_up_coins", new_value)
    print(f"Saved setting 'level_up_coins' to {new_value}: {saved}")
    
    # Step 6: Get the setting to confirm it was saved
    print("\n--- Test Get Setting ---")
    updated_value = await get_setting("level_up_coins")
    print(f"Retrieved 'level_up_coins' value: {updated_value}")
    print(f"Verification: {updated_value == new_value}")
    
    # Step 7: Get a non-existent setting with default
    print("\n--- Test Get Non-existent Setting ---")
    non_existent = await get_setting("non_existent_setting", 999)
    print(f"Retrieved 'non_existent_setting' with default: {non_existent}")
    
    # Step 8: Reset settings (optional - uncomment to test)
    # print("\n--- Test Reset Settings ---")
    # reset = await reset_settings()
    # print(f"Reset all settings to defaults: {reset}")
    
    print("\n=== Testing Complete ===\n")
    
    # Return the value we've set for verification
    return updated_value

if __name__ == "__main__":
    result = asyncio.run(test_all_functions())
    print(f"Final result - level_up_coins: {result}")