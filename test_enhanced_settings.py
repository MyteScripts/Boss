#!/usr/bin/env python3
"""
Test script for the enhanced leveling settings manager module
This script verifies that our implementation works correctly
"""

import asyncio
from leveling_settings_manager import (
    load_settings,
    save_setting,
    reset_settings,
    backup_database,
    get_setting
)

async def test_settings_manager():
    """Test the enhanced settings manager implementation"""
    print("\n=== Testing Enhanced Settings Manager ===\n")
    
    # Create a backup first
    backup_path = await backup_database()
    print(f"Created backup at {backup_path if backup_path else 'N/A'}")
    
    # Load initial settings
    print("\n-- Initial Settings --")
    initial_settings = await load_settings()
    print(f"Loaded {len(initial_settings)} settings:")
    for key, value in initial_settings.items():
        print(f"  {key}: {value}")
    
    # Test updating a setting
    print("\n-- Updating a Setting --")
    test_setting = "level_up_coins"
    original_value = initial_settings.get(test_setting, 0)
    test_value = original_value + 100
    
    print(f"Updating {test_setting} from {original_value} to {test_value}")
    success = await save_setting(test_setting, test_value)
    print(f"Save success: {success}")
    
    # Load again to verify update
    print("\n-- Verifying Update --")
    updated_settings = await load_settings()
    updated_value = updated_settings.get(test_setting, 0)
    print(f"New value for {test_setting}: {updated_value}")
    
    if updated_value == test_value:
        print("✅ Update successful!")
    else:
        print("❌ Update failed!")
    
    # Test get_setting
    print("\n-- Testing get_setting --")
    direct_value = await get_setting(test_setting)
    print(f"Direct value of {test_setting}: {direct_value}")
    
    # Reset to original value
    print("\n-- Resetting to Original Value --")
    success = await save_setting(test_setting, original_value)
    print(f"Reset success: {success}")
    
    # Verify reset
    final_value = await get_setting(test_setting)
    print(f"Final value of {test_setting}: {final_value}")
    
    if final_value == original_value:
        print("✅ Reset successful!")
    else:
        print("❌ Reset failed!")
    
    print("\n=== Settings Manager Test Complete ===")
    
    return True

if __name__ == "__main__":
    asyncio.run(test_settings_manager())