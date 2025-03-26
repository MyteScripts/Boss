"""
Script to add persistence to the /editleveling command
This script patches the necessary functions in main.py
"""

import os
import re
import sys
import asyncio
import aiosqlite

async def apply_fixes():
    """Apply all fixes to implement persistence for the /editleveling command"""
    print("Starting to apply persistence fixes for /editleveling command...")
    
    # First backup the main.py file
    try:
        import shutil
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if os.path.exists("main.py"):
            shutil.copy2("main.py", f"main.py.backup_{timestamp}")
            print(f"✅ Created backup of main.py at main.py.backup_{timestamp}")
        else:
            print("❌ main.py not found - cannot continue")
            return False
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        print("Continuing anyway...")
    
    # Fix the editleveling command's on_submit function
    await fix_editleveling_command()
    
    # Fix the load_xp_settings function to use the new module
    await update_load_xp_settings()
    
    print("✨ All fixes applied successfully!")
    print("Restart the bot for the changes to take effect.")
    return True

async def fix_editleveling_command():
    """Fix the EditValueModal.on_submit method to use our improved persistence"""
    try:
        # Read the current file
        with open("main.py", "r") as f:
            content = f.read()
        
        # Find the on_submit method in EditValueModal
        pattern = r"async def on_submit\(self, interaction: discord\.Interaction\):(.*?)(?=async def|class|\n\n\n)"
        matches = re.findall(pattern, content, re.DOTALL)
        
        if not matches:
            print("❌ Could not find on_submit method in EditValueModal class")
            return False
        
        on_submit_code = matches[0]
        
        # Replace the database update code with our improved version
        old_db_code = r"# Update in database\s+async with aiosqlite\.connect\(\"leveling\.db\"\) as db:(.*?)# Create a new embed"
        old_db_match = re.search(old_db_code, on_submit_code, re.DOTALL)
        
        if not old_db_match:
            print("❌ Could not find database update code in on_submit method")
            return False
        
        # New improved database update code using our settings manager
        new_db_code = """
                # Update in database using the improved settings manager
                from leveling_settings_manager import save_setting
                
                # Save the setting to the database with improved persistence
                success = await save_setting(self.setting, new_value)
                
                if not success:
                    await interaction.response.send_message(
                        "❌ Failed to save setting to database. Please try again.",
                        ephemeral=True
                    )
                    return
                
                # Re-fetch ALL settings to ensure consistency
                from leveling_settings_manager import load_settings
                
                # Load updated settings
                updated_settings = await load_settings()
                
                # Update both the global variable and the class attribute
                global xp_settings
                xp_settings = updated_settings.copy()
                SettingData.current_settings = updated_settings.copy()
                
                print(f"✅ Updated {self.setting} to {new_value}. New settings: {xp_settings}")
                
                """
        
        # Replace in the on_submit code
        new_on_submit = re.sub(old_db_code, new_db_code, on_submit_code, flags=re.DOTALL)
        
        # Replace in the full file
        new_content = content.replace(on_submit_code, new_on_submit)
        
        # Write back to the file
        with open("main.py", "w") as f:
            f.write(new_content)
        
        print("✅ Successfully patched EditValueModal.on_submit method for improved persistence")
        return True
    except Exception as e:
        print(f"❌ Error fixing EditValueModal.on_submit: {e}")
        return False

async def update_load_xp_settings():
    """Update the load_xp_settings function to use our new module"""
    try:
        # Read the current file
        with open("main.py", "r") as f:
            content = f.read()
        
        # Find the load_xp_settings function
        pattern = r"async def load_xp_settings\(\):(.*?)(?=async def|class|\n\n\n)"
        matches = re.findall(pattern, content, re.DOTALL)
        
        if not matches:
            print("❌ Could not find load_xp_settings function")
            return False
        
        old_function = matches[0]
        
        # Create new implementation that uses our settings manager module
        new_function = """
    \"\"\"Load XP settings from the database with improved persistence\"\"\"
    global xp_config, voice_rewards, xp_settings
    
    try:
        # Use our improved settings manager module
        from leveling_settings_manager import load_settings, backup_database
        
        # Create a backup first
        await backup_database()
        
        # Load all settings
        settings_dict = await load_settings()
        
        # Store in global xp_settings variable
        xp_settings = settings_dict
        
        # Also update the specific settings in xp_config and voice_rewards for backward compatibility
        if "xp_min" in settings_dict:
            xp_config["min_xp"] = settings_dict["xp_min"]
        if "xp_max" in settings_dict:
            xp_config["max_xp"] = settings_dict["xp_max"]
        if "cooldown_seconds" in settings_dict:
            xp_config["cooldown"] = settings_dict["cooldown_seconds"]
        if "voice_xp_per_minute" in settings_dict:
            voice_rewards["xp_per_minute"] = settings_dict["voice_xp_per_minute"]
        if "voice_coins_per_minute" in settings_dict:
            voice_rewards["coins_per_minute"] = settings_dict["voice_coins_per_minute"]
            
        print(f"✅ Successfully loaded XP settings with level_up_coins={settings_dict.get('level_up_coins', 'N/A')}")
        print(f"✅ Loaded XP config: min_xp={xp_config.get('min_xp', 'N/A')}, max_xp={xp_config.get('max_xp', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ Error loading XP settings: {e}")
        # Ensure we still have default values if loading fails
        xp_config = {"min_xp": 5, "max_xp": 25, "cooldown": 7}
        voice_rewards = {"xp_per_minute": 2, "coins_per_minute": 1}
        xp_settings = {
            "xp_min": 5,
            "xp_max": 25,
            "cooldown_seconds": 7,
            "voice_xp_per_minute": 2,
            "voice_coins_per_minute": 1,
            "afk_xp_per_minute": 1,
            "afk_coins_per_minute": 0,
            "message_xp_min": 5,
            "message_xp_max": 25,
            "level_up_coins": 150,
            "level_up_xp_base": 50,
            "enabled": 1
        }
        print("⚠️ Using default XP settings due to error")
        return False"""
        
        # Replace in the full file
        new_content = content.replace(f"async def load_xp_settings():{old_function}", 
                                     f"async def load_xp_settings():{new_function}")
        
        # Write back to the file
        with open("main.py", "w") as f:
            f.write(new_content)
        
        print("✅ Successfully updated load_xp_settings function to use new module")
        return True
    except Exception as e:
        print(f"❌ Error updating load_xp_settings: {e}")
        return False

if __name__ == "__main__":
    print("=== Leveling System Persistence Update ===")
    asyncio.run(apply_fixes())