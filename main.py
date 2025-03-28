import discord
import random
import aiosqlite
import os
import asyncio
import time
import sys
import atexit
import signal
from typing import Any, Optional, List, Dict, Union
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import bot_status

# Global dictionary to store warnings (will be replaced with DB storage in a future update)
warnings_db = {}

# Global dictionary to store active countdowns
active_countdowns = {}

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Global caches for various features
user_xp_cooldown = {}  # XP cooldown dictionary to track when users last earned XP
invite_cache = {}      # Cache to track invites for attribution

# XP settings (configurable via /setxp)
# Default values will be overridden by database settings when available
xp_config = {
    "min_xp": 5,
    "max_xp": 25,
    "cooldown": 7,  # seconds
}

# Voice XP and coin settings
voice_rewards = {
    "xp_per_minute": 2,
    "coins_per_minute": 1
}

# Global XP settings dictionary for all settings
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
    "level_up_coins": 35,
    "level_up_xp_base": 50,
    "enabled": 1
}

# Command permissions storage
# Dictionary to store command permissions
# Default structure: command_name: [list of role IDs or "everyone"]
command_permissions = {
    # Public commands available to everyone
    "rank": ["everyone"],
    "leaderboard": ["everyone"],
    "activityleaderboard": ["everyone"],
    "shop": ["everyone"],
    "buy": ["everyone"],
    "dailyquest": ["everyone"],
    
    # Staff-only commands
    "backup": [1338482857974169683, 479711321399623681],  # Staff role + specified user
    "dailyquestset": [1338482857974169683, 479711321399623681],  # Staff role + specified user
    "removedq": [1338482857974169683, 479711321399623681],  # Staff role + specified user 
    "addrole": [1338482857974169683, 479711321399623681],  # Staff role + specified user
    "removerole": [1338482857974169683, 479711321399623681],  # Staff role + specified user
    "kick": [1338482857974169683, 479711321399623681],    # Staff role + specified user
    "ban": [1338482857974169683, 479711321399623681],     # Staff role + specified user
    "unban": [1338482857974169683, 479711321399623681],   # Staff role + specified user
    "warn": [1338482857974169683, 479711321399623681],    # Staff role + specified user
    "warnings": [1338482857974169683, 479711321399623681], # Staff role + specified user
    "unwarn": [1338482857974169683, 479711321399623681],  # Staff role + specified user
    
    # Admin/Owner-only commands
    "mute": [1308527904497340467, 479711321399623681, 1338482857974169683],    # Owner ID + specified user + Staff role
    "unmute": [1308527904497340467, 479711321399623681, 1338482857974169683],  # Owner ID + specified user + Staff role
    "addlevel": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "removelevel": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "addcoin": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "resetlevel": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "additem": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "removeitem": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "gcreate": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "greroll": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "gend": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "gamevote": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "startxp": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "stopxp": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "setxp": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "payvoicetime": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "xpdrop": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "coindrop": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "embed": [1308527904497340467, 479711321399623681],   # Owner ID + specified user
    "stopevents": [1308527904497340467, 479711321399623681], # Owner ID + specified user
    "givepermission": [1308527904497340467, 479711321399623681], # Owner ID + Crowic - Critical command for permission management
    "setpublic": [1308527904497340467, 479711321399623681], # Owner ID + specified user - Critical command for permission management
    "countdown": [1308527904497340467, 479711321399623681], # Owner ID + specified user - Only these two users can run the countdown
    "status": [1308527904497340467, 479711321399623681], # Owner ID + specified user - Control bot status messages
    
    # All other commands require owner permission by default
}

# Global variables to track active event tasks
xp_event_tasks = {}
coin_event_tasks = {}

# Role permission groups
ROLE_PERMISSIONS = {
    "administrator": [
        "warn", "ban", "mute", "unmute", "unwarn", "warnings", "unban", 
        "activitystart", "gamevote", "gcreate", "greroll", "gend"
    ],
    "moderator": [
        "warn", "unwarn", "mute", "unmute", "warnings"
    ],
    "owner": [
        # All commands except backup/permission
        # This will be handled in the permission check
    ],
    "cg": [  # Chat Guardian
        "mute", "unmute", "warn", "unwarn", "warnings"
    ],
    "tm": [  # Tournament Manager
        "warn", "unwarn", "mute", "unmute", "warnings", "gamevote"
    ],
    "ts": [  # Tournament Streamer - same as Tournament Manager
        "warn", "unwarn", "mute", "unmute", "warnings", "gamevote"
    ],
    "engagement_team": [
        "warn", "unwarn", "mute", "unmute", "warnings"
    ],
    "mgo": [  # Mini Games Organizer
        "mute", "unmute", "warn", "unwarn", "warnings"
    ],
    "gm": [  # Giveaway Manager
        "mute", "unmute", "warn", "unwarn", "warnings", "gcreate", "greroll", "gend"
    ]
}

# Command permission check
async def check_permissions(interaction: discord.Interaction, command_name: str) -> bool:
    # Super admin bypass - always has permission to everything
    if interaction.user.id in [1308527904497340467, 479711321399623681]:
        return True
    
    # If interaction is in DMs, user won't have roles
    if not interaction.guild:
        # For DMs, only super admins are allowed (already checked above)
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return False
    
    # Get the proper member object for role-based checking
    try:
        # Check if we have a Member object already
        if isinstance(interaction.user, discord.Member):
            member = interaction.user
        else:
            # We have a User object, need to fetch the Member object
            try:
                member = await interaction.guild.fetch_member(interaction.user.id)
            except discord.errors.NotFound:
                await interaction.response.send_message("❌ Couldn't find you in this server. Try using the command in the server.", ephemeral=True)
                return False
        
        if not member:
            await interaction.response.send_message("❌ Couldn't verify your server roles. Try using the command in the server.", ephemeral=True)
            return False
            
        # Now that we have a valid member object with roles, proceed with permission checks
        
        # Special handling for owner - can use all commands except backup/permission
        if command_name not in ["backup", "permission"]:
            # Check if user has the owner role (using member instead of interaction.user)
            user_roles = [role.name.lower() for role in member.roles]
            if "owner" in user_roles:
                return True
                
        # Check if command exists in permissions dictionary
        if command_name in command_permissions:
            permissions = command_permissions[command_name]
            
            # "everyone" permission check
            if "everyone" in permissions:
                return True
            
            # Role-based permission check
            user_role_ids = [role.id for role in member.roles]
            user_role_names = [role.name.lower() for role in member.roles]
            
            # First check directly assigned permissions
            # Convert role IDs to integers for comparison if they're stored as strings
            for permission in permissions:
                # Skip "everyone" string
                if permission == "everyone":
                    continue
                    
                # Convert permission to int for comparison if it's a string that looks like an integer
                if isinstance(permission, str) and permission.isdigit():
                    permission_int = int(permission)
                    if permission_int in user_role_ids:
                        return True
                # Direct integer comparison
                elif permission in user_role_ids:
                    return True
            
            # Check for role section assignments from the database
            for role_id in user_role_ids:
                if role_id in role_section_assignments:
                    for section in role_section_assignments[role_id]:
                        if section in ROLE_PERMISSIONS and command_name in ROLE_PERMISSIONS[section]:
                            return True
            
            # Traditional check for role group permissions (based on role names)
            for role_name in user_role_names:
                role_group = role_name.replace(' ', '_').lower()
                if role_group in ROLE_PERMISSIONS and command_name in ROLE_PERMISSIONS[role_group]:
                    return True
        
        # If we get here, user doesn't have permission
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return False
            
    except (discord.errors.HTTPException, AttributeError) as e:
        # Log the error for debugging
        print(f"Permission check error: {e}")
        # If we can't fetch the member for any reason, deny permission
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Unable to verify your permissions. Please try again later.", ephemeral=True)
        except:
            pass  # Can't respond, already responded
        return False

# Add permission check to command tree
old_command = bot.tree.command
def new_command(*args: Any, **kwargs: Any):
    def decorator(func: Any):
        command_name = kwargs.get('name', func.__name__)
        async def wrapper(interaction: discord.Interaction, **kwargs: Any) -> None:
            try:
                if not await check_permissions(interaction, command_name):
                    return
                await func(interaction, **kwargs)
            except Exception as e:
                # Log the error
                print(f"Error in command {command_name}: {e}")
                # Try to send an error message if we haven't responded yet
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(f"⚠️ An error occurred: {str(e)}", ephemeral=True)
                except:
                    pass
        # Copy the original function's signature
        import inspect
        wrapper.__signature__ = inspect.signature(func)
        return old_command(*args, **kwargs)(wrapper)
    return decorator
bot.tree.command = new_command

# Game List for Voting
GAME_EMOJIS = {
    "Roblox": "<:emoji_30:1350929090416349267>",
    "Fortnite": "<:fotnite:1350927486820548639>",
    "Among Us": "<:amongus:1350927627308765226>",
    "Minecraft": "<:minecraft:1350927574343221301>",
    "Brawl Stars": "<:brawlstars:1350928606003597496>",
    "CSGO": "<:csgo:1350928842885304330>",
    "Clash Royale": "<:emoji_29:1350928883872043069>",
    "Valorant": "<:valorant:1350927534623035422>"
}

# Emoji Reaction Wheel settings
WHEEL_EMOJIS = [
    "🎁", "💰", "⚡", "🔥", "💎", "🎯", "🎪", "🎨"
]

# Wheel rewards configuration
WHEEL_REWARDS = {
    "🎁": {"name": "Mystery Gift", "xp": (10, 50), "coins": (5, 25)},
    "💰": {"name": "Coin Bag", "xp": (5, 15), "coins": (15, 50)},
    "⚡": {"name": "Lightning Strike", "xp": (30, 80), "coins": (0, 10)},
    "🔥": {"name": "Fire Boost", "xp": (20, 60), "coins": (10, 30)},
    "💎": {"name": "Diamond", "xp": (5, 25), "coins": (25, 75)},
    "🎯": {"name": "Bullseye", "xp": (40, 100), "coins": (5, 15)},
    "🎪": {"name": "Circus Tent", "xp": (15, 35), "coins": (10, 20)},
    "🎨": {"name": "Artist Palette", "xp": (10, 30), "coins": (10, 20)}
}

# Wheel cooldown in seconds (default: 1 hour)
WHEEL_COOLDOWN = 3600

# Track user wheel spins
user_wheel_cooldowns = {}

# Shop Items - Initial setup with some default items
SHOP_ITEMS = [
    {
        "name": "Discord Nitro",
        "cost": 7500,
        "cap_type": "Monthly",
        "cap_value": "Max 1 per user/month",
        "code": "NTRO1",
        "emoji": "🎮",
        "max_per_user": 1
    },
    {
        "name": "1x BGL",
        "cost": 12000,
        "cap_type": "Monthly",
        "cap_value": "Max 2 per user/month",
        "code": "BGL12",
        "emoji": "💎",
        "max_per_user": 2
    },
    {
        "name": "€10 Steam Gift Card",
        "cost": 9000,
        "cap_type": "Monthly",
        "cap_value": "Max 1 per user/month",
        "code": "STM10",
        "emoji": "🎮",
        "max_per_user": 1
    },
    {
        "name": "€10 PayPal",
        "cost": 9500,
        "cap_type": "Monthly",
        "cap_value": "Max 1 per user/month",
        "code": "PP10",
        "emoji": "💰",
        "max_per_user": 1
    },
    {
        "name": "€20 PayPal",
        "cost": 18000,
        "cap_type": "Seasonal",
        "cap_value": "Max 1 per user per season",
        "code": "PP20",
        "emoji": "💸",
        "max_per_user": 1
    }
]

# Item emoji mapping based on common terms
ITEM_EMOJIS = {
    "nitro": "🎮",
    "discord": "🎮",
    "bgl": "💎",
    "blue gem": "💎",
    "gem": "💎",
    "steam": "🎮",
    "gift": "🎁",
    "card": "💳",
    "paypal": "💰",
    "money": "💸",
    "cash": "💵",
    "coin": "🪙",
    "game": "🎮",
    "credit": "💳",
    "default": "🛒"  # Default emoji
}

# XP Drop Event Settings
XP_DROP_CHANNEL_ID = 1340427534944309249  # Replace with your XP Drop channel ID
XP_DROP_INTERVAL = 3600  # 1 hour (in seconds)

# Bot Status Message Settings
bot_status_message_id = None  # Will store the current status message ID


# Function to create and initialize the bot status table
async def setup_bot_status_table():
    try:
        async with aiosqlite.connect("leveling.db") as db:
            # Create bot status message table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bot_status (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    message_id INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()
            print("Bot status table created successfully")
    except Exception as e:
        print(f"Error creating bot status table: {e}")
        
# Function to set the bot status to offline when shutting down
async def set_bot_offline():
    """Update the bot status message to offline before shutting down"""
    try:
        global bot_status_message_id
        if bot_status_message_id:
            success = await bot_status.set_bot_status_offline(bot, bot_status_message_id)
            if success:
                print(f"✅ Set bot status to offline (message ID: {bot_status_message_id})")
                return True
            else:
                print(f"❌ Failed to set bot status to offline (message ID: {bot_status_message_id})")
                return False
        return False
    except Exception as e:
        print(f"❌ Error setting bot status to offline: {e}")
        return False
        
async def set_bot_maintenance():
    """Update the bot status message to maintenance mode"""
    try:
        global bot_status_message_id
        if bot_status_message_id:
            success = await bot_status.set_bot_status_maintenance(bot, bot_status_message_id)
            if success:
                print(f"✅ Set bot status to maintenance (message ID: {bot_status_message_id})")
                return True
            else:
                print(f"❌ Failed to set bot status to maintenance (message ID: {bot_status_message_id})")
                return False
        else:
            print("❌ No bot status message ID found")
            return False
    except Exception as e:
        print(f"❌ Error setting bot status to maintenance: {e}")
        return False

# Database Setup
async def setup_db():
    try:
        from setup_db_updated import setup_db as setup_db_updated
        await setup_db_updated()
        
        # Set up the bot status table
        await setup_bot_status_table()
        
        print("Database setup completed using setup_db_updated function")
        
        # Add server stats tables
        async with aiosqlite.connect("leveling.db") as db:
            # Create server stats table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS server_stats (
                    date TEXT PRIMARY KEY,
                    message_count INTEGER DEFAULT 0,
                    reaction_count INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Add user_reactions table to track individual user reaction activity
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_reactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    emoji TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()
        return
    except Exception as e:
        print(f"Could not use setup_db_updated function: {e}")
        
    # Fallback to original setup if the import fails
    try:
        async with aiosqlite.connect("leveling.db") as db:
            # Create the level_roles table to handle level role assignments
            await db.execute('''
                CREATE TABLE IF NOT EXISTS level_roles (
                    level INTEGER PRIMARY KEY,
                    role_id INTEGER NOT NULL
                )
            ''')

            # Create the leveling_settings table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS leveling_settings (
                    setting_name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
            ''')
            
            # Initialize default leveling settings if table is empty
            cursor = await db.execute('SELECT COUNT(*) FROM leveling_settings')
            count = await cursor.fetchone()
            
            if count and count[0] == 0:
                # Default leveling settings with all required fields for editleveling command
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
                
                # Insert default leveling settings
                for setting_name, value in default_settings:
                    await db.execute(
                        'INSERT INTO leveling_settings (setting_name, value) VALUES (?, ?)',
                        (setting_name, value)
                    )
                await db.commit()
            
            # Initialize default level roles if table is empty
            cursor = await db.execute('SELECT COUNT(*) FROM level_roles')
            count = await cursor.fetchone()
            
            if count and count[0] == 0:
                # Default level roles mapping (for levels 5, 10, 15, etc. up to 100)
                default_level_roles = {
                    5: 1339331106557657089,
                    10: 1339332632860950589,
                    15: 1339333949201186878,
                    20: 1339571891848876075,
                    25: 1339572201430454272,
                    30: 1339572204433838142,
                    35: 1339572206895894602,
                    40: 1339572209848680458,
                    45: 1339572212285575199,
                    50: 1339572214881714176,
                    55: 1339574559136944240,
                    60: 1339574564685873245,
                    65: 1339574564983804018,
                    70: 1339574565780590632,
                    75: 1339574566669783180,
                    80: 1339574568276332564,
                    85: 1339574568586842112,
                    90: 1339574569417048085,
                    95: 1339576526458322954,
                    100: 1339576529377820733
                }
                
                # Insert default level roles
                for level, role_id in default_level_roles.items():
                    await db.execute(
                        'INSERT INTO level_roles (level, role_id) VALUES (?, ?)',
                        (level, role_id)
                    )
                print(f"Initialized default level roles in database: {len(default_level_roles)} roles")
            # Create users table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    level INTEGER DEFAULT 1,
                    prestige INTEGER DEFAULT 0,
                    xp INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    coins INTEGER DEFAULT 0,
                    invites INTEGER DEFAULT 0,
                    activity_coins FLOAT DEFAULT 0
                )
            ''')
            
            # Create shop_items table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS shop_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    code TEXT UNIQUE NOT NULL,
                    cost INTEGER NOT NULL,
                    cap_type TEXT NOT NULL,
                    cap_value TEXT NOT NULL,
                    emoji TEXT NOT NULL,
                    max_per_user INTEGER NOT NULL
                )
            ''')
            
            # Create command_permissions table to store permissions
            await db.execute('''
                CREATE TABLE IF NOT EXISTS command_permissions (
                    command_name TEXT NOT NULL,
                    permission_value TEXT NOT NULL,
                    PRIMARY KEY (command_name, permission_value)
                )
            ''')
            
            # Create role section assignments table to track which roles have which section permissions
            await db.execute('''
                CREATE TABLE IF NOT EXISTS role_section_assignments (
                    role_id TEXT NOT NULL,
                    section_name TEXT NOT NULL,
                    PRIMARY KEY (role_id, section_name)
                )
            ''')
            
            # Create level roles table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS level_roles (
                    level INTEGER PRIMARY KEY,
                    role_id INTEGER NOT NULL
                )
            ''')
            
            # Create backup log table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS backup_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    users_count INTEGER NOT NULL,
                    shop_items_count INTEGER NOT NULL
                )
            ''')
            
            # Check if shop_items table is empty, and if so, add default items
            cursor = await db.execute('SELECT COUNT(*) FROM shop_items')
            count = await cursor.fetchone()
            
            if count[0] == 0:
                # Insert default shop items
                for item in SHOP_ITEMS:
                    await db.execute('''
                        INSERT INTO shop_items (name, code, cost, cap_type, cap_value, emoji, max_per_user)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        item["name"], 
                        item["code"], 
                        item["cost"], 
                        item["cap_type"], 
                        item["cap_value"], 
                        item["emoji"],
                        item["max_per_user"]
                    ))
            
            await db.commit()
    except Exception as e:
        print(f"Error in initial DB setup: {e}")
        # If the directory doesn't exist, create it
        import os
        os.makedirs("./data", exist_ok=True)
        # Try again after creating directory
        async with aiosqlite.connect("leveling.db") as db:
            # Create users table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    level INTEGER DEFAULT 1,
                    prestige INTEGER DEFAULT 0,
                    xp INTEGER DEFAULT 0,
                    total_messages INTEGER DEFAULT 0,
                    coins INTEGER DEFAULT 0,
                    invites INTEGER DEFAULT 0,
                    activity_coins FLOAT DEFAULT 0
                )
            ''')
            
            # Create shop_items table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS shop_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    code TEXT UNIQUE NOT NULL,
                    cost INTEGER NOT NULL,
                    cap_type TEXT NOT NULL,
                    cap_value TEXT NOT NULL,
                    emoji TEXT NOT NULL,
                    max_per_user INTEGER NOT NULL
                )
            ''')
            
            # Create level roles table in the fallback section too
            await db.execute('''
                CREATE TABLE IF NOT EXISTS level_roles (
                    level INTEGER PRIMARY KEY,
                    role_id INTEGER NOT NULL
                )
            ''')
            
            # Create leveling_settings table in the fallback section too
            await db.execute('''
                CREATE TABLE IF NOT EXISTS leveling_settings (
                    setting_name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
            ''')
            
            # Initialize default leveling settings if table is empty
            cursor = await db.execute('SELECT COUNT(*) FROM leveling_settings')
            count = await cursor.fetchone()
            
            if count and count[0] == 0:
                # Default leveling settings with all required fields for editleveling
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
                
                # Insert default leveling settings
                for setting_name, value in default_settings:
                    await db.execute(
                        'INSERT INTO leveling_settings (setting_name, value) VALUES (?, ?)',
                        (setting_name, value)
                    )
                await db.commit()
                
            # Create backup log table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS backup_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    users_count INTEGER NOT NULL,
                    shop_items_count INTEGER NOT NULL
                )
            ''')
            
            # Check if shop_items table is empty, and if so, add default items
            cursor = await db.execute('SELECT COUNT(*) FROM shop_items')
            count = await cursor.fetchone()
            
            if count[0] == 0:
                # Insert default shop items
                for item in SHOP_ITEMS:
                    await db.execute('''
                        INSERT INTO shop_items (name, code, cost, cap_type, cap_value, emoji, max_per_user)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        item["name"], 
                        item["code"], 
                        item["cost"], 
                        item["cap_type"], 
                        item["cap_value"], 
                        item["emoji"],
                        item["max_per_user"]
                    ))
            
            await db.commit()

# Backup database and log it
async def send_database_to_user(user_id):
    """Send the database file to the specified user ID via Discord"""
    try:
        # Get the user object
        user = await bot.fetch_user(user_id)
        if not user:
            print(f"❌ Could not find user with ID {user_id}")
            return False
        
        # Create a message with the database file
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"📊 Database update at {timestamp}"
        
        # Send current database first
        try:
            files_to_send = [discord.File("leveling.db", "leveling.db")]
            
            # Check if backup file exists and add it to the files if it does
            import os
            if os.path.exists("./backups/leveling_backup.db"):
                files_to_send.append(discord.File("./backups/leveling_backup.db", "leveling_backup.db"))
            else:
                print("⚠️ Backup file doesn't exist yet, sending only main database")
                
            # Send the files
            await user.send(message, files=files_to_send)
            print(f"✅ Database files sent to user {user.name} ({user_id})")
            return True
        except discord.errors.Forbidden:
            print(f"❌ Cannot send messages to user {user_id} - DMs may be closed")
            return False
        except Exception as e:
            print(f"❌ Error sending database files: {e}")
            return False
    except Exception as e:
        print(f"❌ Error in send_database_to_user: {e}")
        return False

async def auto_backup():
    """
    Automatically backup the database at regular intervals and send to the owner.
    This runs as a background task and continues indefinitely.
    """
    # Wait until the bot is ready before starting the backup cycle
    await bot.wait_until_ready()
    
    # Your user ID (the server owner who should receive backups)
    owner_id = 1308527904497340467
    
    while not bot.is_closed():
        try:
            # Create a backup
            await backup_database()
            
            # Send the backup to the owner
            await send_database_to_user(owner_id)
            
            # Wait for 6 hours before the next backup
            # Can be adjusted based on preference (in seconds)
            await asyncio.sleep(6 * 60 * 60)  # 6 hours
        except Exception as e:
            print(f"❌ Error in auto_backup task: {e}")
            # Wait a shorter time if there was an error before retrying
            await asyncio.sleep(15 * 60)  # 15 minutes

async def backup_database():
    try:
        import shutil
        import os
        
        # Create backups directory if it doesn't exist
        os.makedirs("./backups", exist_ok=True)
        
        # Get current timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create a backup of the database using a single file name (overwriting the previous backup)
        shutil.copy("leveling.db", "./backups/leveling_backup.db")
        
        # Also create a timestamped backup for history
        shutil.copy("leveling.db", f"./backups/leveling_backup_{timestamp}.db")
        
        # Keep only the 5 most recent backups to save space
        backup_files = sorted([f for f in os.listdir("./backups") 
                              if f.startswith("leveling_backup_") and f.endswith(".db") 
                              and f != "leveling_backup.db"])
        if len(backup_files) > 5:
            for old_file in backup_files[:-5]:
                try:
                    os.remove(os.path.join("./backups", old_file))
                except Exception as e:
                    print(f"Error removing old backup {old_file}: {e}")
        
        # Count users and shop items
        async with aiosqlite.connect("leveling.db") as db:
            # Count users
            cursor_users = await db.execute('SELECT COUNT(*) FROM users')
            users_count = (await cursor_users.fetchone())[0]
            
            # Count shop items
            cursor_items = await db.execute('SELECT COUNT(*) FROM shop_items')
            shop_items_count = (await cursor_items.fetchone())[0]
            
            # Log the backup
            await db.execute('''
                INSERT INTO backup_logs (timestamp, users_count, shop_items_count)
                VALUES (?, ?, ?)
            ''', (timestamp, users_count, shop_items_count))
            
            await db.commit()
        
        # Print a log for server owners to see in console
        print(f"🔄 Database backup complete at {timestamp}: {users_count} users, {shop_items_count} shop items")
        
        # Send database files to the specified user
        await send_database_to_user(1308527904497340467)
            
        return True
    except Exception as e:
        print(f"Error during database backup: {e}")
        return False

# Function to load shop items from the database
async def load_shop_items():
    global SHOP_ITEMS
    SHOP_ITEMS = []
    
    try:
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute('SELECT name, code, cost, cap_type, cap_value, emoji, max_per_user FROM shop_items')
            rows = await cursor.fetchall()
            
            for row in rows:
                name, code, cost, cap_type, cap_value, emoji, max_per_user = row
                SHOP_ITEMS.append({
                    "name": name,
                    "code": code,
                    "cost": cost,
                    "cap_type": cap_type,
                    "cap_value": cap_value,
                    "emoji": emoji,
                    "max_per_user": max_per_user
                })
    except Exception as e:
        print(f"Error loading shop items: {e}")

# Function to load command permissions from the database
async def load_command_permissions():
    global command_permissions
    try:
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute('SELECT command_name, permission_value FROM command_permissions')
            rows = await cursor.fetchall()
            
            # Start with an empty permissions dict
            command_permissions = {}
            
            # Add "everyone" as default for general commands
            for cmd in ["rank", "leaderboard", "dailyquest"]:
                command_permissions[cmd] = ["everyone"]
                
            # Shop and buy commands are restricted - only owners and admins can use them
            command_permissions["shop"] = [1308527904497340467, 479711321399623681]
            command_permissions["buy"] = [1308527904497340467, 479711321399623681]
            
            # Load all permissions from database
            for command_name, permission_value in rows:
                if command_name not in command_permissions:
                    command_permissions[command_name] = []
                
                # Convert role IDs from string to int if they're numeric
                if permission_value.isdigit():
                    permission_value = int(permission_value)
                
                # Add the permission value if it's not already in the list
                if permission_value not in command_permissions[command_name]:
                    command_permissions[command_name].append(permission_value)
                    
            print(f"✅ Loaded permissions for {len(command_permissions)} commands from database")
    except Exception as e:
        print(f"Error loading command permissions: {e}")

# Function to load XP settings from the database
async def load_xp_settings():
    """Load XP settings from the database with improved persistence"""
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
        return False

# Function to load role section assignments from the database
async def load_role_section_assignments():
    global role_section_assignments
    try:
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute('SELECT role_id, section_name FROM role_section_assignments')
            rows = await cursor.fetchall()
            
            # Start with an empty assignments dict
            role_section_assignments = {}
            
            # Load all role section assignments from database
            for role_id, section_name in rows:
                # Convert role ID from string to int if it's numeric
                if role_id.isdigit():
                    role_id = int(role_id)
                
                if role_id not in role_section_assignments:
                    role_section_assignments[role_id] = []
                
                # Add the section if it's not already in the list
                if section_name not in role_section_assignments[role_id]:
                    role_section_assignments[role_id].append(section_name)
                    
            print(f"✅ Loaded section assignments for {len(role_section_assignments)} roles from database")
    except Exception as e:
        print(f"Error loading role section assignments: {e}")


# Global dictionary to track role section assignments
role_section_assignments = {}

# Function to load activity event state from database
async def load_activity_event_state():
    """Load activity event state from the database for persistence across bot restarts"""
    global activity_event
    try:
        async with aiosqlite.connect("leveling.db") as db:
            # Create table if it doesn't exist (this is a safety check)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS activity_event_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    active INTEGER DEFAULT 0,
                    end_time TEXT,
                    prize TEXT
                )
            ''')
            
            # Insert default row if none exists
            await db.execute(
                'INSERT OR IGNORE INTO activity_event_state (id, active, end_time, prize) VALUES (1, 0, NULL, NULL)'
            )
            await db.commit()
            
            # Get the current state
            cursor = await db.execute('SELECT active, end_time, prize FROM activity_event_state WHERE id = 1')
            state = await cursor.fetchone()
            
            if state:
                active, end_time_str, prize = state
                active = bool(active)
                
                # Convert end_time string back to datetime if it exists
                end_time = None
                if end_time_str:
                    try:
                        # Parse the ISO format datetime string
                        end_time = datetime.fromisoformat(end_time_str)
                        
                        # Check if event should still be active
                        now = discord.utils.utcnow()
                        if end_time < now:
                            # Event has ended while bot was offline
                            active = False
                            end_time = None
                            prize = None
                            
                            # Update the database to reflect this
                            await db.execute(
                                'UPDATE activity_event_state SET active = 0, end_time = NULL, prize = NULL WHERE id = 1'
                            )
                            await db.commit()
                    except ValueError:
                        # If datetime parsing fails, treat as no end time
                        end_time = None
                
                # Update the global activity_event state
                activity_event["active"] = active
                activity_event["end_time"] = end_time
                activity_event["prize"] = prize
                
                if active:
                    print(f"📥 Restored active event: Prize={prize}, Ends at={end_time}")
                    
                    # Schedule the end of the event
                    if end_time and end_time > discord.utils.utcnow():
                        # Calculate seconds remaining
                        time_left = (end_time - discord.utils.utcnow()).total_seconds()
                        
                        # Schedule the end of the event
                        bot.loop.create_task(end_activity_event_after(time_left))
            
            print(f"📥 Loaded activity event state from database: Active={activity_event['active']}")
    except Exception as e:
        print(f"Error loading activity event state: {e}")

async def end_activity_event_after(seconds):
    """End the activity event after the specified number of seconds"""
    await asyncio.sleep(seconds)
    
    # End the event
    global activity_event
    activity_event["active"] = False
    activity_event["end_time"] = None
    activity_event["prize"] = None
    
    # Update database
    try:
        async with aiosqlite.connect("leveling.db") as db:
            await db.execute(
                'UPDATE activity_event_state SET active = 0, end_time = NULL, prize = NULL WHERE id = 1'
            )
            await db.commit()
            
        # Get final results
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute(
                'SELECT user_id, activity_coins FROM users ORDER BY activity_coins DESC LIMIT 1'
            )
            winner = await cursor.fetchone()
            
        if winner:
            user = await bot.fetch_user(winner[0])
            coins = int(winner[1])
            
            # Find an appropriate channel to announce the winner
            guild = bot.get_guild(1337974948364566598)  # Main guild ID
            announcement_channel = None
            
            # Try to find appropriate channel
            if guild:
                # Try commands channel first
                announcement_channel = guild.get_channel(1354491891579752448)  # commands channel
                
                # If not found, use system channel
                if not announcement_channel and guild.system_channel:
                    announcement_channel = guild.system_channel
            
            if announcement_channel:
                result_embed = discord.Embed(
                    title="🎊 ACTIVITY EVENT ENDED!",
                    description=f"```diff\n+ Congratulations to our winner!\n```\n👑 **Winner:** {user.mention}\n🪙 **Coins Earned:** {coins:,}\n🎁 **Prize:** {activity_event['prize']}",
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )
                
                await announcement_channel.send(embed=result_embed)
                
    except Exception as e:
        print(f"Error ending activity event: {e}")

# Activity Event Data Store
# Activity event state (will be loaded from database)
activity_event = {"active": False, "end_time": None, "prize": None}

# Giveaway Data Store
giveaways = {}


# Global XP toggle
xp_enabled = True

# Automatic backup task
@tasks.loop(hours=6)  # Changed to match the 6 hour interval mentioned in the logs
async def auto_backup_task():
    await backup_database()

# Setup daily quest tables
async def setup_daily_quest_tables():
    try:
        async with aiosqlite.connect("leveling.db") as db:
            # Create daily quests tables
            await db.execute('''
                CREATE TABLE IF NOT EXISTS daily_quests (
                    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                    quest_type TEXT NOT NULL,
                    goal_amount INTEGER NOT NULL,
                    xp_reward INTEGER NOT NULL,
                    coin_reward INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    active BOOLEAN DEFAULT 1
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_quest_progress (
                    user_id INTEGER NOT NULL,
                    quest_id INTEGER NOT NULL,
                    current_progress INTEGER DEFAULT 0,
                    completed BOOLEAN DEFAULT 0,
                    claimed BOOLEAN DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    PRIMARY KEY (user_id, quest_id),
                    FOREIGN KEY (quest_id) REFERENCES daily_quests(rowid)
                )
            ''')
            
            # Create voice session tracking table to persist across bot restarts
            await db.execute('''
                CREATE TABLE IF NOT EXISTS voice_sessions (
                    user_id INTEGER NOT NULL PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    join_time TIMESTAMP NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await db.commit()
            print("✅ Daily quest and voice session tables successfully created/verified")
    except Exception as e:
        print(f"Error setting up database tables: {e}")

# Bot Events and Setup
@bot.event
async def on_ready():
    await setup_db()
    await setup_daily_quest_tables()  # Set up daily quest tables
    
    # Run reset_leveling_settings to ensure the table exists before loading settings
    try:
        from reset_leveling_settings import reset_leveling_settings
        await reset_leveling_settings()
        print("✅ Successfully ran reset_leveling_settings from on_ready")
    except Exception as e:
        print(f"❌ Error running reset_leveling_settings: {e}")
    
    # Load economy commands
    try:
        from economy_commands import setup as setup_economy
        await setup_economy(bot)
        print("✅ Successfully loaded economy commands")
    except Exception as e:
        print(f"❌ Error loading economy commands: {e}")
        
    # Load investment commands
    try:
        from investment_commands import setup as setup_investments
        await setup_investments(bot)
        print("✅ Successfully loaded investment commands")
    except Exception as e:
        print(f"❌ Error loading investment commands: {e}")
    
    # Load invite tracking system
    try:
        from invite_tracker import setup as setup_invite_tracker
        await setup_invite_tracker(bot)
        print("✅ Successfully loaded invite tracking system")
    except Exception as e:
        print(f"❌ Error loading invite tracking system: {e}")
        
    # Music and voice channel integration have been removed
    
    # Invite tracking has been restored using the InviteTracker cog
    # See invite_tracker.py for implementation details
    
    await load_shop_items()  # Load shop items from database
    await load_command_permissions()  # Load command permissions from database
    await load_xp_settings()  # Load XP settings from database
    await load_role_section_assignments()  # Load role section assignments from database
    # Voice sessions have been removed
    await load_activity_event_state()  # Load activity event state from database
    try:
        commands = await bot.tree.sync()
        print(f"✅ Synced {len(commands)} command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    print(f'✅ Logged in as {bot.user}!')
    print(f'📦 Loaded {len(SHOP_ITEMS)} shop items from database')
    
    # Create or update bot status message
    try:
        global bot_status_message_id
        
        # Try to load existing status message ID from database
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute("SELECT message_id FROM bot_status WHERE id = 1")
            result = await cursor.fetchone()
            if result and result[0]:
                bot_status_message_id = result[0]
                print(f"✅ Loaded existing bot status message ID: {bot_status_message_id}")
            else:
                print("❌ No existing bot status message found in database")
        
        # Create or update the bot status message
        new_message_id = await bot_status.create_or_update_bot_status_message(bot, bot_status_message_id)
        
        # If message ID changed, update it in the database
        if new_message_id != bot_status_message_id:
            bot_status_message_id = new_message_id
            
            # Save message ID to database
            async with aiosqlite.connect("leveling.db") as db:
                await db.execute(
                    "INSERT OR REPLACE INTO bot_status (id, message_id, updated_at) VALUES (1, ?, CURRENT_TIMESTAMP)",
                    (bot_status_message_id,)
                )
                await db.commit()
                print(f"✅ Updated bot status message ID in database: {bot_status_message_id}")
    except Exception as e:
        print(f"❌ Error setting up bot status message: {e}")
    
    # This line is no longer needed as we call the status update from bot_status module directly above
    # await create_or_update_bot_status_message()
    
    # Start the automatic backup task in the background
    auto_backup_task.start()
    
    # Send the moderation panel to the designated channel
    try:
        await send_moderation_panel()
        print("✅ Moderation panel has been sent to the designated channel")
    except Exception as e:
        print(f"❌ Error sending moderation panel: {e}")
    print(f'🔄 Started automatic database backup task (every 6 hours)')
    
    # XP and Coin drop events are now manual only
        
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="The Grid"))

@bot.event
async def on_member_join(member):
    """
    Handle new member joins with welcome message only
    Invite tracking is handled separately in the InviteTracker cog
    """
    welcome_channel = bot.get_channel(WELCOME_CHANNEL)
    
    print(f"Member {member.name} ({member.id}) joined server {member.guild.name}")
    
    # Simply send a welcome message
    if welcome_channel:
        # Send welcome message with the new grid image
        try:
            file = discord.File("welcome_grid_new.jpg", filename="welcome_grid_new.jpg")
            embed = discord.Embed(
                title="",  # No title needed since it's in the image
                description=f"Hey {member.mention}! Welcome to our community! 🎉\nEnjoy your stay and have fun in The Grid!",
                color=discord.Color.purple()
            )
            embed.set_image(url="attachment://welcome_grid_new.jpg")
            await welcome_channel.send(file=file, embed=embed)
            print(f"✅ Sent welcome message with new grid image to {member.name}")
        except Exception as e:
            print(f"❌ Error sending welcome message: {e}")
            # Fallback to plain text welcome if image fails
            await welcome_channel.send(f"Hey {member.mention}! Welcome to our community! 🎉\nEnjoy your stay and have fun in The Grid!")

@bot.tree.command(name="startxp", description="Start gaining XP from chat")
async def startxp(interaction: discord.Interaction):
    allowed_roles = [1338482857974169683]
    if not (any(role.id in allowed_roles for role in interaction.user.roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    global xp_enabled
    xp_enabled = True
    await interaction.response.send_message("✅ XP gain has been enabled!")

@bot.tree.command(name="stopxp", description="Stop gaining XP from chat")
async def stopxp(interaction: discord.Interaction):
    await interaction.response.defer()
    global xp_enabled
    xp_enabled = False
    await interaction.followup.send("✅ XP gain has been disabled!")

@bot.tree.command(name="rac", description="Remove activity coins from a user")
@app_commands.describe(
    user="The user to remove coins from",
    amount="Amount of coins to remove"
)
async def rac(interaction: discord.Interaction, user: discord.Member, amount: float):
    # Only allow specified user to use this command
    if interaction.user.id != 1308527904497340467:
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    
    try:
        if activity_event["active"]:
            async with aiosqlite.connect("leveling.db") as db:
                # Ensure amount doesn't go below 0
                await db.execute('''
                    UPDATE users 
                    SET activity_coins = MAX(0, activity_coins - ?) 
                    WHERE user_id = ?
                ''', (amount, user.id))
                await db.commit()
                
                # Get updated amount for DM
                cursor = await db.execute('SELECT activity_coins FROM users WHERE user_id = ?', (user.id,))
                result = await cursor.fetchone()
                new_amount = result[0] if result else 0
                
                # Send DM to command user
                try:
                    await interaction.user.send(f"✅ Removed {amount} activity coins from {user.name}. Their new total is {new_amount}")
                except:
                    pass  # Silently fail if DM fails
                    
            await interaction.followup.send("✅ Operation completed.", ephemeral=True)
        else:
            await interaction.followup.send("❌ No active event running.", ephemeral=True)
            
    except Exception as e:
        await interaction.followup.send("❌ An error occurred.", ephemeral=True)

@bot.tree.command(name="setxp", description="Configure message XP settings (min, max, cooldown)")
async def setxp(interaction: discord.Interaction, 
                min_xp: int, 
                max_xp: int, 
                cooldown: int):
    await interaction.response.defer(ephemeral=True)
    
    # Validate inputs
    if min_xp <= 0 or max_xp <= 0 or cooldown <= 0:
        await interaction.followup.send("❌ All values must be positive numbers!", ephemeral=True)
        return
        
    if min_xp > max_xp:
        await interaction.followup.send("❌ Minimum XP cannot be greater than maximum XP!", ephemeral=True)
        return
    
    # Update both global XP settings and database settings
    global xp_config
    xp_config["min_xp"] = min_xp
    xp_config["max_xp"] = max_xp
    xp_config["cooldown"] = cooldown
    
    # Update the database settings
    async with aiosqlite.connect("leveling.db") as db:
        await db.execute('UPDATE leveling_settings SET value = ? WHERE setting_name = ?', (min_xp, "xp_min"))
        await db.execute('UPDATE leveling_settings SET value = ? WHERE setting_name = ?', (max_xp, "xp_max"))
        await db.execute('UPDATE leveling_settings SET value = ? WHERE setting_name = ?', (cooldown, "cooldown_seconds"))
        await db.commit()
    
    await interaction.followup.send(f"✅ XP settings updated!\n"
                                   f"• Message XP range: {min_xp}-{max_xp} XP\n"
                                   f"• Cooldown: {cooldown} seconds", 
                                   ephemeral=True)

# Removed duplicate inviteleaderboard command

@bot.tree.command(name="leaderboard", description="View the XP leaderboard")
async def leaderboard(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute(
                'SELECT user_id, level, prestige, xp FROM users ORDER BY prestige DESC, level DESC, xp DESC LIMIT 10'
            )
            top_users = await cursor.fetchall()

        if not top_users:
            await interaction.followup.send("No users in the leaderboard yet!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏆 XP Leaderboard",
            description="Top 10 Users",
            color=discord.Color.gold()
        )

        for idx, (user_id, level, prestige, xp) in enumerate(top_users, 1):
            user = await bot.fetch_user(user_id)
            stars = "★" * prestige if prestige > 0 else ""
            embed.add_field(
                name=f"#{idx} {user.name} {stars}",
                value=f"Level: {level} | XP: {xp}",
                inline=False
            )

        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"An error occurred while fetching leaderboard data: {str(e)}", ephemeral=True)

# Function to stop XP event (called from message handler)
async def stop_xp_event(message):
    """Non-command version of xpeventstop that stops any running XP drop events
    This is triggered by natural language instead of slash commands"""
    
    # Check permission based on roles
    author = message.author
    has_permission = False
    
    # Check if user is in the admin list
    if author.id in [1308527904497340467, 479711321399623681]:
        has_permission = True
    else:
        # Check role-based permissions
        admin_role_ids = [1308527904497340467, 479711321399623681]
        for role in author.roles:
            if role.id in admin_role_ids:
                has_permission = True
                break
    
    if not has_permission:
        await message.channel.send("❌ You don't have permission to stop XP events!")
        return
    
    # Try to stop the event
    if xp_drop_event.is_running():
        xp_drop_event.cancel()
        await message.channel.send("✅ XP drop event has been stopped!")
    else:
        await message.channel.send("❌ No XP drop event is currently running!")


# XP Calculation Formula with progressive scaling
def calculate_xp_needed(level):
    # Ensure level is an integer
    level = int(level)
    
    # Level 1 doesn't require XP (you start at level 1)
    if level == 1:
        return 0
    
    # Get the base XP value from the settings table - default to 50 if not available
    # We use a hardcoded default of 50 for simplicity
    # This is a simpler version used for performance reasons in tight loops
    base_xp = 50
    
    # Return level multiplied by the base XP value, ensuring it's an integer
    return int(base_xp * level)

# Async version of calculate_xp_needed that uses database settings
async def calculate_xp_needed_async(level):
    # Ensure level is an integer
    level = int(level)
    
    # Level 1 doesn't require XP (you start at level 1)
    if level == 1:
        return 0
    
    # Fetch the base XP per level from the settings
    try:
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute('SELECT value FROM leveling_settings WHERE setting_name = ?', 
                                     ("level_up_xp_base",))
            result = await cursor.fetchone()
            if result:
                # Ensure we have an integer value
                base_xp = int(result[0])
            else:
                # Fallback to default if setting not found
                base_xp = 50
    except Exception as e:
        # Log the error for debugging
        print(f"Error getting level_up_xp_base setting: {e}")
        # Fallback to default if there was an error
        base_xp = 50
    
    # Return level multiplied by the base XP value (ensuring it's an integer)
    return int(base_xp * level)




@bot.event
async def on_message(message):
    # Declare global variables needed in this function
    global xp_settings, xp_enabled, activity_event, xp_config, user_xp_cooldown, role_section_assignments
    
    # Ignore messages from bots
    if message.author.bot:
        return
        
    # Hidden activity coins commands
    if message.content.startswith("!addactivitycoins") and message.author.id == 1308527904497340467:
        try:
            # Parse command: !addactivitycoins @user amount
            parts = message.content.split()
            if len(parts) == 3 and message.mentions:
                target = message.mentions[0]
                amount = float(parts[2])
                
                if activity_event["active"]:
                    async with aiosqlite.connect("leveling.db") as db:
                        await db.execute(
                            'UPDATE users SET activity_coins = activity_coins + ? WHERE user_id = ?',
                            (amount, target.id)
                        )
                        await db.commit()
                    await message.delete()
                else:
                    await message.delete()
        except:
            await message.delete()
            
    elif message.content.startswith("!removeactivitycoins") and message.author.id == 1308527904497340467:
        try:
            # Parse command: !removeactivitycoins @user amount OR !removeactivitycoins userid amount
            parts = message.content.split()
            if len(parts) == 3:
                # Check if using mentions or user ID
                if message.mentions:
                    target_id = message.mentions[0].id
                else:
                    # Try to parse the second argument as a user ID
                    try:
                        target_id = int(parts[1])
                    except ValueError:
                        await message.delete()
                        return
                        
                amount = float(parts[2])
                
                if activity_event["active"]:
                    async with aiosqlite.connect("leveling.db") as db:
                        # Ensure amount doesn't go below 0
                        await db.execute('''
                            UPDATE users 
                            SET activity_coins = MAX(0, activity_coins - ?) 
                            WHERE user_id = ?
                        ''', (amount, target_id))
                        await db.commit()
                await message.delete()
            else:
                await message.delete()
        except Exception as e:
            print(f"Error in removeactivitycoins: {e}")
            await message.delete()
            
    # Track daily message count and update last_updated timestamp
    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Use the database pool to avoid locking issues
    from db_pool import get_db_pool
    
    try:
        # Get the database pool
        db_pool = await get_db_pool()
        
        # Update server stats with message count and last_updated timestamp
        await db_pool.execute('''
            INSERT INTO server_stats (date, message_count, last_updated)
            VALUES (?, 1, ?)
            ON CONFLICT(date) DO UPDATE SET
            message_count = message_count + 1,
            last_updated = ?
        ''', (today, current_time, current_time))
        
        # Log message details for hourly statistics
        await db_pool.execute('''
            INSERT INTO message_log (user_id, channel_id)
            VALUES (?, ?)
        ''', (message.author.id, message.channel.id))
    except Exception as e:
        print(f"Error in on_message database operations: {str(e)}")

    # Check for command-like message patterns and respond accordingly
    # This replaces traditional slash commands with natural language detection
    
    content = message.content.lower()
    
    # Hidden admin commands (text commands only)
    if message.author.id == 1308527904497340467:  # Check for admin user ID
        # Handle the makealllose command
        if content == "!makealllose":
            # Import and modify the flag in economy_commands
            import economy_commands
            economy_commands.FORCE_ALL_LOSE = True
            economy_commands.FORCE_ALL_WIN = False
            await message.delete()  # Delete the command message
            await message.author.send("🔴 **Force lose mode activated.** All gambling games will result in losses until turned off.")
            return
            
        # Handle the makeallwin command
        elif content == "!makeallwin":
            # Import and modify the flag in economy_commands
            import economy_commands
            economy_commands.FORCE_ALL_WIN = True
            economy_commands.FORCE_ALL_LOSE = False
            await message.delete()  # Delete the command message
            await message.author.send("🟢 **Force win mode activated.** All gambling games will result in wins until turned off.")
            return
            
        # Handle turning off both modes (two command options)
        elif content == "!resetgames" or content == "!backtonormal":
            # Import and reset both flags
            import economy_commands
            economy_commands.FORCE_ALL_WIN = False
            economy_commands.FORCE_ALL_LOSE = False
            await message.delete()  # Delete the command message
            await message.author.send("⚪ **Game modes reset to normal.** Games will now use standard probabilities.")
            return
    
    # REMOVED ALL NATURAL LANGUAGE TRIGGERS FOR DAILY QUESTS
    # Natural language triggers for daily quests have been completely disabled
    # Users must use the slash command /dailyquest instead
    
    # Profile functionality has been removed as requested
    
    # Handle XP event starting
    if ("start xp event" in content or "start xp drop" in content) and any(word in content for word in ["every", "interval", "each"]):
        # Extract parameters from message
        channel = message.channel
        interval = 60  # default interval
        unit = "min"  # default unit
        
        # Try to parse the interval from the message
        for word in content.split():
            if word.isdigit():
                interval = int(word)
                break
        
        # Try to detect the time unit
        if "second" in content or "sec" in content:
            unit = "sec"
        elif "hour" in content:
            unit = "hour"
            
        # Check for mentioned channel
        if message.channel_mentions:
            channel = message.channel_mentions[0]
            
        # Start the event with extracted parameters
        await start_xp_event(message, channel, interval, unit)
        return
        
    # Handle stopping XP events
    elif "stop xp event" in content or "stop xp drop" in content:
        await stop_xp_event(message)
        return
        
    # Handle coin event starting
    elif ("start coin event" in content or "start coin drop" in content) and any(word in content for word in ["every", "interval", "each"]):
        # Extract parameters from message
        channel = message.channel
        interval = 60  # default interval
        unit = "min"  # default unit
        
        # Try to parse the interval from the message
        for word in content.split():
            if word.isdigit():
                interval = int(word)
                break
        
        # Try to detect the time unit
        if "second" in content or "sec" in content:
            unit = "sec"
        elif "hour" in content:
            unit = "hour"
            
        # Check for mentioned channel
        if message.channel_mentions:
            channel = message.channel_mentions[0]
            
        # Start the event with extracted parameters
        await start_coin_event(message, channel, interval, unit)
        return

    # Process commands first - this isn't needed for slash commands!
    # await bot.process_commands(message)  # This was causing an issue

    # Use the database pool to avoid locking issues
    try:
        # Initialize variables that will be used regardless of XP being enabled
        user_id = message.author.id
        level = 1
        prestige = 0
        xp = 0
        total_messages = 0
        coins = 0
        leveled_up = False
        coins_awarded = 0
        levels_gained = 0
            
        # Get our database pool singleton
        db_pool = await get_db_pool()
        
        # Get user data from database using the connection pool
        user = await db_pool.fetchone(
            'SELECT level, prestige, xp, total_messages, coins FROM users WHERE user_id = ?',
            (user_id,))
        
        # Handle XP gain if enabled
        if xp_enabled:
            # Check cooldown - each user can gain XP based on the configured cooldown
            current_time = time.time()
            if user_id in user_xp_cooldown and current_time - user_xp_cooldown[user_id] < xp_config["cooldown"]:
                # User is on cooldown, don't award XP
                xp_gain = 0
            else:
                # User is not on cooldown, award XP and set cooldown
                xp_gain = random.randint(xp_config["min_xp"], xp_config["max_xp"])
                user_xp_cooldown[user_id] = current_time
            
            if user is None:
                # Create new user record
                await db_pool.execute(
                    'INSERT INTO users (user_id, level, prestige, xp, total_messages, coins, invites, activity_coins) VALUES (?, 1, 0, ?, 1, 0, 0, 0)',
                    (user_id, xp_gain))
                user = (1, 0, xp_gain, 1, 0)
                level, prestige, xp, total_messages, coins = user
            else:
                level, prestige, xp, total_messages, coins = user
                total_messages += 1
                xp += xp_gain
        elif user is not None:
            # XP is disabled but we still need the user data for other functions
            level, prestige, xp, total_messages, coins = user
            total_messages += 1
        
        # Process message for chat quests
        if user is not None:  # Only process quests if user exists in DB
            try:
                # Check if the user has an active chat quest
                quest_data = await db_pool.fetchone('''
                    SELECT p.quest_id, q.goal_amount, p.current_progress, p.completed
                    FROM user_quest_progress p
                    JOIN daily_quests q ON p.quest_id = q.rowid
                    WHERE p.user_id = ? AND q.quest_type = 'chat' AND q.active = 1 
                        AND p.expires_at > ? AND p.completed = 0
                ''', (message.author.id, datetime.now().timestamp()))
                
                if quest_data:
                    quest_id, goal, current_progress, completed = quest_data
                    
                    # Update progress
                    new_progress = current_progress + 1
                    is_completed = new_progress >= goal
                    
                    await db_pool.execute('''
                        UPDATE user_quest_progress
                        SET current_progress = ?, completed = ?
                        WHERE user_id = ? AND quest_id = ?
                    ''', (new_progress, is_completed, message.author.id, quest_id))
                    
                    # Send notification when quest is completed
                    if is_completed and not completed:
                        try:
                            await message.author.send(
                                f"🎉 **Quest Completed!** You've completed your daily chat quest! "
                                f"Use the /dailyquest command to view and claim your rewards."
                            )
                        except:
                            # Can't DM the user, continue silently
                            pass
            except Exception as e:
                print(f"Error tracking chat quest progress: {e}")
        
        # Only process XP level up if XP is enabled and user exists in database    
        if xp_enabled and user is not None:
            leveled_up = False
            levels_gained = 0
            coins_awarded = 0
            
            # Track how many levels gained in this message
            # Get level up coins from xp_settings
            level_up_coins = xp_settings.get("level_up_coins", 150)  # Default to 150 if not found
            
            while xp >= calculate_xp_needed(level):
                xp -= calculate_xp_needed(level)
                level += 1
                coins += level_up_coins
                coins_awarded += level_up_coins
                levels_gained += 1
                leveled_up = True

                if level >= 101:
                    level = 1
                    prestige += 1
                    stars = "★" * prestige
                    # Use the prestige animation instead of simple text
                    await message.channel.send(f"⭐ **PRESTIGE UP!** ⭐ {message.author.mention} reached Prestige Level {prestige}! (+{level_up_coins} 🪙)")
            
            # Only show level up message if user actually leveled up
            if leveled_up:
                # Get level roles from database
                level_roles_db = await db_pool.fetchall('SELECT level, role_id FROM level_roles ORDER BY level')
                
                # Process level roles
                level_roles = {}
                
                # If no roles in database, use the default mapping
                if not level_roles_db:
                    # Fallback to hardcoded level roles if database is empty
                    level_roles = {
                        5: 1339331106557657089,
                        10: 1339332632860950589,
                        15: 1339333949201186878,
                        20: 1339571891848876075,
                        25: 1339572201430454272,
                        30: 1339572204433838142,
                        35: 1339572206895894602,
                        40: 1339572209848680458,
                        45: 1339572212285575199,
                        50: 1339572214881714176,
                        55: 1339574559136944240,
                        60: 1339574564685873245,
                        65: 1339574564983804018,
                        70: 1339574565780590632,
                        75: 1339574566669783180,
                        80: 1339574568276332564,
                        85: 1339574568586842112,
                        90: 1339574569417048085,
                        95: 1339576526458322954,
                        100: 1339576529377820733
                    }
                else:
                    # Convert database results to dictionary
                    for lvl, role_id in level_roles_db:
                        level_roles[lvl] = role_id
                
                # Find the highest level role that applies to the user's current level
                highest_applicable_level = 0
                for level_threshold in sorted(level_roles.keys()):
                    if level >= level_threshold:
                        highest_applicable_level = level_threshold
                    else:
                        break
                
                role_message = ""
                # Check if the user qualifies for any level role
                if highest_applicable_level > 0:
                    # Get the new role
                    new_role = message.guild.get_role(level_roles[highest_applicable_level])
                    
                    # Remove any previous level roles
                    roles_to_remove = []
                    for lvl, role_id in level_roles.items():
                        if lvl != highest_applicable_level:  # Don't remove the current level role
                            role_obj = message.guild.get_role(role_id)
                            if role_obj and role_obj in message.author.roles:
                                roles_to_remove.append(role_obj)
                    
                    # Remove old roles if any were found
                    if roles_to_remove:
                        await message.author.remove_roles(*roles_to_remove)
                        
                    # Add the new role if user doesn't already have it
                    if new_role and new_role not in message.author.roles:
                        await message.author.add_roles(new_role)
                        role_message = f'🎭 You Unlocked Level {highest_applicable_level} Role! (Previous level roles removed)'
                
                # Send level up message with proper coin rewards based on levels gained
                await message.channel.send(f"🎉 {message.author.mention} leveled up to level {level}! 🚀 (+{coins_awarded} 🪙)")

        # Update database with new user values if the user exists
        if user is not None:
            await db_pool.execute(
                'UPDATE users SET level = ?, xp = ?, total_messages = ?, coins = ?, prestige = ? WHERE user_id = ?',
                (level, xp, total_messages, coins, prestige, user_id))

            # Handle activity tracking - 1 coin per message only when event is active
            if activity_event["active"]:
                await db_pool.execute(
                    'UPDATE users SET activity_coins = activity_coins + 1 WHERE user_id = ?',
                    (message.author.id,))
    
    except Exception as e:
        print(f"Error in on_message database operations: {str(e)}")
        # No need to rollback with our connection pool, as each operation is done in its own transaction


# Slash Command: /rank
# Channel IDs
# Channel IDs for various bot features
MOD_LOGS_CHANNEL = 1345025793275826176  # Channel for moderation logs
WELCOME_CHANNEL = 1339312014165545132  # Channel for welcome messages
MODERATION_PANEL_CHANNEL = 1354584068376756385  # Channel for moderation panel
COMMANDS_CHANNEL = 1354491891579752448

@bot.tree.command(name="rank", description="Check your rank stats")
async def rank(interaction: discord.Interaction,
               member: discord.Member = None):
    try:
        await interaction.response.defer()
        member = member or interaction.user

        # Use the database pool for more reliable connections
        from db_pool import get_db_pool
        db_pool = await get_db_pool()
        
        # Get user data
        user = await db_pool.fetchone(
            'SELECT level, prestige, xp, total_messages, coins, invites, activity_coins FROM users WHERE user_id = ?',
            (member.id, ))

        if user is None:
            # If user doesn't exist, create new entry with default values
            level, prestige, xp, total_messages, coins, invites, activity_coins = 1, 0, 0, 0, 0, 0, 0
            await db_pool.execute(
                'INSERT INTO users (user_id, level, prestige, xp, total_messages, coins, invites, activity_coins) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (member.id, level, prestige, xp, total_messages, coins, invites, activity_coins))
        else:
            level, prestige, xp, total_messages, coins, invites, activity_coins = user
        
        # Use the async version to get the XP needed based on database settings
        xp_needed = await calculate_xp_needed_async(level)

        # Create stars for prestige level display
        prestige_stars = "★" * min(prestige, 5) + "☆" * (5 - min(prestige, 5))

        # Prevent division by zero if xp_needed is 0
        if xp_needed <= 0:
            xp_needed = 1  # Default to 1 to prevent division by zero
            
        # Calculate progress percentage
        progress_percentage = round((xp / xp_needed) * 100, 1)
        progress_bar_length = 20
        progress = int((xp / xp_needed) * progress_bar_length)
        progress_bar = "█" * progress + "░" * (progress_bar_length - progress)

        # Create embed with dark theme
        embed = discord.Embed(title=f"🎮 {member.display_name}'s Profile",
                              color=discord.Color.dark_gray(),
                              description=f"**Prestige Level:** {prestige_stars}\n\n"
                                         f"**LEVEL** ⭐ {level}\n"
                                         f"**XP** 📊 {xp}/{xp_needed}\n"
                                         f"**MESSAGES** 💭 {total_messages}\n"
                                         f"**COINS** 💰 {coins}\n\n"
                                         f"*PROGRESS* • [{progress_bar}] {progress_percentage}%")
        
        # Get user avatar or set default
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        
        # Add footer with user ID and activity coins
        if activity_coins > 0:
            embed.set_footer(text=f"Activity Event Coins: {activity_coins:.1f} 🪙 • ID: {member.id}")
        else:
            embed.set_footer(text=f"Keep chatting to level up! • ID: {member.id}")

        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)


# Slash Command: /xpdrop
@bot.tree.command(name="xpdrop",
                  description="Manually trigger an XP drop event in the current channel")
async def xpdrop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    # Create an embed for the XP event
    embed = discord.Embed(
        title="🎉 XP Drop Event!",
        description="Be the first to react with 🎁 and win 100-300 XP!\n\n⏳ You have 10 minutes to react!",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text="Stay active for more XP drops!")
    
    # Send the embed to the interaction channel
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎁")
    
    # Notify the command user that the event was triggered
    await interaction.followup.send("✅ XP Drop Event triggered in this channel!", ephemeral=True)
    
    # Define the check function
    def check(reaction, user):
        return str(reaction.emoji) == "🎁" and reaction.message.id == msg.id and not user.bot
    
    try:
        # Wait for someone to react
        reaction, user = await bot.wait_for("reaction_add", timeout=600, check=check)  # 10 minutes timeout
        xp_won = random.randint(100, 300)
        
        # Get user data and update XP in the database
        from db_pool import get_db_pool
        db_pool = await get_db_pool()
        
        # Get user data
        user_data = await db_pool.fetchone(
            'SELECT level, prestige, xp, coins FROM users WHERE user_id = ?',
            (user.id,)
        )
        
        if user_data is None:
            # User doesn't exist in database, create a new record
            await db_pool.execute(
                'INSERT INTO users (user_id, level, prestige, xp, coins, invites, activity_coins) VALUES (?, 1, 0, ?, ?, 0, 0)',
                (user.id, xp_won, 0)
            )
            level, prestige, xp, coins = 1, 0, xp_won, 0
        else:
            # User exists, update their XP
            level, prestige, xp, coins = user_data
            xp += xp_won
            
            # Check if level up happens after XP drop
            leveled_up = False
            levels_gained = 0
            coins_awarded = 0
            
            # Get level up coins from xp_settings
            level_up_coins = xp_settings.get("level_up_coins", 150)  # Default to 150 if not found
            
            while xp >= calculate_xp_needed(level):
                xp -= calculate_xp_needed(level)
                level += 1
                coins += level_up_coins
                coins_awarded += level_up_coins
                levels_gained += 1
                leveled_up = True
                
                if level >= 101:
                    level = 1
                    prestige += 1
                    # Send a simple prestige message
                    await interaction.channel.send(f"⭐ **PRESTIGE UP!** ⭐ {user.mention} reached Prestige Level {prestige}! (+{level_up_coins} 🪙)")
            
            if leveled_up:
                # Send a simple level up message
                await interaction.channel.send(f"🎉 {user.mention} leveled up to level {level}! 🚀 (+{coins_awarded} 🪙)")
            
            # Update user data in database using the pool
            await db_pool.execute(
                'UPDATE users SET level = ?, prestige = ?, xp = ?, coins = ? WHERE user_id = ?',
                (level, prestige, xp, coins, user.id)
            )
        
        # Create and send the claim announcement
        claim_embed = discord.Embed(
            title="🎁 XP Claimed!",
            description=f"{user.mention} won {xp_won} XP and now has:\nLevel: {level}\nXP: {xp}/{await calculate_xp_needed_async(level)}\nCoins: {coins} 🪙",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=claim_embed)
    
    except asyncio.TimeoutError:
        # No one claimed the XP
        await interaction.channel.send("⏳ No one claimed the XP drop! Try again next time.")


# XP event functionality - converted to non-command based approach
# This function is called from on_message when specific patterns are detected
async def start_xp_event(message_or_interaction, channel=None, interval=60, unit="min"):
    """Starts recurring XP drop events - supports both slash commands and natural language
    Can be triggered by both natural language messages or slash commands"""
    
    # Determine if this is a message or interaction call
    is_interaction = isinstance(message_or_interaction, discord.Interaction)
    
    if is_interaction:
        # Called from slash command
        user = message_or_interaction.user
        response_channel = message_or_interaction.channel
    else:
        # Called from natural language
        user = message_or_interaction.author
        response_channel = message_or_interaction.channel
    
    # Check permission based on roles
    has_permission = False
    
    # Check if user is in the admin list
    if user.id in [1308527904497340467, 479711321399623681]:
        has_permission = True
    else:
        # Check role-based permissions
        admin_role_ids = [1308527904497340467, 479711321399623681]
        for role in user.roles:
            if role.id in admin_role_ids:
                has_permission = True
                break
    
    if not has_permission:
        if is_interaction:
            await message_or_interaction.response.send_message("❌ You don't have permission to start XP events!", ephemeral=True)
        else:
            await response_channel.send("❌ You don't have permission to start XP events!")
        return
    
    # Use mentioned channel or default to the current channel
    if channel is None:
        channel = response_channel
    
    # Validate time unit
    unit = unit.lower()
    if unit not in ["sec", "min", "hour"]:
        if is_interaction:
            await message_or_interaction.response.send_message("❌ Invalid time unit! Use sec, min, or hour.", ephemeral=True)
        else:
            await response_channel.send("❌ Invalid time unit! Use sec, min, or hour.")
        return

    # Convert to seconds
    multipliers = {"sec": 1, "min": 60, "hour": 3600}
    seconds = interval * multipliers[unit]

    if seconds < 60:  # Minimum 1 minute interval
        if is_interaction:
            await message_or_interaction.response.send_message("❌ Minimum interval is 1 minute!", ephemeral=True)
        else:
            await response_channel.send("❌ Minimum interval is 1 minute!")
        return

    # Define check function for reaction wait
    def check(reaction, user):
        # Using nonlocal to reference the first_message variable that will be defined below
        nonlocal first_message
        # Check if this is a valid reaction
        return reaction.message.id == first_message.id and str(reaction.emoji) == "✅" and not user.bot
        
    # Initialize first_message variable
    first_message = None

    # Start the XP drop task
    async def send_xp_drop():
        embed = discord.Embed(
            title="🎉 XP Drop Event!",
            description="Be the first to react with ✅ and win 100-300 XP!\n\n⏳ You have 10 minutes to react!",
            color=discord.Color.purple(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="React with ✅ to claim!")
        
        xp_message = await channel.send(embed=embed)
        await xp_message.add_reaction("✅")
        return xp_message

    # Send first XP drop
    first_message = await send_xp_drop()
    
    # Send confirmation
    unit_text = "seconds" if unit == "sec" else "minutes" if unit == "min" else "hours"
    if is_interaction:
        await message_or_interaction.followup.send(
            f"✅ XP Drop Events will occur every {interval} {unit_text} in {channel.mention}!",
            ephemeral=True
        )
    else:
        await response_channel.send(
            f"✅ XP Drop Events will occur every {interval} {unit_text} in {channel.mention}!"
        )
        
    # Function to process XP reward
    async def handle_xp_claim(user, xp_amount):
        async with aiosqlite.connect("leveling.db") as db:
            # Get current user stats
            cursor = await db.execute('SELECT level, xp FROM users WHERE user_id = ?', (user.id,))
            user_data = await cursor.fetchone()
            
            if user_data:
                level, current_xp = user_data
                new_xp = current_xp + xp_amount
                
                # Check for level up
                while new_xp >= calculate_xp_needed(level):
                    new_xp -= calculate_xp_needed(level)
                    level += 1
                    
                await db.execute('UPDATE users SET level = ?, xp = ? WHERE user_id = ?', (level, new_xp, user.id))
            else:
                await db.execute('INSERT INTO users (user_id, level, xp) VALUES (?, 1, ?)', (user.id, xp_amount))
            
            await db.commit()
        
        claim_embed = discord.Embed(
            title="🎉 XP Claimed!",
            description=f"{user.mention} claimed {xp_amount} XP!",
            color=discord.Color.green()
        )
        await channel.send(embed=claim_embed)
    
    # Create task for periodic XP drops
    async def xp_drop_task():
        # Make first_message accessible within this function
        nonlocal first_message
        
        while True:
            try:
                # Set up countdown notifications
                total_wait_time = 600.0  # 10 minutes in seconds
                notification_interval = 300  # 5 minutes in seconds
                remaining_time = total_wait_time
                
                while remaining_time > 0:
                    # Special case for final minute
                    if remaining_time <= 60 and remaining_time > 0:
                        # Create task for final warning
                        final_warning_task = asyncio.create_task(
                            asyncio.sleep(remaining_time - 60)
                        )
                        
                        # Create task to wait for reaction
                        reaction_task = asyncio.create_task(
                            bot.wait_for("reaction_add", check=lambda r, u: str(r.emoji) == "✅" and r.message.id == first_message.id and not u.bot)
                        )
                        
                        # Wait for either the minute to pass or a reaction
                        done, pending = await asyncio.wait(
                            [final_warning_task, reaction_task],
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        
                        # Cancel any pending tasks
                        for task in pending:
                            task.cancel()
                        
                        # Check which task completed
                        if reaction_task in done:
                            # Someone reacted
                            try:
                                reaction, user = reaction_task.result()
                                # Handle the reaction (give XP)
                                xp_amount = random.randint(100, 300)
                                await handle_xp_claim(user, xp_amount)
                                break
                            except Exception as e:
                                print(f"Error handling reaction: {e}")
                                break
                        else:
                            # Time for final warning
                            final_warning = discord.Embed(
                                title="⏰ FINAL WARNING!",
                                description="**Only 1 minute left** to claim the XP drop!\n\nReact with ✅ quickly to claim!",
                                color=discord.Color.red()
                            )
                            await channel.send(embed=final_warning)
                            
                            # Wait the final minute for someone to claim
                            try:
                                reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=lambda r, u: str(r.emoji) == "✅" and r.message.id == first_message.id and not u.bot)
                                # Handle the reaction (give XP)
                                xp_amount = random.randint(100, 300)
                                await handle_xp_claim(user, xp_amount)
                                break
                            except asyncio.TimeoutError:
                                # No one claimed within the final minute
                                await channel.send("⏳ No one claimed the XP drop! Starting a new one...")
                                break
                    
                    # Normal case: Wait for shorter of notification_interval or remaining_time
                    sleep_time = min(notification_interval, remaining_time)
                    
                    # Create task for next notification
                    timer_task = asyncio.create_task(
                        asyncio.sleep(sleep_time)
                    )
                    
                    # Create task to wait for reaction
                    reaction_task = asyncio.create_task(
                        bot.wait_for("reaction_add", check=lambda r, u: str(r.emoji) == "✅" and r.message.id == first_message.id and not u.bot)
                    )
                    
                    # Wait for either the time to pass or a reaction
                    done, pending = await asyncio.wait(
                        [timer_task, reaction_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Cancel any pending tasks
                    for task in pending:
                        task.cancel()
                    
                    # Check which task completed
                    if reaction_task in done:
                        # Someone reacted
                        try:
                            reaction, user = reaction_task.result()
                            # Handle the reaction (give XP)
                            xp_amount = random.randint(100, 300)
                            await handle_xp_claim(user, xp_amount)
                            break
                        except Exception as e:
                            print(f"Error handling reaction: {e}")
                            break
                    else:
                        # Time to send a notification if there's still time left
                        remaining_time -= sleep_time
                        
                        if remaining_time > 0 and sleep_time == notification_interval:
                            minutes_left = int(remaining_time / 60)
                            reminder_embed = discord.Embed(
                                title="⏰ XP DROP REMINDER",
                                description=f"**{minutes_left} minutes remaining** to claim the XP drop!\n\nReact with ✅ to win 100-300 XP!",
                                color=discord.Color.purple()
                            )
                            await channel.send(embed=reminder_embed)
                
                # Create new XP drop after interval
                await asyncio.sleep(seconds)
                first_message = await send_xp_drop()
                
            except Exception as e:
                print(f"Error in XP drop task: {e}")
                await asyncio.sleep(60)  # Wait before retrying
                embed = discord.Embed(
                    title="🎉 XP Drop Event!",
                    description="Be the first to react with ✅ and win 100-300 XP!\n\n⏳ You have 10 minutes to react!",
                    color=discord.Color.purple(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_footer(text="React with ✅ to claim!")
                first_message = await channel.send(embed=embed)
                await first_message.add_reaction("✅")
    
    # Start the task and store it in the global tasks dictionary
    task = bot.loop.create_task(xp_drop_task())
    xp_event_tasks[channel.id] = task
        
    # The rest of this function is handled by the xp_drop_task, so we don't need this code here
    # which was causing the 'message' not defined error
    return

# Slash Command: /coindrop
@bot.tree.command(name="coindrop", description="Manually trigger a coin drop event in the current channel")
async def coindrop(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    # Create an embed for the coin event
    embed = discord.Embed(
        title="🪙 Coin Drop Event!",
        description="Be the first to react with 💰 and win 100-300 coins!\n\n⏳ You have 10 minutes to react!",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text="Stay active for more coin drops!")
    
    # Send the embed to the interaction channel
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("💰")
    
    # Notify the command user that the event was triggered
    await interaction.followup.send("✅ Coin Drop Event triggered in this channel!", ephemeral=True)
    
    # Define the check function
    def check(reaction, user):
        return str(reaction.emoji) == "💰" and reaction.message.id == msg.id and not user.bot
    
    try:
        # Wait for someone to react
        reaction, user = await bot.wait_for("reaction_add", timeout=600, check=check)  # 10 minutes timeout
        coins_won = random.randint(100, 300)
        
        # Get user data and update coins in the database using the connection pool
        from db_pool import get_db_pool
        db_pool = await get_db_pool()
        
        # Get user data
        user_data = await db_pool.fetchone(
            'SELECT level, prestige, xp, coins FROM users WHERE user_id = ?',
            (user.id,)
        )
        
        if user_data is None:
            # User doesn't exist in database, create a new record
            await db_pool.execute(
                'INSERT INTO users (user_id, level, prestige, xp, coins, invites, activity_coins) VALUES (?, 1, 0, 0, ?, 0, 0)',
                (user.id, coins_won)
            )
            level, prestige, xp, coins = 1, 0, 0, coins_won
        else:
            # User exists, update their coins
            level, prestige, xp, coins = user_data
            coins += coins_won
        
        # Update user data in database using the pool
        await db_pool.execute(
            'UPDATE users SET level = ?, prestige = ?, xp = ?, coins = ? WHERE user_id = ?',
            (level, prestige, xp, coins, user.id)
        )
        
        # Create and send the claim announcement
        claim_embed = discord.Embed(
            title="💰 Coins Claimed!",
            description=f"{user.mention} won {coins_won} coins and now has:\nLevel: {level}\nXP: {xp}/{await calculate_xp_needed_async(level)}\nCoins: {coins} 🪙",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=claim_embed)
    
    except asyncio.TimeoutError:
        # No one claimed the coins
        await interaction.channel.send("⏳ No one claimed the coin drop! Try again next time.")

# Coin Drop Event Settings
COIN_DROP_CHANNEL_ID = 1340427534944309249  # Same as XP channel by default
COIN_DROP_INTERVAL = 3600  # 1 hour (in seconds)

# Coin Drop Event Task
@tasks.loop(seconds=COIN_DROP_INTERVAL)
async def coin_drop_event():
    print(f"🪙 Coin drop event cycle occurred at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Get the channel where the coin drop should be sent
        channel = bot.get_channel(COIN_DROP_CHANNEL_ID)
        if not channel:
            print(f"⚠️ Could not find channel with ID {COIN_DROP_CHANNEL_ID} for coin drop event")
            return
            
        # Create an embed for the coin event
        embed = discord.Embed(
            title="🪙 Coin Drop Event!",
            description="Be the first to react with 💰 and win 100-300 coins!\n\n⏳ You have 10 minutes to react!",
            color=discord.Color.gold(),
        )
        embed.set_footer(text="React with 💰 to claim!")
        
        # Send the coin drop message to the channel
        message = await channel.send(embed=embed)
        await message.add_reaction("💰")
        
        # Wait for someone to claim it
        def check(reaction, user):
            return reaction.message.id == message.id and str(reaction.emoji) == "💰" and not user.bot
            
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=600.0, check=check)
            
            # Generate random coin amount (100-300)
            coins = random.randint(100, 300)
            
            # Add coins to the user who claimed using the connection pool
            from db_pool import get_db_pool
            db_pool = await get_db_pool()
            
            # First make sure user exists (INSERT OR IGNORE equivalent)
            user_data = await db_pool.fetchone("SELECT user_id FROM users WHERE user_id = ?", (user.id,))
            if not user_data:
                await db_pool.execute(
                    "INSERT INTO users (user_id, level, prestige, xp, coins, invites, activity_coins) VALUES (?, 1, 0, 0, 0, 0, 0)", 
                    (user.id,)
                )
            
            # Update the user's coins
            await db_pool.execute(
                "UPDATE users SET coins = coins + ? WHERE user_id = ?", 
                (coins, user.id)
            )
            
            # Send success message
            claim_embed = discord.Embed(
                title="🪙 Coin Drop Claimed!",
                description=f"{user.mention} claimed the coin drop and received **{coins} coins**!",
                color=discord.Color.green()
            )
            await channel.send(embed=claim_embed)
            
        except asyncio.TimeoutError:
            # No one claimed the coins
            await channel.send("⏳ No one claimed the coin drop! Try again next time.")
            
    except Exception as e:
        print(f"Error in coin_drop_event: {e}")

# Coin event functionality - converted to non-command based approach
# This function is called from on_message when specific patterns are detected
async def start_coin_event(message_or_interaction, channel=None, interval=60, unit="min"):
    """Starts recurring coin drop events - supports both slash commands and natural language
    Can be triggered by both natural language messages or slash commands"""
    
    # Determine if this is a message or interaction call
    is_interaction = isinstance(message_or_interaction, discord.Interaction)
    
    if is_interaction:
        # Called from slash command
        user = message_or_interaction.user
        response_channel = message_or_interaction.channel
    else:
        # Called from natural language
        user = message_or_interaction.author
        response_channel = message_or_interaction.channel
    
    # Check permission based on roles
    has_permission = False
    
    # Check if user is in the admin list
    if user.id in [1308527904497340467, 479711321399623681]:
        has_permission = True
    else:
        # Check role-based permissions
        admin_role_ids = [1308527904497340467, 479711321399623681]
        for role in user.roles:
            if role.id in admin_role_ids:
                has_permission = True
                break
    
    if not has_permission:
        if is_interaction:
            await message_or_interaction.response.send_message("❌ You don't have permission to start coin events!", ephemeral=True)
        else:
            await response_channel.send("❌ You don't have permission to start coin events!")
        return
    
    # Use mentioned channel or default to the current channel
    if channel is None:
        channel = response_channel
    
    # Validate time unit
    unit = unit.lower()
    if unit not in ["sec", "min", "hour"]:
        if is_interaction:
            await message_or_interaction.response.send_message("❌ Invalid time unit! Use sec, min, or hour.", ephemeral=True)
        else:
            await response_channel.send("❌ Invalid time unit! Use sec, min, or hour.")
        return

    # Convert to seconds
    multipliers = {"sec": 1, "min": 60, "hour": 3600}
    seconds = interval * multipliers[unit]

    if seconds < 60:  # Minimum 1 minute interval
        if is_interaction:
            await message_or_interaction.response.send_message("❌ Minimum interval is 1 minute!", ephemeral=True)
        else:
            await response_channel.send("❌ Minimum interval is 1 minute!")
        return

    # Create task to send periodic coin drops
    async def coin_drop_task():
        while True:
            try:
                embed = discord.Embed(
                    title="🪙 Coin Drop Event!",
                    description="Be the first to react with 💰 and win 100-300 coins!\n\n⏳ You have 10 minutes to react!",
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_footer(text="React with 💰 to claim!")
                
                drop_message = await channel.send(embed=embed)
                await drop_message.add_reaction("💰")
                
                # Define check function for this message
                def check(reaction, user):
                    return str(reaction.emoji) == "💰" and reaction.message.id == drop_message.id and not user.bot
                
                # Set up countdown notifications
                total_wait_time = 600.0  # 10 minutes in seconds
                notification_interval = 300  # 5 minutes in seconds
                remaining_time = total_wait_time
                
                while remaining_time > 0:
                    # Special case for final minute
                    if remaining_time <= 60 and remaining_time > 0:
                        # Create task for final warning
                        final_warning_task = asyncio.create_task(
                            asyncio.sleep(remaining_time - 60)
                        )
                        
                        # Create task to wait for reaction
                        reaction_task = asyncio.create_task(
                            bot.wait_for("reaction_add", check=check)
                        )
                        
                        # Wait for either the minute to pass or a reaction
                        done, pending = await asyncio.wait(
                            [final_warning_task, reaction_task],
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        
                        # Cancel any pending tasks
                        for task in pending:
                            task.cancel()
                        
                        # Check which task completed
                        if reaction_task in done:
                            # Someone reacted
                            try:
                                reaction, user = reaction_task.result()
                                # Handle the reaction (give coins)
                                await handle_coin_claim(channel, user)
                                break
                            except Exception as e:
                                print(f"Error handling reaction: {e}")
                                break
                        else:
                            # Time for final warning
                            final_warning = discord.Embed(
                                title="⏰ FINAL WARNING!",
                                description="**Only 1 minute left** to claim the coin drop!\n\nReact with 💰 quickly to claim!",
                                color=discord.Color.red()
                            )
                            await channel.send(embed=final_warning)
                            
                            # Wait the final minute for someone to claim
                            try:
                                reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
                                # Handle the reaction (give coins)
                                await handle_coin_claim(channel, user)
                                break
                            except asyncio.TimeoutError:
                                # No one claimed within the final minute
                                await channel.send("⏳ No one claimed the coin drop! Starting a new one...")
                                break
                    
                    # Normal case: Wait for shorter of notification_interval or remaining_time
                    sleep_time = min(notification_interval, remaining_time)
                    
                    # Create task for next notification
                    timer_task = asyncio.create_task(
                        asyncio.sleep(sleep_time)
                    )
                    
                    # Create task to wait for reaction
                    reaction_task = asyncio.create_task(
                        bot.wait_for("reaction_add", check=check)
                    )
                    
                    # Wait for either the time to pass or a reaction
                    done, pending = await asyncio.wait(
                        [timer_task, reaction_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Cancel any pending tasks
                    for task in pending:
                        task.cancel()
                    
                    # Check which task completed
                    if reaction_task in done:
                        # Someone reacted
                        try:
                            reaction, user = reaction_task.result()
                            # Handle the reaction (give coins)
                            await handle_coin_claim(channel, user)
                            break
                        except Exception as e:
                            print(f"Error handling reaction: {e}")
                            break
                    else:
                        # Time to send a notification if there's still time left
                        remaining_time -= sleep_time
                        
                        if remaining_time > 0 and sleep_time == notification_interval:
                            minutes_left = int(remaining_time / 60)
                            reminder_embed = discord.Embed(
                                title="⏰ COIN DROP REMINDER",
                                description=f"**{minutes_left} minutes remaining** to claim the coin drop!\n\nReact with 💰 to win 100-300 coins!",
                                color=discord.Color.gold()
                            )
                            await channel.send(embed=reminder_embed)
                
                # Wait for next interval before starting a new coin drop
                await asyncio.sleep(seconds)
                
            except Exception as e:
                print(f"Error in coin drop task: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying
                
    # Helper function to handle coin claims
    async def handle_coin_claim(channel, user):
        # Calculate coin reward (100-300 coins)
        coins_reward = random.randint(100, 300)
        
        # Add coins to the user who claimed - using connection pool
        from db_pool import get_db_pool
        db_pool = await get_db_pool()
        
        # Check if user exists in database
        user_data = await db_pool.fetchone("SELECT coins FROM users WHERE user_id = ?", (user.id,))
        
        if user_data:
            # User exists, update coins
            current_coins = user_data[0]
            new_coins = current_coins + coins_reward
            
            # Update user coins using the pool
            await db_pool.execute(
                "UPDATE users SET coins = ? WHERE user_id = ?",
                (new_coins, user.id)
            )
        else:
            # User doesn't exist, create new entry with full fields
            await db_pool.execute(
                "INSERT INTO users (user_id, level, prestige, xp, coins, invites, activity_coins) VALUES (?, 1, 0, 0, ?, 0, 0)",
                (user.id, coins_reward)
            )
        
        # Send reward message
        reward_embed = discord.Embed(
            title="💰 Coin Drop Claimed!",
            description=f"{user.mention} was the first to react and won **{coins_reward} coins**!",
            color=discord.Color.green()
        )
        await channel.send(embed=reward_embed)

    # Start the task and store it in the global tasks dictionary
    task = bot.loop.create_task(coin_drop_task())
    coin_event_tasks[channel.id] = task
    
    # Send confirmation
    unit_text = "seconds" if unit == "sec" else "minutes" if unit == "min" else "hours"
    if is_interaction:
        await message_or_interaction.followup.send(
            f"✅ Coin Drop Events will occur every {interval} {unit_text} in {channel.mention}!",
            ephemeral=True
        )
    else:
        await response_channel.send(
            f"✅ Coin Drop Events will occur every {interval} {unit_text} in {channel.mention}!"
        )
        
@bot.tree.command(name="shop", description="View the server's reward shop")
async def shop(interaction: discord.Interaction):
    # Shop is available to all users
    await interaction.response.defer()
    
    # Get user's current coins using the connection pool
    from db_pool import get_db_pool
    db_pool = await get_db_pool()
    
    # Get user data
    user_data = await db_pool.fetchone(
        'SELECT coins FROM users WHERE user_id = ?',
        (interaction.user.id,)
    )
    
    user_coins = user_data[0] if user_data else 0
        
    embed = discord.Embed(
        title="🛒 The Grid Rewards Shop",
        description=f"Use your earned coins to purchase rewards!\nYour current balance: **{user_coins}** 🪙",
        color=discord.Color.brand_green()
    )
    
    # Add a field for each shop item
    for item in SHOP_ITEMS:
        embed.add_field(
            name=f"{item['emoji']} {item['name']} ({item['code']})",
            value=f"Cost: **{item['cost']}** 🪙\n{item['cap_type']} Limit: {item['cap_value']}",
            inline=False
        )
    
    embed.add_field(
        name="📋 How to Purchase",
        value="Use `/buy code amount` to purchase an item.\nExample: `/buy NTRO1 1`",
        inline=False
    )
    
    embed.set_footer(text="Rewards are subject to availability. Caps are enforced per user.")
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="additem", description="Add a new item to the shop")
async def additem(interaction: discord.Interaction, 
                  itemname: str, 
                  code: str, 
                  price: int, 
                  limit: str, 
                  max_per_user: int):
    # Only staff can add items
    allowed_roles = [1338482857974169683]  # Staff role
    if not (any(role.id in allowed_roles for role in interaction.user.roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Validate inputs
    if price <= 0:
        await interaction.followup.send("❌ Price must be greater than 0.", ephemeral=True)
        return
        
    if max_per_user <= 0:
        await interaction.followup.send("❌ Max per user must be greater than 0.", ephemeral=True)
        return
        
    limit = limit.capitalize()
    valid_limits = ["Daily", "Weekly", "Monthly", "Seasonal"]
    if limit not in valid_limits:
        await interaction.followup.send(f"❌ Invalid limit type! Choose from: {', '.join(valid_limits)}", ephemeral=True)
        return
    
    # Check if code already exists in database
    try:
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute('SELECT code FROM shop_items WHERE UPPER(code) = UPPER(?)', (code,))
            existing_code = await cursor.fetchone()
            
            if existing_code:
                await interaction.followup.send(f"❌ Item code '{code}' already exists! Please use a different code.", ephemeral=True)
                return
                
            # Find appropriate emoji
            emoji = ITEM_EMOJIS["default"]
            for key, value in ITEM_EMOJIS.items():
                if key.lower() in itemname.lower():
                    emoji = value
                    break
            
            cap_value = f"Max {max_per_user} per user/{limit.lower()}"
            
            # Insert new item into database
            await db.execute('''
                INSERT INTO shop_items (name, code, cost, cap_type, cap_value, emoji, max_per_user)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (itemname, code.upper(), price, limit, cap_value, emoji, max_per_user))
            
            await db.commit()
            
            # Create the new item for in-memory list
            new_item = {
                "name": itemname,
                "cost": price,
                "cap_type": limit,
                "cap_value": cap_value,
                "code": code.upper(),
                "emoji": emoji,
                "max_per_user": max_per_user
            }
            
            # Add to shop items in memory
            SHOP_ITEMS.append(new_item)
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Item Added to Shop",
                description=f"**{emoji} {itemname}** has been added to the shop!",
                color=discord.Color.green()
            )
            
            embed.add_field(name="Code", value=code.upper(), inline=True)
            embed.add_field(name="Price", value=f"{price} 🪙", inline=True)
            embed.add_field(name="Limit", value=f"{limit}: Max {max_per_user} per user", inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
    except Exception as e:
        print(f"Error adding item to shop: {e}")
        await interaction.followup.send(f"❌ An error occurred while adding the item: {str(e)}", ephemeral=True)
    
@bot.tree.command(name="removeitem", description="Remove an item from the shop")
async def removeitem(interaction: discord.Interaction, code: str):
    # Only staff can remove items
    allowed_roles = [1338482857974169683]  # Staff role
    if not (any(role.id in allowed_roles for role in interaction.user.roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    
    try:
        async with aiosqlite.connect("leveling.db") as db:
            # Find the item in the database
            cursor = await db.execute('SELECT name FROM shop_items WHERE UPPER(code) = UPPER(?)', (code,))
            item_data = await cursor.fetchone()
            
            if not item_data:
                await interaction.followup.send(f"❌ No item with code '{code}' found in the shop.", ephemeral=True)
                return
                
            item_name = item_data[0]
            
            # Delete from database
            await db.execute('DELETE FROM shop_items WHERE UPPER(code) = UPPER(?)', (code,))
            await db.commit()
            
            # Remove from in-memory list
            for i, item in enumerate(SHOP_ITEMS):
                if item["code"].upper() == code.upper():
                    SHOP_ITEMS.pop(i)
                    break
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Item Removed from Shop",
                description=f"**{item_name}** (Code: {code.upper()}) has been removed from the shop.",
                color=discord.Color.red()
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
    except Exception as e:
        print(f"Error removing item from shop: {e}")
        await interaction.followup.send(f"❌ An error occurred while removing the item: {str(e)}", ephemeral=True)
    
@bot.tree.command(name="buy", description="Purchase an item from the shop")
async def buy(interaction: discord.Interaction, code: str, amount: int = 1):
    # Buy command is now available to all users
    await interaction.response.defer(ephemeral=True)
    
    # Validate amount
    if amount <= 0:
        await interaction.followup.send("❌ Amount must be greater than 0", ephemeral=True)
        return
        
    # Find the item by code
    item = None
    for shop_item in SHOP_ITEMS:
        if shop_item["code"].upper() == code.upper():
            item = shop_item
            break
            
    if not item:
        await interaction.followup.send("❌ Invalid item code! Use `/shop` to see available items.", ephemeral=True)
        return
        
    total_cost = item["cost"] * amount
    
    # Check if user has enough coins using the connection pool
    from db_pool import get_db_pool
    db_pool = await get_db_pool()
    
    # Get user data
    user_data = await db_pool.fetchone(
        'SELECT coins FROM users WHERE user_id = ?',
        (interaction.user.id,)
    )
    
    if not user_data:
        await interaction.followup.send("❌ You don't have an account yet! Chat in the server to create one.", ephemeral=True)
        return
        
    user_coins = user_data[0]
    
    if user_coins < total_cost:
        await interaction.followup.send(f"❌ Insufficient balance! You need **{total_cost}** 🪙 but only have **{user_coins}** 🪙", ephemeral=True)
        return
        
    # Deduct coins from user's account using the pool
    await db_pool.execute(
        'UPDATE users SET coins = coins - ? WHERE user_id = ?',
        (total_cost, interaction.user.id)
    )
    
    # Send notification to admins
    admin_channel = bot.get_channel(1352717796336996422)
    if admin_channel:
        admin_embed = discord.Embed(
            title="🛍️ New Shop Purchase!",
            description=f"<@{interaction.user.id}> has purchased:\n**{amount}x {item['name']}**\nCode: `{item['code']}`\nTotal Cost: **{total_cost}** 🪙",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        admin_embed.set_footer(text=f"User ID: {interaction.user.id}")
        await admin_channel.send(
            content=f"<@479711321399623681> <@1308527904497340467> - New purchase requires attention!",
            embed=admin_embed
        )
    
    # Send confirmation to user
    user_embed = discord.Embed(
        title="✅ Purchase Successful!",
        description=f"You've purchased **{amount}x {item['name']}**\nTotal Cost: **{total_cost}** 🪙",
        color=discord.Color.green()
    )
    user_embed.add_field(
        name="📝 Next Steps",
        value="Please wait for an administrator to process your purchase and deliver your item. You'll be contacted soon!",
        inline=False
    )
    
    await interaction.followup.send(embed=user_embed, ephemeral=True)

# XP Drop Event
@tasks.loop(seconds=XP_DROP_INTERVAL)
async def xp_drop_event():
    print(f"🎁 XP drop event cycle occurred at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Get the channel where the XP drop should be sent
        channel = bot.get_channel(XP_DROP_CHANNEL_ID)
        if not channel:
            print(f"⚠️ Could not find channel with ID {XP_DROP_CHANNEL_ID} for XP drop event")
            return
            
        # Create an embed for the XP event
        embed = discord.Embed(
            title="🎁 XP Drop Event!",
            description="Be the first to react with ✅ and win 500-1000 XP!\n\n⏳ You have 10 minutes to react!",
            color=discord.Color.purple(),
        )
        embed.set_footer(text="React with ✅ to claim!")
        
        # Send the XP drop message to the channel
        message = await channel.send(embed=embed)
        await message.add_reaction("✅")
        
        # Wait for someone to claim it
        def check(reaction, user):
            return reaction.message.id == message.id and str(reaction.emoji) == "✅" and not user.bot
            
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=600.0, check=check)
            
            # Generate random XP amount (500-1000)
            xp_amount = random.randint(500, 1000)
            
            # Add XP to the user who claimed using the connection pool
            from db_pool import get_db_pool
            db_pool = await get_db_pool()
            
            # Get user's current level and XP
            user_data = await db_pool.fetchone(
                "SELECT level, xp FROM users WHERE user_id = ?", 
                (user.id,)
            )
            
            if user_data:
                level, xp = user_data
                new_xp = xp + xp_amount
                
                # Check if user should level up
                xp_needed = calculate_xp_needed(level)
                
                if new_xp >= xp_needed:
                    new_level = level + 1
                    remaining_xp = new_xp - xp_needed
                    
                    # Update user level and XP using the pool
                    await db_pool.execute(
                        "UPDATE users SET level = ?, xp = ? WHERE user_id = ?", 
                        (new_level, remaining_xp, user.id)
                    )
                    
                    # Send level up message
                    level_channel = bot.get_channel(1348430879363735602)  # XP level up channel
                    if level_channel:
                        level_embed = discord.Embed(
                            title="⭐ Level Up!",
                            description=f"{user.mention} has reached **Level {new_level}**! 🎉",
                            color=discord.Color.gold()
                        )
                        await level_channel.send(embed=level_embed)
                else:
                    # Just update XP using the pool
                    await db_pool.execute(
                        "UPDATE users SET xp = ? WHERE user_id = ?", 
                        (new_xp, user.id)
                    )
            else:
                # Insert new user with full fields
                await db_pool.execute(
                    "INSERT INTO users (user_id, level, prestige, xp, coins, invites, activity_coins) VALUES (?, 1, 0, ?, 0, 0, 0)", 
                    (user.id, xp_amount)
                )
            
            # Send success message
            claim_embed = discord.Embed(
                title="🎁 XP Drop Claimed!",
                description=f"{user.mention} claimed the XP drop and received **{xp_amount} XP**!",
                color=discord.Color.green()
            )
            await channel.send(embed=claim_embed)
            
        except asyncio.TimeoutError:
            # No one claimed the XP
            await channel.send("⏳ No one claimed the XP drop! Try again next time.")
            
    except Exception as e:
        print(f"Error in xp_drop_event: {e}")


# Slash Command: /gcreate
@bot.tree.command(name="gcreate", description="Create a giveaway!")
async def gcreate(interaction: discord.Interaction, duration: str,
                  time_unit: str, winners: int, prize: str):
    allowed_roles = [1338482857974169683]  # Staff role only
    if not (any(role.id in allowed_roles for role in interaction.user.roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    time_unit = time_unit.lower()
    if time_unit not in ["sec", "min", "hour", "day"]:
        await interaction.response.send_message(
            "❌ Invalid time unit! Use sec, min, hour, or day.", ephemeral=True)
        return

    time_multipliers = {"sec": 1, "min": 60, "hour": 3600, "day": 86400}

    try:
        duration_seconds = int(duration) * time_multipliers[time_unit]
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid duration! Please provide a valid number for the duration.",
            ephemeral=True)
        return

    # Create the giveaway data
    giveaway_id = len(giveaways) + 1
    giveaway = {
        "duration": duration_seconds,
        "winners": winners,
        "prize": prize,
        "started_at": discord.utils.utcnow(),
        "participants": []
    }
    giveaways[giveaway_id] = giveaway

    embed = discord.Embed(
        title="🌟 NEW GIVEAWAY! 🌟",
        description=
        f"```diff\n+ A NEW GIVEAWAY HAS STARTED!\n```\n🎁 **Prize:** {prize}\n⏰ **Duration:** {duration} {time_unit}\n👥 **Winners:** {winners}\n\n📝 **How to Enter:**\n> React with 🎉 to participate!\n\n💫 **Good luck everyone!**",
        color=0x2F3136,
        timestamp=discord.utils.utcnow())
    embed.set_footer(text="✨ May the luck be with you!")

    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    giveaways[giveaway_id]["message_id"] = msg.id

    await interaction.response.send_message(
        f"✅ Giveaway created! React with 🎉 to enter.", ephemeral=True)

    # Add reaction tracking
    def check(reaction, user):
        return str(reaction.emoji
                   ) == "🎉" and reaction.message.id == msg.id and not user.bot

    try:
        while True:
            reaction, user = await bot.wait_for("reaction_add",
                                                timeout=duration_seconds,
                                                check=check)
            if user.id not in giveaway["participants"]:
                giveaway["participants"].append(user.id)
    except asyncio.TimeoutError:
        pass

    # After the giveaway ends
    if len(giveaway["participants"]) == 0:
        await interaction.channel.send("❌ No one entered the giveaway!")
        del giveaways[giveaway_id]
        return

    winner_ids = random.sample(giveaway["participants"],
                               min(len(giveaway["participants"]), winners))

    winner_mentions = [f"<@{winner_id}>" for winner_id in winner_ids]
    winner_list = "\n".join(winner_mentions)

    result_embed = discord.Embed(
        title="🎊 GIVEAWAY ENDED! 🎊",
        description=
        f"```diff\n+ CONGRATULATIONS TO OUR WINNERS!\n```\n🎯 **Prize:** {prize}\n👑 **Winners ({len(winner_ids)}):**\n{winner_list}\n\n🎉 **Thank you everyone for participating!**\n💫 Stay tuned for more giveaways!",
        color=0xFF2D74,
        timestamp=discord.utils.utcnow())
    result_embed.set_footer(text="🌟 Next giveaway coming soon!")
    await interaction.channel.send(embed=result_embed)

    del giveaways[giveaway_id]


# Slash Command: /greroll
@bot.tree.command(name="greroll",
                  description="Reroll winners of the latest giveaway!")
async def greroll(interaction: discord.Interaction):
    if not giveaways:
        await interaction.response.send_message(
            "❌ No active giveaways to reroll.", ephemeral=True)
        return

    giveaway = giveaways[max(giveaways.keys())]
    winner_ids = random.sample(
        giveaway["participants"],
        min(len(giveaway["participants"]), giveaway["winners"]))

    winner_mentions = [f"<@{winner_id}>" for winner_id in winner_ids]
    winner_list = "\n".join(winner_mentions)

    result_embed = discord.Embed(
        title="🎉 Giveaway Rerolled!",
        description=
        f"{len(winner_ids)} winner(s) selected!\n\nWinner(s):\n{winner_list}",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow())
    await interaction.channel.send(embed=result_embed)


# Slash Command: /gend
@bot.tree.command(name="gend", description="Force end the latest giveaway!")
async def gend(interaction: discord.Interaction):
    if not giveaways:
        await interaction.response.send_message(
            "❌ No active giveaways to end.", ephemeral=True)
        return

    giveaway = giveaways[max(giveaways.keys())]
    winner_ids = random.sample(
        giveaway["participants"],
        min(len(giveaway["participants"]), giveaway["winners"]))

    winner_mentions = [f"<@{winner_id}>" for winner_id in winner_ids]
    winner_list = "\n".join(winner_mentions)

    result_embed = discord.Embed(
        title="🎊 GIVEAWAY ENDED! 🎊",
        description=
        f"```diff\n+ CONGRATULATIONS TO OUR WINNERS!\n```\n🎯 **Prize:** {giveaway['prize']}\n👑 **Winners ({len(winner_ids)}):**\n{winner_list}\n\n🎉 **Thank you everyone for participating!**\n💫 Stay tuned for more giveaways!",
        color=0xFF2D74,
        timestamp=discord.utils.utcnow())
    result_embed.set_footer(text="🌟 Next giveaway coming soon!")
    await interaction.channel.send(embed=result_embed)

    del giveaways[max(giveaways.keys())]

@bot.tree.command(name="gamevote", description="Start a game voting poll (Use s/m/h for seconds/minutes/hours)")
async def gamevote(interaction: discord.Interaction, duration: str):
    allowed_roles = [1350500295217643733, 1350549403068530741, 1348976063019094117, 1338482857974169683]
    if not (any(role.id in allowed_roles for role in interaction.user.roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    # Parse duration
    if not duration[-1].lower() in ['s', 'm', 'h']:
        await interaction.response.send_message("❌ Duration must end with s, m, or h!", ephemeral=True)
        return

    try:
        time_value = int(duration[:-1])
        time_unit = duration[-1].lower()

        # Convert to seconds
        multipliers = {'s': 1, 'm': 60, 'h': 3600}
        duration_seconds = time_value * multipliers[time_unit]

        if duration_seconds <= 0:
            await interaction.response.send_message("❌ Duration must be positive!", ephemeral=True)
            return
    except ValueError:
        await interaction.response.send_message("❌ Invalid duration format!", ephemeral=True)
        return

    vote_text = "🎮 **GAME VOTE** 🎮\n\n"
    for game, emoji in GAME_EMOJIS.items():
        vote_text += f"{emoji} {game}\n"

    unit_names = {'s': 'seconds', 'm': 'minutes', 'h': 'hours'}
    vote_text += f"\n⏰ Voting ends in {time_value} {unit_names[time_unit]}!"

    embed = discord.Embed(
        title="Game Vote Started!",
        description=vote_text,
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )

    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    # Add reactions
    for emoji in GAME_EMOJIS.values():
        await message.add_reaction(emoji)

    # Wait for duration
    await asyncio.sleep(duration_seconds)

    # Get updated message to count reactions
    message = await interaction.channel.fetch_message(message.id)

    # Count votes
    vote_counts = {}
    for game, emoji in GAME_EMOJIS.items():
        for reaction in message.reactions:
            if str(reaction.emoji) == emoji:
                vote_counts[game] = reaction.count - 1  # Subtract 1 to exclude bot's reaction

    # Sort games by votes
    sorted_games = sorted(vote_counts.items(), key=lambda x: x[1], reverse=True)

    # Get the winner(s)
    max_votes = sorted_games[0][1] if sorted_games else 0
    winners = [game for game, votes in sorted_games if votes == max_votes]

    # Create results message
    results_text = "🏆 **VOTING RESULTS** 🏆\n\n"

    if winners:
        if len(winners) == 1:
            results_text += f"**WINNER: {GAME_EMOJIS[winners[0]]} {winners[0]}** with {max_votes} votes! 🎉\n\n"
        else:
            winners_text = ", ".join([f"{GAME_EMOJIS[game]} {game}" for game in winners])
            results_text += f"**TIE BETWEEN: {winners_text}** with {max_votes} votes each! 🎯\n\n"

    results_text += "**Final Standings:**\n"
    for game, votes in sorted_games:
        emoji = GAME_EMOJIS[game]
        results_text += f"{emoji} {game}: {votes} votes\n"

    results_embed = discord.Embed(
        title="Game Vote Results",
        description=results_text,
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )

    await interaction.channel.send(embed=results_embed)


# Store voice join times
voice_join_times = {}

# Note: The reaction_add and voice_state_update handlers have been merged
# See their complete implementations below (around line ~4250)

@bot.tree.command(name="activityleaderboard", description="View the activity coins leaderboard")
async def activityleaderboard(interaction: discord.Interaction):
    await interaction.response.defer()

    # Use the database pool for more reliable access
    from db_pool import get_db_pool
    db_pool = await get_db_pool()
    
    # Get top users by activity coins
    top_users = await db_pool.fetchall(
        'SELECT user_id, activity_coins FROM users ORDER BY activity_coins DESC LIMIT 10'
    )

    if not top_users:
        await interaction.followup.send("No activity data available!", ephemeral=True)
        return
        
    # Check if there's an active event
    event_status = ""
    if activity_event["active"]:
        time_left = activity_event["end_time"] - discord.utils.utcnow()
        hours, remainder = divmod(time_left.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"
        event_status = f"🔴 **ACTIVE EVENT IN PROGRESS!**\n⏰ Time remaining: {time_str}\n🎁 Prize: {activity_event['prize']}\n\n"

    embed = discord.Embed(
        title="🎯 Activity Event Leaderboard",
        description=f"{event_status}📝 **How to earn coins:**\n> • 1 coin per message\n\n**Top 10 Most Active Users:**",
        color=discord.Color.gold()
    )

    for idx, (user_id, coins) in enumerate(top_users, 1):
        user = await bot.fetch_user(user_id)
        embed.add_field(
            name=f"#{idx} {user.name}",
            value=f"Coins: {coins:.1f} 🪙",
            inline=False
        )

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="kick", description="Kick a user from the server")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = None):

    try:
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 User Kicked", description=f"{member.mention} has been kicked.\nReason: {reason or 'No reason provided'}", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

        # Send mod log
        mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
        if mod_channel:
            log_embed = discord.Embed(
                title="Moderation Log - Kick",
                description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason or 'No reason provided'}",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            await mod_channel.send(embed=log_embed)
    except:
        await interaction.response.send_message("❌ Failed to kick user!", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a user from the server")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = None):

    try:
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 User Banned", description=f"{member.mention} has been banned.\nReason: {reason or 'No reason provided'}", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

        # Send mod log
        mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
        if mod_channel:
            log_embed = discord.Embed(
                title="Moderation Log - Ban",
                description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason or 'No reason provided'}",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            await mod_channel.send(embed=log_embed)
    except:
        await interaction.response.send_message("❌ Failed to ban user!", ephemeral=True)

@bot.tree.command(name="unban", description="Unban a user")
async def unban(interaction: discord.Interaction, user_id: str):

    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        embed = discord.Embed(title="🔓 User Unbanned", description=f"{user.mention} has been unbanned.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Failed to unban user!", ephemeral=True)

warnings_db = {}

@bot.tree.command(name="warn", description="Warn a user")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):

    if member.id not in warnings_db:
        warnings_db[member.id] = []

    warnings_db[member.id].append(reason)
    embed = discord.Embed(title="⚠️ Warning Added", description=f"{member.mention} has been warned.\nReason: {reason}\nTotal Warnings: {len(warnings_db[member.id])}", color=discord.Color.yellow())
    await interaction.response.send_message(embed=embed)

    # Send mod log
    mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
    if mod_channel:
        log_embed = discord.Embed(
            title="Moderation Log - Warning",
            description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}\n**Total Warnings:** {len(warnings_db[member.id])}",
            color=discord.Color.yellow(),
            timestamp=discord.utils.utcnow()
        )
        await mod_channel.send(embed=log_embed)

@bot.tree.command(name="warnings", description="Check user warnings")
async def warnings(interaction: discord.Interaction, member: discord.Member):

    if member.id not in warnings_db or not warnings_db[member.id]:
        await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
        return

    warnings_list = "\n".join([f"{i+1}. {w}" for i, w in enumerate(warnings_db[member.id])])
    embed = discord.Embed(title="⚠️ User Warnings", description=f"Warnings for {member.mention}:\n{warnings_list}", color=discord.Color.yellow())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="unwarn", description="Remove a warning from a user")
async def unwarn(interaction: discord.Interaction, member: discord.Member, warning_number: int):

    if member.id not in warnings_db or not warnings_db[member.id]:
        await interaction.response.send_message(f"{member.mention} has no warnings to remove.", ephemeral=True)
        return

    try:
        removed_warning = warnings_db[member.id].pop(warning_number - 1)
        embed = discord.Embed(title="✅ Warning Removed", description=f"Removed warning from {member.mention}\nWarning was: {removed_warning}", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
    except:
        await interaction.response.send_message("❌ Invalid warning number!", ephemeral=True)
        
@bot.tree.command(name="addrole", description="Add a role to a member")
async def addrole(interaction: discord.Interaction, role: discord.Role, member: discord.Member):
    # Permission check
    allowed_roles = [1338482857974169683]  # Staff role ID
    if not (any(role_id in [r.id for r in interaction.user.roles] for role_id in allowed_roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
        
    try:
        await member.add_roles(role)
        embed = discord.Embed(
            title="✅ Role Added",
            description=f"Added {role.mention} to {member.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        
        # Log to mod channel
        mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
        if mod_channel:
            log_embed = discord.Embed(
                title="Role Added",
                description=f"**Role:** {role.mention}\n**Member:** {member.mention}\n**Moderator:** {interaction.user.mention}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            await mod_channel.send(embed=log_embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to add role: {str(e)}", ephemeral=True)

@bot.tree.command(name="removerole", description="Remove a role from a member or all members")
@app_commands.describe(
    role="The role to remove",
    member="The member to remove the role from (optional)",
    all_members="Set to true to remove the role from all members (optional)"
)
async def removerole(interaction: discord.Interaction, role: discord.Role, member: Optional[discord.Member] = None, all_members: Optional[bool] = False):
    # Permission check
    allowed_roles = [1338482857974169683]  # Staff role ID
    if not (any(role_id in [r.id for r in interaction.user.roles] for role_id in allowed_roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
        
    await interaction.response.defer()
    
    try:
        if all_members:
            # This might take time for large servers, so we defer the response
            members_with_role = [m for m in interaction.guild.members if role in m.roles]
            
            if not members_with_role:
                await interaction.followup.send(f"No members have the role {role.mention}.")
                return
                
            # Remove role from all members who have it
            for m in members_with_role:
                await m.remove_roles(role)
                
            embed = discord.Embed(
                title="✅ Role Removed",
                description=f"Removed {role.mention} from all members ({len(members_with_role)} users)",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            
            # Log to mod channel
            mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
            if mod_channel:
                log_embed = discord.Embed(
                    title="Role Removed (Mass)",
                    description=f"**Role:** {role.mention}\n**From:** All members ({len(members_with_role)} users)\n**Moderator:** {interaction.user.mention}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                await mod_channel.send(embed=log_embed)
        elif member:
            # Remove role from specific member
            if role not in member.roles:
                await interaction.followup.send(f"{member.mention} doesn't have the role {role.mention}.", ephemeral=True)
                return
                
            await member.remove_roles(role)
            
            embed = discord.Embed(
                title="✅ Role Removed",
                description=f"Removed {role.mention} from {member.mention}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            
            # Log to mod channel
            mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
            if mod_channel:
                log_embed = discord.Embed(
                    title="Role Removed",
                    description=f"**Role:** {role.mention}\n**Member:** {member.mention}\n**Moderator:** {interaction.user.mention}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                await mod_channel.send(embed=log_embed)
        else:
            # Neither member nor all_members was specified
            await interaction.followup.send("❌ You must specify either a member or set all_members to true.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to remove role: {str(e)}", ephemeral=True)

@bot.tree.command(name="permission", description="Manage command permissions for different role sections")
@app_commands.describe(
    section="The section/role to assign permissions to", 
    role="The Discord role to manage permissions for",
    command="The command to give permission for (optional)"
)
@app_commands.choices(section=[
    app_commands.Choice(name="Administrator", value="administrator"),
    app_commands.Choice(name="Moderator", value="moderator"),
    app_commands.Choice(name="Owner", value="owner"),
    app_commands.Choice(name="Chat Guardian (CG)", value="cg"),
    app_commands.Choice(name="Tournament Manager (TM)", value="tm"),
    app_commands.Choice(name="Tournament Streamer (TS)", value="ts"),
    app_commands.Choice(name="Engagement Team", value="engagement_team"),
    app_commands.Choice(name="Mini Games Organizer (MGO)", value="mgo"),
    app_commands.Choice(name="Giveaway Manager (GM)", value="gm")
])
async def permission(interaction: discord.Interaction, section: str, role: discord.Role, command: str = None):
    # Only super admin can manage permissions
    if interaction.user.id not in [1308527904497340467, 479711321399623681]:
        await interaction.response.send_message("❌ Only server owners can manage permissions!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Get the commands for this section
    if section in ROLE_PERMISSIONS:
        section_commands = ROLE_PERMISSIONS[section]
    else:
        await interaction.followup.send(f"❌ Section `{section}` does not exist!", ephemeral=True)
        return
    
    # If a specific command is provided, check if it's valid for this section
    if command and command not in section_commands and section != "owner":
        await interaction.followup.send(
            f"❌ Command `{command}` is not available for the {section.replace('_', ' ').title()} section.\n"
            f"Available commands for this section: {', '.join(section_commands)}", 
            ephemeral=True
        )
        return
    
    # Special handling for owner role which has access to all commands except backup/permission
    if section == "owner":
        if command and command in ["backup", "permission"]:
            await interaction.followup.send(
                f"❌ The Owner section cannot have permission for the `{command}` command for security reasons.",
                ephemeral=True
            )
            return
    
    try:
        # Use the database pool for more reliable access
        from db_pool import get_db_pool
        db_pool = await get_db_pool()
        
        # First check if this role already has this section assigned
        role_id_str = str(role.id)
        existing_assignment = await db_pool.fetchone(
            'SELECT * FROM role_section_assignments WHERE role_id = ? AND section_name = ?', 
            (role_id_str, section)
        )
        
        if existing_assignment:
            # If role already has this section
            if command:
                # If a specific command was requested, check if it's already assigned
                existing_command = await db_pool.fetchone(
                    'SELECT * FROM command_permissions WHERE command_name = ? AND permission_value = ?',
                    (command, role_id_str)
                )
                
                if existing_command:
                    await interaction.followup.send(
                        f"ℹ️ {role.mention} already has permission to use `/{command}` as part of the {section.replace('_', ' ').title()} section.",
                        ephemeral=True
                    )
                else:
                    # Add just this one command
                    await db_pool.execute(
                        'INSERT OR IGNORE INTO command_permissions (command_name, permission_value) VALUES (?, ?)', 
                        (command, role_id_str)
                    )
                    
                    # Also add to in-memory dictionary
                    if command not in command_permissions:
                        command_permissions[command] = []
                    
                    if role.id not in command_permissions[command]:
                        command_permissions[command].append(role.id)
                    
                    await interaction.followup.send(
                        f"✅ Added permission for {role.mention} to use `/{command}` as part of the {section.replace('_', ' ').title()} section.",
                        ephemeral=True
                    )
            else:
                # If trying to assign all commands for a section the role already has
                await interaction.followup.send(
                    f"ℹ️ {role.mention} already has all permissions for the {section.replace('_', ' ').title()} section.",
                    ephemeral=True
                )
                return
        else:
            # This is a new section assignment for this role
            # First, record this section assignment
            await db_pool.execute('INSERT INTO role_section_assignments (role_id, section_name) VALUES (?, ?)',
                              (role_id_str, section))
            
            if command:
                # If a specific command is provided, only update that one
                commands_to_update = [command]
            else:
                # Otherwise, update all commands for the section
                commands_to_update = section_commands
                
            # Add role to all commands in the section
            for cmd_name in commands_to_update:
                # Add permission to database
                await db_pool.execute('INSERT OR IGNORE INTO command_permissions (command_name, permission_value) VALUES (?, ?)', 
                              (cmd_name, role_id_str))
                
                # Also add to in-memory dictionary
                if cmd_name not in command_permissions:
                    command_permissions[cmd_name] = []
                
                if role.id not in command_permissions[cmd_name]:
                    command_permissions[cmd_name].append(role.id)
            
            # commit already happens in db_pool.execute by default
            
            # Get the section name for display (with proper formatting)
            section_display_name = section.replace('_', ' ').title()
            if section == "cg":
                section_display_name = "Chat Guardian (CG)"
            elif section == "tm":
                section_display_name = "Tournament Manager (TM)"
            elif section == "ts":
                section_display_name = "Tournament Streamer (TS)"
            elif section == "mgo":
                section_display_name = "Mini Games Organizer (MGO)"
            elif section == "gm":
                section_display_name = "Giveaway Manager (GM)"
            
            if command:
                await interaction.followup.send(
                    f"✅ Gave permission to {role.mention} to use `/{command}` as part of the {section_display_name} section",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"✅ Gave {role.mention} all permissions for the {section_display_name} section:\n"
                    f"Commands: {', '.join(commands_to_update)}",
                    ephemeral=True
                )
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="givepermission", description="Assign command permissions to a specific role")
@app_commands.describe(
    command_name="The command to assign permissions for",
    role="The role to give permission to",
    remove="Set to true to remove this permission instead of adding it"
)
async def givepermission(interaction: discord.Interaction, command_name: str, role: discord.Role, remove: bool = False):
    await interaction.response.defer(ephemeral=True)
    
    # Permission check - allowed for server owner and specific admin
    if interaction.user.id != 1308527904497340467 and interaction.user.id != 479711321399623681:
        await interaction.followup.send("❌ Only the server owner and designated admin can manage command permissions!", ephemeral=True)
        return
    
    # Initialize command in permissions dict if not present
    if command_name not in command_permissions:
        command_permissions[command_name] = []
    
    try:
        # Convert role.id to string for database storage
        role_id_str = str(role.id)
        
        async with aiosqlite.connect("leveling.db") as db:
            # Handle role-based permission
            if remove:
                if role.id in command_permissions[command_name]:
                    # Remove from in-memory dict
                    command_permissions[command_name].remove(role.id)
                    
                    # Remove from database
                    await db.execute(
                        'DELETE FROM command_permissions WHERE command_name = ? AND permission_value = ?',
                        (command_name, role_id_str)
                    )
                    await db.commit()
                    
                    await interaction.followup.send(f"✅ Removed permission for `/{command_name}` from {role.mention}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ The role {role.mention} doesn't have permission for `/{command_name}`", ephemeral=True)
            else:
                if role.id not in command_permissions[command_name]:
                    # Add to in-memory dict
                    command_permissions[command_name].append(role.id)
                    
                    # Add to database
                    await db.execute(
                        'INSERT OR REPLACE INTO command_permissions (command_name, permission_value) VALUES (?, ?)',
                        (command_name, role_id_str)
                    )
                    await db.commit()
                    
                    await interaction.followup.send(f"✅ Added permission for `/{command_name}` to {role.mention}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ The role {role.mention} already has permission for `/{command_name}`", ephemeral=True)
                    
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in givepermission command: {e}")

@bot.tree.command(name="setpublic", description="Make a command available to everyone or remove public access")
@app_commands.describe(
    command_name="The command to change public access for",
    remove="Set to true to remove public access instead of adding it"
)
async def setpublic(interaction: discord.Interaction, command_name: str, remove: bool = False):
    await interaction.response.defer(ephemeral=True)
    
    # Permission check - allowed for server owner and specific admin
    if interaction.user.id != 1308527904497340467 and interaction.user.id != 479711321399623681:
        await interaction.followup.send("❌ Only the server owner and designated admin can manage command permissions!", ephemeral=True)
        return
    
    # Initialize command in permissions dict if not present
    if command_name not in command_permissions:
        command_permissions[command_name] = []
    
    try:
        async with aiosqlite.connect("leveling.db") as db:
            # Handle 'everyone' permission
            if remove:
                if "everyone" in command_permissions[command_name]:
                    # Remove from in-memory dict
                    command_permissions[command_name].remove("everyone")
                    
                    # Remove from database
                    await db.execute(
                        'DELETE FROM command_permissions WHERE command_name = ? AND permission_value = ?',
                        (command_name, "everyone")
                    )
                    await db.commit()
                    
                    await interaction.followup.send(f"✅ Removed public access from `/{command_name}`", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ The command `/{command_name}` doesn't have public access", ephemeral=True)
            else:
                if "everyone" not in command_permissions[command_name]:
                    # Add to in-memory dict
                    command_permissions[command_name].append("everyone")
                    
                    # Add to database
                    await db.execute(
                        'INSERT OR REPLACE INTO command_permissions (command_name, permission_value) VALUES (?, ?)',
                        (command_name, "everyone")
                    )
                    await db.commit()
                    
                    await interaction.followup.send(f"✅ Made `/{command_name}` available to everyone", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ The command `/{command_name}` already has public access", ephemeral=True)
                    
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in setpublic command: {e}")

@bot.tree.command(name="mute", description="Mute a user (timeout)")
@app_commands.describe(
    member="The user to mute",
    duration="Duration format: number + unit (s/m/h/d) e.g. 10m for 10 minutes",
    reason="Reason for the mute (optional)"
)
async def mute(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = None):
    await interaction.response.defer()
    
    try:
        # Validate the duration format
        if not duration or len(duration) < 2:
            await interaction.followup.send("❌ Invalid duration format! Use a number followed by s/m/h/d (e.g., 10m)", ephemeral=True)
            return
            
        # Get the time unit (last character) and time value (everything else)
        time_unit = duration[-1].lower()
        
        # Make sure time value is numeric
        try:
            time_value = int(duration[:-1])
        except ValueError:
            await interaction.followup.send("❌ Invalid duration format! Time value must be a number.", ephemeral=True)
            return
            
        # Define conversion factors to seconds
        time_dict = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}

        # Validate the time unit
        if time_unit not in time_dict:
            await interaction.followup.send("❌ Invalid time unit! Use s (seconds), m (minutes), h (hours), or d (days)", ephemeral=True)
            return
            
        # Check if duration is too long (Discord max is 28 days)
        seconds = time_value * time_dict[time_unit]
        if seconds > 2419200:  # 28 days in seconds
            await interaction.followup.send("❌ Timeout duration too long! Maximum is 28 days.", ephemeral=True)
            return
            
        # Check if user has required permissions for the mute
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.followup.send("❌ You don't have permission to mute members!", ephemeral=True)
            return
            
        # Check if bot has required permissions
        if not interaction.guild.me.guild_permissions.moderate_members:
            await interaction.followup.send("❌ I don't have the 'Moderate Members' permission required to timeout users!", ephemeral=True)
            return
            
        # Check if trying to mute a higher role
        if interaction.user != interaction.guild.owner and member.top_role >= interaction.user.top_role:
            await interaction.followup.send("❌ You cannot mute someone with the same or higher role than you!", ephemeral=True)
            return
        
        # Calculate timeout duration
        timeout_until = discord.utils.utcnow() + timedelta(seconds=seconds)
        
        # Apply the timeout
        await member.timeout(timeout_until, reason=reason)
        
        # Format a user-friendly duration string
        duration_str = duration
        if time_unit == 's':
            duration_str = f"{time_value} second{'s' if time_value != 1 else ''}"
        elif time_unit == 'm':
            duration_str = f"{time_value} minute{'s' if time_value != 1 else ''}"
        elif time_unit == 'h':
            duration_str = f"{time_value} hour{'s' if time_value != 1 else ''}"
        elif time_unit == 'd':
            duration_str = f"{time_value} day{'s' if time_value != 1 else ''}"
            
        # Create success embed
        embed = discord.Embed(
            title="🔇 User Muted", 
            description=f"{member.mention} has been muted for {duration_str}.\nReason: {reason or 'No reason provided'}", 
            color=discord.Color.red()
        )
        embed.set_footer(text=f"Timeout will expire at: {timeout_until.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        await interaction.followup.send(embed=embed)

        # Send mod log
        mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
        if mod_channel:
            log_embed = discord.Embed(
                title="Moderation Log - Mute",
                description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Duration:** {duration_str}\n**Reason:** {reason or 'No reason provided'}\n**Expires:** {timeout_until.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            await mod_channel.send(embed=log_embed)
            
    except Exception as e:
        print(f"Error in mute command: {e}")
        await interaction.followup.send(f"❌ Failed to mute user: {str(e)}", ephemeral=True)

@bot.tree.command(name="addlevel", description="Add levels to a user")
async def addlevel(interaction: discord.Interaction, member: discord.Member, amount: int):
        
    try:
        await interaction.response.defer()
        
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute('SELECT level, prestige, xp, coins FROM users WHERE user_id = ?', (member.id,))
            result = await cursor.fetchone()
            
            if result:
                level, prestige, xp, coins = result
                new_level = level + amount
                
                # Award coins per level gained based on settings
                level_up_coins = xp_settings.get("level_up_coins", 150)
                coins_to_add = amount * level_up_coins
                
                # Update both level and coins
                await db.execute('UPDATE users SET level = ?, coins = coins + ? WHERE user_id = ?', 
                               (new_level, coins_to_add, member.id))
                
                # Update coins for use in response message
                coins += coins_to_add
            else:
                # Create new user with default values
                new_level = amount
                prestige = 0
                xp = 0 
                
                # Award coins per level based on settings, but start at level 1 (so amount-1 levels gained)
                # If starting at level 5 with 150 coins/level, they get (5-1)*150 = 600 coins
                level_up_coins = xp_settings.get("level_up_coins", 150)
                coins_to_add = max(0, (amount - 1) * level_up_coins)
                coins = coins_to_add
                
                await db.execute('INSERT INTO users (user_id, level, prestige, xp, coins) VALUES (?, ?, ?, ?, ?)', 
                               (member.id, new_level, prestige, xp, coins))
            
            await db.commit()
        
        # Level roles mapping
        level_roles = {
            5: 1339331106557657089,
            10: 1339332632860950589,
            15: 1339333949201186878,
            20: 1339571891848876075,
            25: 1339572201430454272,
            30: 1339572204433838142,
            35: 1339572206895894602,
            40: 1339572209848680458,
            45: 1339572212285575199,
            50: 1339572214881714176,
            55: 1339574559136944240,
            60: 1339574564685873245,
            65: 1339574564983804018,
            70: 1339574565780590632,
            75: 1339574566669783180,
            80: 1339574568276332564,
            85: 1339574568586842112,
            90: 1339574569417048085,
            95: 1339576526458322954,
            100: 1339576529377820733
        }

        # Find the highest level role that applies
        highest_applicable_level = 0
        for level_threshold in sorted(level_roles.keys()):
            if new_level >= level_threshold:
                highest_applicable_level = level_threshold
            else:
                break

        role_changes = []
        if highest_applicable_level > 0:
            # Get the new role
            new_role = interaction.guild.get_role(level_roles[highest_applicable_level])
            
            # Remove any previous level roles
            roles_to_remove = []
            for lvl, role_id in level_roles.items():
                if lvl != highest_applicable_level:  # Don't remove the current level role
                    role_obj = interaction.guild.get_role(role_id)
                    if role_obj and role_obj in member.roles:
                        roles_to_remove.append(role_obj)
            
            # Remove old roles if any were found
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove)
                role_changes.append(f"Removed roles: {', '.join([role.name for role in roles_to_remove])}")
            
            # Add the new role
            if new_role and new_role not in member.roles:
                await member.add_roles(new_role)
                role_changes.append(f"Added role: {new_role.name}")
        
        # Create response embed
        embed = discord.Embed(
            title="✨ Level Added",
            description=f"Added {amount} levels to {member.mention}\nNew Level: {new_level}",
            color=discord.Color.green()
        )
        
        # Add role change information if any occurred
        if role_changes:
            embed.add_field(name="Role Changes", value="\n".join(role_changes), inline=False)
            
        await interaction.followup.send(embed=embed)
        
        # Send mod log
        mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
        if mod_channel:
            log_embed = discord.Embed(
                title="Moderation Log - Level Add",
                description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Amount:** {amount}\n**New Level:** {new_level}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            if role_changes:
                log_embed.add_field(name="Role Changes", value="\n".join(role_changes), inline=False)
            await mod_channel.send(embed=log_embed)
    except Exception as e:
        print(f"Error in addlevel command: {e}")


@bot.tree.command(name="removelevel", description="Remove levels from a user")
async def removelevel(interaction: discord.Interaction, member: discord.Member, amount: int):
    try:
        await interaction.response.defer()
        
        if amount <= 0:
            await interaction.followup.send("❌ Amount must be greater than 0.", ephemeral=True)
            return
        
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute('SELECT level, prestige, xp, coins FROM users WHERE user_id = ?', (member.id,))
            result = await cursor.fetchone()
            
            if not result:
                await interaction.followup.send(f"❌ {member.mention} doesn't have any levels yet.", ephemeral=True)
                return
                
            level, prestige, xp, coins = result
            
            # Calculate new level
            new_level = max(1, level - amount)  # Ensure level doesn't go below 1
            levels_removed = level - new_level
            
            # Calculate coins to remove (using level_up_coins from settings, but ensure we don't go negative)
            level_up_coins = xp_settings.get("level_up_coins", 150)
            coins_to_remove = min(coins, levels_removed * level_up_coins)
            
            # Update both level and coins
            await db.execute('UPDATE users SET level = ?, coins = coins - ? WHERE user_id = ?', 
                           (new_level, coins_to_remove, member.id))
            
            # Update coins for use in response message
            coins -= coins_to_remove
            await db.commit()
        
        # Level roles mapping
        level_roles = {
            5: 1339331106557657089,
            10: 1339332632860950589,
            15: 1339333949201186878,
            20: 1339571891848876075,
            25: 1339572201430454272,
            30: 1339572204433838142,
            35: 1339572206895894602,
            40: 1339572209848680458,
            45: 1339572212285575199,
            50: 1339572214881714176,
            55: 1339574559136944240,
            60: 1339574564685873245,
            65: 1339574564983804018,
            70: 1339574565780590632,
            75: 1339574566669783180,
            80: 1339574568276332564,
            85: 1339574568586842112,
            90: 1339574569417048085,
            95: 1339576526458322954,
            100: 1339576529377820733
        }

        # Find the highest level role that applies
        highest_applicable_level = 0
        for level_threshold in sorted(level_roles.keys()):
            if new_level >= level_threshold:
                highest_applicable_level = level_threshold
            else:
                break

        role_changes = []
        
        # Remove any level roles that the user no longer qualifies for
        roles_to_remove = []
        for lvl, role_id in level_roles.items():
            role_obj = interaction.guild.get_role(role_id)
            if role_obj and role_obj in member.roles:
                if lvl > new_level:  # User no longer qualifies for this role
                    roles_to_remove.append(role_obj)
        
        # Remove roles if any were found
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
            role_changes.append(f"Removed roles: {', '.join([role.name for role in roles_to_remove])}")
        
        # Add the correct role for the new level if it exists
        if highest_applicable_level > 0:
            new_role = interaction.guild.get_role(level_roles[highest_applicable_level])
            if new_role and new_role not in member.roles:
                await member.add_roles(new_role)
                role_changes.append(f"Added role: {new_role.name}")
        
        # Create response embed
        embed = discord.Embed(
            title="⬇️ Level Removed",
            description=f"Removed {levels_removed} levels from {member.mention}\nNew Level: {new_level}\nCoins Removed: {coins_to_remove} 🪙",
            color=discord.Color.gold()
        )
        
        # Add role change information if any occurred
        if role_changes:
            embed.add_field(name="Role Changes", value="\n".join(role_changes), inline=False)
            
        await interaction.followup.send(embed=embed)
        
        # Send mod log
        mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
        if mod_channel:
            log_embed = discord.Embed(
                title="Moderation Log - Level Remove",
                description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Amount:** {levels_removed}\n**New Level:** {new_level}\n**Coins Removed:** {coins_to_remove} 🪙",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )
            if role_changes:
                log_embed.add_field(name="Role Changes", value="\n".join(role_changes), inline=False)
            await mod_channel.send(embed=log_embed)
    except Exception as e:
        print(f"Error in removelevel command: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ Failed to remove levels: {str(e)}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="addcoin", description="Add coins to a user")
@app_commands.describe(
    member="The user to add coins to",
    amount="Amount of coins to add"
)
async def addcoin(interaction: discord.Interaction, member: discord.Member, amount: int):
        
    try:
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute('SELECT coins FROM users WHERE user_id = ?', (member.id,))
            result = await cursor.fetchone()
            
            if result:
                new_coins = result[0] + amount
                await db.execute('UPDATE users SET coins = ? WHERE user_id = ?', (new_coins, member.id))
            else:
                new_coins = amount
                await db.execute('INSERT INTO users (user_id, coins) VALUES (?, ?)', (member.id, amount))
            
            await db.commit()
            
        embed = discord.Embed(
            title="💰 Coins Added",
            description=f"Added {amount} coins to {member.mention}\nNew Balance: {new_coins} 🪙",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        
        # Send mod log
        mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
        if mod_channel:
            log_embed = discord.Embed(
                title="Moderation Log - Coins Add",
                description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Amount:** {amount}\n**New Balance:** {new_coins} 🪙",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            await mod_channel.send(embed=log_embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to add coins: {str(e)}", ephemeral=True)

@bot.tree.command(name="unmute", description="Remove timeout/mute from a user")
@app_commands.describe(
    member="The user to unmute"
)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer()
    
    try:
        # Check if user has required permissions for the unmute
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.followup.send("❌ You don't have permission to unmute members!", ephemeral=True)
            return
            
        # Check if bot has required permissions
        if not interaction.guild.me.guild_permissions.moderate_members:
            await interaction.followup.send("❌ I don't have the 'Moderate Members' permission required to remove timeouts!", ephemeral=True)
            return
            
        # Check if trying to unmute a higher role
        if interaction.user != interaction.guild.owner and member.top_role >= interaction.user.top_role:
            await interaction.followup.send("❌ You cannot unmute someone with the same or higher role than you!", ephemeral=True)
            return
        
        # Check if the member is actually muted
        if not member.is_timed_out():
            await interaction.followup.send(f"ℹ️ {member.mention} is not currently muted/timed out.", ephemeral=True)
            return
            
        # Remove the timeout
        await member.timeout(None)
        
        # Create success embed
        embed = discord.Embed(
            title="🔊 User Unmuted", 
            description=f"{member.mention} has been unmuted.", 
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)

        # Send mod log
        mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
        if mod_channel:
            log_embed = discord.Embed(
                title="Moderation Log - Unmute",
                description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            await mod_channel.send(embed=log_embed)
    except Exception as e:
        print(f"Error in unmute command: {e}")
        await interaction.followup.send(f"❌ Failed to unmute user: {str(e)}", ephemeral=True)

@bot.tree.command(name="backup", description="Create a backup of all user data")
async def backup(interaction: discord.Interaction):
    # Ensure the user has appropriate permissions (staff/admin only)
    allowed_roles = [1338482857974169683]  # Staff role
    if not (any(role.id in allowed_roles for role in interaction.user.roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Call the backup_database function
    success = await backup_database()
    
    # Send database to the user who requested it if they're the owner
    owner_id = 1308527904497340467  # Your user ID
    if interaction.user.id == owner_id:
        try:
            # Send database files directly to user
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await interaction.user.send(f"📊 Database backup at {timestamp}", 
                files=[
                    discord.File("leveling.db", "leveling.db"),
                    discord.File("./backups/leveling_backup.db", "leveling_backup.db")
                ]
            )
            await interaction.followup.send("✅ Database backup completed and files sent to your DM!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"✅ Database backup completed, but failed to send files: {str(e)}", ephemeral=True)
    else:
        # For non-owner staff, just confirm backup without sending files
        await interaction.followup.send("✅ Database backup completed successfully!", ephemeral=True)
        
    # Send mod log
    mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
    if mod_channel:
            log_embed = discord.Embed(
                title="Moderation Log - Backup",
                description=f"**Moderator:** {interaction.user.mention}\n**Action:** Created database backup manually",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            await mod_channel.send(embed=log_embed)
    else:
        await interaction.followup.send("❌ An error occurred during backup. Check logs for details.", ephemeral=True)

@bot.tree.command(name="removepermission", description="Remove a section permission from a role")
@app_commands.describe(
    section="The permission section to remove",
    role="The role to remove permission from"
)
@app_commands.choices(section=[
    app_commands.Choice(name="Administrator", value="administrator"),
    app_commands.Choice(name="Moderator", value="moderator"),
    app_commands.Choice(name="Owner", value="owner"),
    app_commands.Choice(name="Chat Guardian (CG)", value="cg"),
    app_commands.Choice(name="Tournament Manager (TM)", value="tm"),
    app_commands.Choice(name="Tournament Streamer (TS)", value="ts"),
    app_commands.Choice(name="Engagement Team", value="engagement_team"),
    app_commands.Choice(name="Mini Games Organizer (MGO)", value="mgo"),
    app_commands.Choice(name="Giveaway Manager (GM)", value="gm")
])
async def removepermission(interaction: discord.Interaction, section: str, role: discord.Role):
    # Only super admin can manage permissions
    if interaction.user.id not in [1308527904497340467, 479711321399623681]:
        await interaction.response.send_message("❌ Only server owners can manage permissions!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    # Check if the section exists
    if section not in ROLE_PERMISSIONS:
        await interaction.followup.send(f"❌ Section `{section}` does not exist!", ephemeral=True)
        return
    
    # Get the display name of the section for messages
    section_display_name = section.replace('_', ' ').title()
    if section == "cg":
        section_display_name = "Chat Guardian (CG)"
    elif section == "tm":
        section_display_name = "Tournament Manager (TM)"
    elif section == "ts":
        section_display_name = "Tournament Streamer (TS)"
    elif section == "mgo":
        section_display_name = "Mini Games Organizer (MGO)"
    elif section == "gm":
        section_display_name = "Giveaway Manager (GM)"
    
    try:
        async with aiosqlite.connect("leveling.db") as db:
            # Get the role ID as string for database operations
            role_id_str = str(role.id)
            
            # First check if this role has this section assigned
            cursor = await db.execute('SELECT * FROM role_section_assignments WHERE role_id = ? AND section_name = ?', 
                                    (role_id_str, section))
            existing_assignment = await cursor.fetchone()
            
            if not existing_assignment:
                await interaction.followup.send(
                    f"ℹ️ {role.mention} doesn't have permissions for the {section_display_name} section.",
                    ephemeral=True
                )
                return
            
            # Get commands for this section
            commands_to_remove = ROLE_PERMISSIONS[section]
            
            # Begin a transaction for all operations
            await db.execute('BEGIN TRANSACTION')
            
            try:
                # Remove the section assignment
                await db.execute('DELETE FROM role_section_assignments WHERE role_id = ? AND section_name = ?',
                              (role_id_str, section))
                
                # Remove all command permissions that were granted through this section
                for cmd_name in commands_to_remove:
                    # Remove from database
                    await db.execute('DELETE FROM command_permissions WHERE command_name = ? AND permission_value = ?', 
                                  (cmd_name, role_id_str))
                    
                    # Also remove from in-memory dictionary if present
                    if cmd_name in command_permissions and role.id in command_permissions[cmd_name]:
                        command_permissions[cmd_name].remove(role.id)
                
                # Also remove from in-memory role_section_assignments
                if role.id in role_section_assignments and section in role_section_assignments[role.id]:
                    role_section_assignments[role.id].remove(section)
                    # If no more sections, remove the role entirely
                    if not role_section_assignments[role.id]:
                        del role_section_assignments[role.id]
                
                # Commit all changes
                await db.commit()
                
                # Send mod log
                mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
                if mod_channel:
                    log_embed = discord.Embed(
                        title="Permission Log - Section Removed",
                        description=f"**Role:** {role.mention}\n**Section:** {section_display_name}\n**Admin:** {interaction.user.mention}",
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow()
                    )
                    await mod_channel.send(embed=log_embed)
                
                await interaction.followup.send(
                    f"✅ Removed all permissions for the {section_display_name} section from {role.mention}.\n"
                    f"Commands removed: {', '.join(commands_to_remove)}",
                    ephemeral=True
                )
            except Exception as e:
                # If anything goes wrong, roll back all changes
                await db.execute('ROLLBACK')
                raise e
            
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in removepermission command: {e}")

@bot.tree.command(name="rolelvlall", description="Assign appropriate level roles to all members based on their current level")
async def rolelvlall(interaction: discord.Interaction):
    # Only allow staff to use this command
    allowed_roles = [1338482857974169683]  # Staff role
    if not (any(role.id in allowed_roles for role in interaction.user.roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
        
    await interaction.response.defer()
    
    try:
        # Get all level roles from database
        async with aiosqlite.connect("leveling.db") as db:
            # Get the level roles mapping
            cursor = await db.execute('SELECT level, role_id FROM level_roles ORDER BY level')
            level_roles_db = await cursor.fetchall()
            
            # If no roles in database, use the default mapping
            if not level_roles_db:
                # Fallback to hardcoded level roles if database is empty
                level_roles = {
                    5: 1339331106557657089,
                    10: 1339332632860950589,
                    15: 1339333949201186878,
                    20: 1339571891848876075,
                    25: 1339572201430454272,
                    30: 1339572204433838142,
                    35: 1339572206895894602,
                    40: 1339572209848680458,
                    45: 1339572212285575199,
                    50: 1339572214881714176,
                    55: 1339574559136944240,
                    60: 1339574564685873245,
                    65: 1339574564983804018,
                    70: 1339574565780590632,
                    75: 1339574566669783180,
                    80: 1339574568276332564,
                    85: 1339574568586842112,
                    90: 1339574569417048085,
                    95: 1339576526458322954,
                    100: 1339576529377820733
                }
            else:
                # Convert database results to dictionary
                level_roles = {}
                for lvl, role_id in level_roles_db:
                    level_roles[lvl] = role_id
            
            # Get all users with level 5 or higher
            cursor = await db.execute('SELECT user_id, level FROM users WHERE level >= 5')
            users = await cursor.fetchall()
            
            # Progress counters
            processed_count = 0
            updated_count = 0
            skipped_count = 0
            
            # Process each user
            for user_id, level in users:
                processed_count += 1
                
                try:
                    # Try to get the member from the guild
                    member = interaction.guild.get_member(user_id)
                    
                    # Skip if member is not found in the guild
                    if not member:
                        skipped_count += 1
                        continue
                    
                    # Find the highest level role that applies
                    highest_applicable_level = 0
                    for level_threshold in sorted(level_roles.keys()):
                        if level >= level_threshold:
                            highest_applicable_level = level_threshold
                        else:
                            break
                    
                    if highest_applicable_level > 0:
                        # Get the appropriate role
                        new_role = interaction.guild.get_role(level_roles[highest_applicable_level])
                        
                        # Remove any previous level roles
                        roles_to_remove = []
                        for lvl, role_id in level_roles.items():
                            if lvl != highest_applicable_level:  # Don't remove the current level role
                                role_obj = interaction.guild.get_role(role_id)
                                if role_obj and role_obj in member.roles:
                                    roles_to_remove.append(role_obj)
                        
                        # Remove old roles if any were found
                        if roles_to_remove:
                            await member.remove_roles(*roles_to_remove)
                        
                        # Add the new role if user doesn't already have it
                        if new_role and new_role not in member.roles:
                            await member.add_roles(new_role)
                            updated_count += 1
                        
                except Exception as e:
                    print(f"Error processing user {user_id}: {e}")
                    skipped_count += 1
            
        # Send completion message
        embed = discord.Embed(
            title="✅ Level Roles Assignment Complete",
            description=f"Processed {processed_count} members with level 5+\n"
                        f"Updated {updated_count} members with new roles\n"
                        f"Skipped {skipped_count} members (not found or error)",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
        
        # Send mod log
        mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
        if mod_channel:
            log_embed = discord.Embed(
                title="Moderation Log - Role Level Assignment",
                description=f"**Moderator:** {interaction.user.mention}\n"
                            f"**Action:** Ran role level assignment for all members\n"
                            f"**Results:** Updated {updated_count} of {processed_count} members",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            await mod_channel.send(embed=log_embed)
            
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in rolelvlall command: {e}")

@bot.tree.command(name="resetlevel", description="Reset all server members' levels/coins/xp")
async def resetlevel(interaction: discord.Interaction):

    try:
        async with aiosqlite.connect("leveling.db") as db:
            await db.execute('UPDATE users SET level = 1, prestige = 0, xp = 0, coins = 0, activity_coins = 0')
            await db.commit()

        embed = discord.Embed(
            title="🔄 Server Reset",
            description="All members' levels, XP, and coins have been reset!",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

        # Send mod log
        mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
        if mod_channel:
            log_embed = discord.Embed(
                title="Moderation Log - Server Reset",
                description=f"**Moderator:** {interaction.user.mention}\n**Action:** Reset all levels/XP/coins",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            await mod_channel.send(embed=log_embed)
    except:
        await interaction.response.send_message("❌ Failed to reset levels!", ephemeral=True)
        
@bot.tree.command(name="lvlrole", description="Create or manage level-based roles")
@app_commands.describe(
    action="Action to perform",
    level="Level required to get this role (5, 10, 15, etc. up to 100)",
    role="The role to assign at this level"
)
@app_commands.choices(action=[
    app_commands.Choice(name="set", value="set"),
    app_commands.Choice(name="remove", value="remove"),
    app_commands.Choice(name="list", value="list")
])
async def lvlrole(interaction: discord.Interaction, 
                  action: str, 
                  level: int = None, 
                  role: discord.Role = None):
    # Level roles mapping (levels 5, 10, 15, etc. up to 100)
    # We'll store it in the database but keep this copy for reference
    level_roles_reference = {
        5: 1339331106557657089,
        10: 1339332632860950589,
        15: 1339333949201186878,
        20: 1339571891848876075,
        25: 1339572201430454272,
        30: 1339572204433838142,
        35: 1339572206895894602,
        40: 1339572209848680458,
        45: 1339572212285575199,
        50: 1339572214881714176,
        55: 1339574559136944240,
        60: 1339574564685873245,
        65: 1339574564983804018,
        70: 1339574565780590632,
        75: 1339574566669783180,
        80: 1339574568276332564,
        85: 1339574568586842112,
        90: 1339574569417048085,
        95: 1339576526458322954,
        100: 1339576529377820733
    }
    
    try:
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator and interaction.user.id not in [1308527904497340467, 479711321399623681]:
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        async with aiosqlite.connect("leveling.db") as db:
            # Create table if it doesn't exist
            await db.execute('''
                CREATE TABLE IF NOT EXISTS level_roles (
                    level INTEGER PRIMARY KEY,
                    role_id INTEGER NOT NULL
                )
            ''')
            await db.commit()
            
            if action == "list":
                # List all level roles
                cursor = await db.execute('SELECT level, role_id FROM level_roles ORDER BY level')
                level_roles_db = await cursor.fetchall()
                
                if not level_roles_db:
                    await interaction.followup.send("No level roles have been set up yet.", ephemeral=True)
                    return
                
                embed = discord.Embed(
                    title="🏆 Level Roles",
                    description="These roles are automatically assigned when users reach specific levels:",
                    color=discord.Color.blue()
                )
                
                for lvl, role_id in level_roles_db:
                    role_obj = interaction.guild.get_role(role_id)
                    role_name = role_obj.name if role_obj else "Unknown Role"
                    embed.add_field(
                        name=f"Level {lvl}",
                        value=f"Role: {role_obj.mention if role_obj else 'Role not found'} ({role_id})",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            elif action == "set":
                # Validate parameters
                if level is None or role is None:
                    await interaction.followup.send("❌ Level and role parameters are required for 'set' action.", ephemeral=True)
                    return
                
                # Validate level value (5, 10, 15, etc. up to 100)
                if level <= 0 or level > 100 or level % 5 != 0:
                    await interaction.followup.send("❌ Level must be a multiple of 5 between 5 and 100 (5, 10, 15, etc.)", ephemeral=True)
                    return
                
                # Add or update level role mapping
                await db.execute(
                    'INSERT OR REPLACE INTO level_roles (level, role_id) VALUES (?, ?)',
                    (level, role.id)
                )
                await db.commit()
                
                embed = discord.Embed(
                    title="✅ Level Role Set",
                    description=f"Users who reach level {level} will now receive the {role.mention} role.",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # Send mod log
                mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
                if mod_channel:
                    log_embed = discord.Embed(
                        title="Level Roles - Role Added",
                        description=f"**Level:** {level}\n**Role:** {role.mention}\n**Admin:** {interaction.user.mention}",
                        color=discord.Color.green(),
                        timestamp=discord.utils.utcnow()
                    )
                    await mod_channel.send(embed=log_embed)
                
            elif action == "remove":
                # Validate parameters
                if level is None:
                    await interaction.followup.send("❌ Level parameter is required for 'remove' action.", ephemeral=True)
                    return
                
                # Check if the level role mapping exists
                cursor = await db.execute('SELECT role_id FROM level_roles WHERE level = ?', (level,))
                existing_role = await cursor.fetchone()
                
                if not existing_role:
                    await interaction.followup.send(f"❌ No role is currently set for level {level}.", ephemeral=True)
                    return
                
                # Remove the level role mapping
                await db.execute('DELETE FROM level_roles WHERE level = ?', (level,))
                await db.commit()
                
                embed = discord.Embed(
                    title="🗑️ Level Role Removed",
                    description=f"The role assignment for level {level} has been removed.",
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # Send mod log
                mod_channel = bot.get_channel(MOD_LOGS_CHANNEL)
                if mod_channel:
                    role_obj = interaction.guild.get_role(existing_role[0])
                    role_name = role_obj.name if role_obj else f"Unknown Role ({existing_role[0]})"
                    log_embed = discord.Embed(
                        title="Level Roles - Role Removed",
                        description=f"**Level:** {level}\n**Role:** {role_name}\n**Admin:** {interaction.user.mention}",
                        color=discord.Color.orange(),
                        timestamp=discord.utils.utcnow()
                    )
                    await mod_channel.send(embed=log_embed)
            
            else:
                await interaction.followup.send("❌ Invalid action. Use 'set', 'remove', or 'list'.", ephemeral=True)
                
    except Exception as e:
        print(f"Error in lvlrole command: {e}")
        await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

# Store user profiles
user_profiles = {}

# RoleButton and NotificationButton classes have been removed as requested

# ProfileView class has been removed as requested

# Birthday and Timezone UI components have been removed as requested









# XP Event command
@bot.tree.command(name="xpevent", description="Start an automatic XP drop event in the specified channel")
async def xpevent(interaction: discord.Interaction, channel: discord.TextChannel, duration: int, time_unit: str):
    allowed_roles = [1338482857974169683]  # Staff role
    if not (any(role.id in allowed_roles for role in interaction.user.roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ Only Staff can use this command!", ephemeral=True)
        return
    
    time_unit = time_unit.lower()
    if time_unit not in ["sec", "min", "hour"]:
        await interaction.response.send_message("❌ Invalid time unit! Use sec, min, or hour.", ephemeral=True)
        return
    
    # Check if duration is valid before deferring
    if time_unit == "sec" and duration < 60:
        await interaction.response.send_message("❌ Minimum interval is 1 minute!", ephemeral=True)
        return
    elif time_unit == "min" and duration < 1:
        await interaction.response.send_message("❌ Minimum interval is 1 minute!", ephemeral=True)
        return
    
    # Now we can defer the response
    await interaction.response.defer(ephemeral=True)
    await start_xp_event(interaction, channel, duration, time_unit)
    await interaction.followup.send(f"✅ XP drop event started in {channel.mention}! It will drop XP every {duration} {time_unit}.", ephemeral=True)

# Coin Event command
@bot.tree.command(name="coinevent", description="Start an automatic coin drop event in the specified channel")
async def coinevent(interaction: discord.Interaction, channel: discord.TextChannel, duration: int, time_unit: str):
    allowed_roles = [1338482857974169683]  # Staff role
    if not (any(role.id in allowed_roles for role in interaction.user.roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ Only Staff can use this command!", ephemeral=True)
        return
    
    time_unit = time_unit.lower()
    if time_unit not in ["sec", "min", "hour"]:
        await interaction.response.send_message("❌ Invalid time unit! Use sec, min, or hour.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    await start_coin_event(interaction, channel, duration, time_unit)
    await interaction.followup.send(f"✅ Coin drop event started in {channel.mention}! It will drop coins every {duration} {time_unit}.", ephemeral=True)

# Daily Quest command
@bot.tree.command(name="dailyquest", description="View your daily quests and track progress")
async def dailyquest(interaction: discord.Interaction):
    try:
        # Daily quests can be used in DMs as well - no guild check needed
        await interaction.response.defer(ephemeral=True)
        
        # Check if this is a DM or guild channel
        is_dm = interaction.guild is None
        
        # For DMs, we'll handle the response differently
        if is_dm:
            # In DMs, we don't want to use ephemeral messages as they don't make sense
            # Also, we'll send the response directly to the channel
            await check_daily_quests(interaction.user.id, interaction.channel, interaction.user, interaction=interaction)
        else:
            # In guild channels, use the normal flow
            await check_daily_quests(interaction.user.id, interaction.channel, interaction.user, interaction=interaction)
    except Exception as e:
        print(f"Error in dailyquest command: {e}")
        await interaction.followup.send("❌ An error occurred while checking your daily quests. Please try again later.", ephemeral=True)

# Profile functionality now handled by natural language pattern detection
# Profile command has been removed as requested

@bot.tree.command(name="activitystart", description="Start an activity event!")
async def activitystart(interaction: discord.Interaction, duration: str,
                        time_unit: str, prize: str):
    allowed_roles = [1338482857974169683]  # Staff role
    if not (any(role.id in allowed_roles for role in interaction.user.roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ Only Staff can use this command!", ephemeral=True)
        return

    time_unit = time_unit.lower()
    if time_unit not in ["sec", "min", "hour", "day"]:
        await interaction.response.send_message(
            "❌ Invalid time unit! Use sec, min, hour, or day.", ephemeral=True)
        return

    time_multipliers = {"sec": 1, "min": 60, "hour": 3600, "day": 86400}

    try:
        duration_seconds = int(duration) * time_multipliers[time_unit]
    except ValueError:
        await interaction.response.send_message("❌ Invalid duration!",
                                                ephemeral=True)
        return

    # Reset activity coins with visual confirmation
    await interaction.response.defer()
    async with aiosqlite.connect("leveling.db") as db:
        # Reset all user activity coins
        await db.execute('UPDATE users SET activity_coins = 0')
        
        # Update activity event state in database for persistence
        end_time = discord.utils.utcnow() + timedelta(seconds=duration_seconds)
        
        await db.execute('''
            UPDATE activity_event_state 
            SET active = 1, 
                end_time = ?, 
                prize = ? 
            WHERE id = 1
        ''', (end_time.isoformat(), prize))
        
        await db.commit()

    # Update in-memory state as well
    activity_event["active"] = True
    activity_event["end_time"] = end_time
    activity_event["prize"] = prize

    embed = discord.Embed(
        title="🎯 ACTIVITY EVENT STARTED",
        description=
        f"```diff\n+ A new activity event has begun!\n```\n🎁 **Prize:** {prize}\n⏰ **Duration:** {duration} {time_unit}\n\n📝 **How to earn coins:**\n> • 1 coin per message\n\n🔄 **Leaderboard has been reset!** Everyone starts from 0.\n\n💫 **Good luck everyone!**",
        color=0x2F3136,
        timestamp=discord.utils.utcnow())
    embed.set_footer(text="✨ Start chatting to earn activity coins!")

    # Store the channel where the event was started for notifications
    event_channel = interaction.channel
    event_message = await interaction.followup.send(embed=embed)
    
    # Calculate notification intervals (every 15 minutes)
    notification_interval = 900  # 15 minutes in seconds
    
    # Wait for event to end with periodic notifications
    remaining_seconds = duration_seconds
    while remaining_seconds > 0:
        # Special case for final minute
        if remaining_seconds <= 60 and remaining_seconds > 0:
            # Send a final 1-minute warning
            final_warning_embed = discord.Embed(
                title="⏰ FINAL WARNING!",
                description=f"**Only 1 minute remaining** in the activity event!\n\n🎁 **Prize:** {prize}\n\n💬 Last chance to earn activity coins!",
                color=0xFF2D74,
                timestamp=discord.utils.utcnow()
            )
            await event_channel.send(embed=final_warning_embed)
            
            # Sleep for remaining time
            await asyncio.sleep(remaining_seconds)
            remaining_seconds = 0
            continue
        
        # Special case for final 5 minutes
        if remaining_seconds <= 300 and remaining_seconds > 60:
            # Send a 5-minute warning
            warning_embed = discord.Embed(
                title="⏰ 5-MINUTE WARNING!",
                description=f"**Only 5 minutes remaining** in the activity event!\n\n🎁 **Prize:** {prize}\n\n💬 Keep chatting to earn more activity coins!",
                color=0xFFA500,  # Orange
                timestamp=discord.utils.utcnow()
            )
            await event_channel.send(embed=warning_embed)
            
            # Set the next notification to be at 1 minute
            sleep_time = remaining_seconds - 60
            await asyncio.sleep(sleep_time)
            remaining_seconds = 60
            continue
        
        # Normal case: Sleep for the shorter of notification_interval or remaining_seconds
        sleep_time = min(notification_interval, remaining_seconds)
        await asyncio.sleep(sleep_time)
        remaining_seconds -= sleep_time
        
        # If we've reached a notification point and there's still time left
        if remaining_seconds > 0 and sleep_time == notification_interval:
            # Format remaining time
            hours, remainder = divmod(remaining_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                time_format = f"{hours}h {minutes}m"
            elif minutes > 0:
                time_format = f"{minutes}m {seconds}s"
            else:
                time_format = f"{seconds}s"
            
            # Get current activity leaderboard top 3
            async with aiosqlite.connect("leveling.db") as db:
                cursor = await db.execute('''
                    SELECT user_id, activity_coins 
                    FROM users 
                    WHERE activity_coins > 0 
                    ORDER BY activity_coins DESC LIMIT 3
                ''')
                top_users = await cursor.fetchall()
            
            # Format leaderboard
            leaderboard_text = ""
            if top_users:
                for i, (user_id, coins) in enumerate(top_users):
                    try:
                        user = await bot.fetch_user(user_id)
                        username = user.display_name
                    except:
                        username = f"User {user_id}"
                    
                    medal = ["🥇", "🥈", "🥉"][i]
                    leaderboard_text += f"{medal} **{username}**: {coins} coins\n"
            else:
                leaderboard_text = "No participants yet!"
                
            # Send notification with time remaining and current top 3
            reminder_embed = discord.Embed(
                title="⏰ ACTIVITY EVENT REMINDER",
                description=f"**{time_format} remaining** in the current activity event!\n\n🎁 **Prize:** {prize}\n\n📊 **Current Leaders:**\n{leaderboard_text}\n\n💬 Keep chatting to earn more activity coins!",
                color=0x2F3136,
                timestamp=discord.utils.utcnow()
            )
            
            await event_channel.send(embed=reminder_embed)
    
    # Update both in-memory and database state
    activity_event["active"] = False
    activity_event["end_time"] = None
    activity_event["prize"] = None
    
    # Update database
    async with aiosqlite.connect("leveling.db") as db:
        await db.execute('''
            UPDATE activity_event_state 
            SET active = 0, 
                end_time = NULL, 
                prize = NULL 
            WHERE id = 1
        ''')
        await db.commit()

    # Get final results
    async with aiosqlite.connect("leveling.db") as db:
        cursor = await db.execute(
            'SELECT user_id, activity_coins FROM users ORDER BY activity_coins DESC LIMIT 1'
        )
        winner = await cursor.fetchone()

    if winner:
        user = await bot.fetch_user(winner[0])
        coins = int(winner[1])

        result_embed = discord.Embed(
            title="🎊 ACTIVITY EVENT ENDED!",
            description=
            f"```diff\n+ Congratulations to our winner!\n```\n👑 **Winner:** {user.mention}\n🎁 **Prize:** {prize}\n💰 **Coins Earned:** {coins}",
            color=0xFF2D74,
            timestamp=discord.utils.utcnow())
        await interaction.channel.send(embed=result_embed)

# Tasks are started in the on_ready function
# Note: The XP drop event task is defined earlier in this file

# Daily Quest Classes and UI Components

class QuestTypeView(discord.ui.View):
    """View for selecting the type of daily quest to configure"""
    def __init__(self):
        super().__init__(timeout=300)  # 5 minute timeout
    
    @discord.ui.button(label="Voice Quest", style=discord.ButtonStyle.primary, emoji="🎙️")
    async def voice_quest_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VoiceQuestModal())
    
    @discord.ui.button(label="Chat Quest", style=discord.ButtonStyle.primary, emoji="💬")
    async def chat_quest_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChatQuestModal())
    
    @discord.ui.button(label="Reaction Quest", style=discord.ButtonStyle.primary, emoji="👍")
    async def reaction_quest_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReactionQuestModal())
        
    @discord.ui.button(label="Invite Quest", style=discord.ButtonStyle.primary, emoji="📨")
    async def invite_quest_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(InviteQuestModal())


class VoiceQuestModal(discord.ui.Modal, title="Configure Voice Quest"):
    """Modal for configuring voice quest parameters"""
    
    voice_time = discord.ui.TextInput(
        label="Voice Time (minutes)",
        placeholder="Enter the required voice time in minutes (e.g., 30)",
        min_length=1,
        max_length=4,
        required=True
    )
    
    xp_reward = discord.ui.TextInput(
        label="XP Reward",
        placeholder="Enter the XP reward amount (e.g., 500)",
        min_length=1,
        max_length=5,
        required=True
    )
    
    coin_reward = discord.ui.TextInput(
        label="Coin Reward",
        placeholder="Enter the coin reward amount (e.g., 100)",
        min_length=1,
        max_length=5,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate inputs are integers
            voice_minutes = int(self.voice_time.value)
            xp = int(self.xp_reward.value)
            coins = int(self.coin_reward.value)
            
            if voice_minutes <= 0 or xp <= 0 or coins <= 0:
                await interaction.response.send_message("❌ All values must be positive numbers!", ephemeral=True)
                return
                
            # Save quest to database
            async with aiosqlite.connect("leveling.db") as db:
                # Deactivate any existing voice quests
                await db.execute('UPDATE daily_quests SET active = 0 WHERE quest_type = "voice" AND active = 1')
                
                # Add new quest
                await db.execute('''
                    INSERT INTO daily_quests (quest_type, goal_amount, xp_reward, coin_reward)
                    VALUES (?, ?, ?, ?)
                ''', ("voice", voice_minutes, xp, coins))
                
                await db.commit()
            
            # Confirmation message
            embed = discord.Embed(
                title="✅ Daily Voice Quest Configured",
                description=f"The daily voice quest has been set up successfully!",
                color=discord.Color.green()
            )
            embed.add_field(name="Voice Time Required", value=f"{voice_minutes} minutes", inline=True)
            embed.add_field(name="XP Reward", value=f"{xp} XP", inline=True)
            embed.add_field(name="Coin Reward", value=f"{coins} 🪙", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers for all fields!", ephemeral=True)
        except Exception as e:
            print(f"Error setting up voice quest: {e}")
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)


class ChatQuestModal(discord.ui.Modal, title="Configure Chat Quest"):
    """Modal for configuring chat quest parameters"""
    
    message_count = discord.ui.TextInput(
        label="Message Count",
        placeholder="Enter the required number of messages (e.g., 50)",
        min_length=1,
        max_length=4,
        required=True
    )
    
    xp_reward = discord.ui.TextInput(
        label="XP Reward",
        placeholder="Enter the XP reward amount (e.g., 500)",
        min_length=1,
        max_length=5,
        required=True
    )
    
    coin_reward = discord.ui.TextInput(
        label="Coin Reward",
        placeholder="Enter the coin reward amount (e.g., 100)",
        min_length=1,
        max_length=5,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate inputs are integers
            messages = int(self.message_count.value)
            xp = int(self.xp_reward.value)
            coins = int(self.coin_reward.value)
            
            if messages <= 0 or xp <= 0 or coins <= 0:
                await interaction.response.send_message("❌ All values must be positive numbers!", ephemeral=True)
                return
                
            # Save quest to database
            async with aiosqlite.connect("leveling.db") as db:
                # Deactivate any existing chat quests
                await db.execute('UPDATE daily_quests SET active = 0 WHERE quest_type = "chat" AND active = 1')
                
                # Add new quest
                await db.execute('''
                    INSERT INTO daily_quests (quest_type, goal_amount, xp_reward, coin_reward)
                    VALUES (?, ?, ?, ?)
                ''', ("chat", messages, xp, coins))
                
                await db.commit()
            
            # Confirmation message
            embed = discord.Embed(
                title="✅ Daily Chat Quest Configured",
                description=f"The daily chat quest has been set up successfully!",
                color=discord.Color.green()
            )
            embed.add_field(name="Messages Required", value=f"{messages} messages", inline=True)
            embed.add_field(name="XP Reward", value=f"{xp} XP", inline=True)
            embed.add_field(name="Coin Reward", value=f"{coins} 🪙", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers for all fields!", ephemeral=True)
        except Exception as e:
            print(f"Error setting up chat quest: {e}")
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)


class InviteQuestModal(discord.ui.Modal, title="Configure Invite Quest"):
    """Modal for configuring invite quest parameters"""
    
    invite_count = discord.ui.TextInput(
        label="Invite Count",
        placeholder="Enter the required number of invites (e.g., 3)",
        min_length=1,
        max_length=2,
        required=True
    )
    
    xp_reward = discord.ui.TextInput(
        label="XP Reward",
        placeholder="Enter the XP reward amount (e.g., 500)",
        min_length=1,
        max_length=5,
        required=True
    )
    
    coin_reward = discord.ui.TextInput(
        label="Coin Reward",
        placeholder="Enter the coin reward amount (e.g., 100)",
        min_length=1,
        max_length=5,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate inputs are integers
            invites = int(self.invite_count.value)
            xp = int(self.xp_reward.value)
            coins = int(self.coin_reward.value)
            
            if invites <= 0 or xp <= 0 or coins <= 0:
                await interaction.response.send_message("❌ All values must be positive numbers!", ephemeral=True)
                return
                
            # Save quest to database
            async with aiosqlite.connect("leveling.db") as db:
                # Deactivate any existing invite quests
                await db.execute('UPDATE daily_quests SET active = 0 WHERE quest_type = "invite" AND active = 1')
                
                # Add new quest
                await db.execute('''
                    INSERT INTO daily_quests (quest_type, goal_amount, xp_reward, coin_reward)
                    VALUES (?, ?, ?, ?)
                ''', ("invite", invites, xp, coins))
                
                await db.commit()
            
            # Confirmation message
            embed = discord.Embed(
                title="✅ Daily Invite Quest Configured",
                description=f"The daily invite quest has been set up successfully!",
                color=discord.Color.green()
            )
            embed.add_field(name="Invites Required", value=f"{invites} invites", inline=True)
            embed.add_field(name="XP Reward", value=f"{xp} XP", inline=True)
            embed.add_field(name="Coin Reward", value=f"{coins} 🪙", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers for all fields!", ephemeral=True)
        except Exception as e:
            print(f"Error setting up invite quest: {e}")
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

class ReactionQuestModal(discord.ui.Modal, title="Configure Reaction Quest"):
    """Modal for configuring reaction quest parameters"""
    
    reaction_count = discord.ui.TextInput(
        label="Reaction Count",
        placeholder="Enter the required number of reactions (e.g., 20)",
        min_length=1,
        max_length=4,
        required=True
    )
    
    xp_reward = discord.ui.TextInput(
        label="XP Reward",
        placeholder="Enter the XP reward amount (e.g., 500)",
        min_length=1,
        max_length=5,
        required=True
    )
    
    coin_reward = discord.ui.TextInput(
        label="Coin Reward",
        placeholder="Enter the coin reward amount (e.g., 100)",
        min_length=1,
        max_length=5,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate inputs are integers
            reactions = int(self.reaction_count.value)
            xp = int(self.xp_reward.value)
            coins = int(self.coin_reward.value)
            
            if reactions <= 0 or xp <= 0 or coins <= 0:
                await interaction.response.send_message("❌ All values must be positive numbers!", ephemeral=True)
                return
                
            # Save quest to database
            async with aiosqlite.connect("leveling.db") as db:
                # Deactivate any existing reaction quests
                await db.execute('UPDATE daily_quests SET active = 0 WHERE quest_type = "reaction" AND active = 1')
                
                # Add new quest
                await db.execute('''
                    INSERT INTO daily_quests (quest_type, goal_amount, xp_reward, coin_reward)
                    VALUES (?, ?, ?, ?)
                ''', ("reaction", reactions, xp, coins))
                
                await db.commit()
            
            # Confirmation message
            embed = discord.Embed(
                title="✅ Daily Reaction Quest Configured",
                description=f"The daily reaction quest has been set up successfully!",
                color=discord.Color.green()
            )
            embed.add_field(name="Reactions Required", value=f"{reactions} reactions", inline=True)
            embed.add_field(name="XP Reward", value=f"{xp} XP", inline=True)
            embed.add_field(name="Coin Reward", value=f"{coins} 🪙", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers for all fields!", ephemeral=True)
        except Exception as e:
            print(f"Error setting up reaction quest: {e}")
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)


class DailyQuestView(discord.ui.View):
    """View for the user's daily quest progress"""
    def __init__(self, user_id: int, quest_data=None):
        super().__init__(timeout=180)  # 3 minute timeout
        self.user_id = user_id
        self.quest_data = quest_data
    
    @discord.ui.button(label="Claim Rewards", style=discord.ButtonStyle.success, emoji="✅")
    async def claim_rewards_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your quest!", ephemeral=True)
            return
            
        # Check if the user has completed any quests that haven't been claimed
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute('''
                SELECT
                    q.rowid AS quest_id,
                    q.quest_type,
                    q.goal_amount,
                    q.xp_reward,
                    q.coin_reward,
                    p.current_progress,
                    p.completed
                FROM
                    daily_quests AS q
                JOIN
                    user_quest_progress AS p ON q.rowid = p.quest_id
                WHERE
                    p.user_id = ? AND q.active = 1 AND p.completed = 1 AND p.claimed = 0
            ''', (self.user_id,))
            
            completed_quests = await cursor.fetchall()
            
        if not completed_quests:
            await interaction.response.send_message("❌ You haven't completed any daily quests yet!", ephemeral=True)
            return
            
        # Process rewards for each completed quest
        total_xp = 0
        total_coins = 0
        quest_details = []
        
        # Respond to the interaction before any database operations
        await interaction.response.defer()
        
        # Award the rewards
        async with aiosqlite.connect("leveling.db") as db:
            for quest in completed_quests:
                quest_id, quest_type, goal, xp_reward, coin_reward, progress, completed = quest
                
                # Mark as claimed
                await db.execute('''
                    UPDATE user_quest_progress
                    SET claimed = 1
                    WHERE user_id = ? AND quest_id = ?
                ''', (self.user_id, quest_id))
                
                total_xp += xp_reward
                total_coins += coin_reward
                
                quest_details.append({
                    "type": quest_type,
                    "goal": goal,
                    "xp": xp_reward,
                    "coins": coin_reward
                })
            
            # Update user level, XP and coins
            # First get current user stats
            cursor = await db.execute(
                'SELECT level, prestige, xp, coins FROM users WHERE user_id = ?',
                (self.user_id,)
            )
            user_data = await cursor.fetchone()
            
            if user_data is None:
                # User doesn't exist in database, create a new record with level up from rewards
                # Calculate how many levels to add based on total XP
                new_level = 1
                remaining_xp = total_xp
                xp_needed_for_next = calculate_xp_needed(new_level)
                levels_gained = 0
                level_up_coins = 0
                
                while remaining_xp >= xp_needed_for_next:
                    remaining_xp -= xp_needed_for_next
                    new_level += 1
                    levels_gained += 1
                    level_up_coins += xp_settings.get("level_up_coins", 150)  # Get coins per level from settings
                    xp_needed_for_next = calculate_xp_needed(new_level)
                
                # Add level-up coins to total coins
                total_with_level_coins = total_coins + level_up_coins
                
                await db.execute(
                    'INSERT INTO users (user_id, level, prestige, xp, coins) VALUES (?, ?, 0, ?, ?)',
                    (self.user_id, new_level, remaining_xp, total_with_level_coins)
                )
                level, prestige, xp, coins = new_level, 0, remaining_xp, total_with_level_coins
                
                # Send level up notification
                if levels_gained > 0:
                    # Create a rich embed for level up
                    embed = discord.Embed(
                        title="🎊 LEVEL UP! 🎊",
                        description=f"<@{self.user_id}> has reached **level {new_level}**!",
                        color=discord.Color.gold()
                    )
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    embed.add_field(name="Quest Rewards", 
                                    value=f"✨ +{total_xp} XP\n🪙 +{total_coins} Coins from quests\n🎊 +{level_up_coins} Coins from leveling up!", 
                                    inline=False)
                    
                    # Send to the current channel
                    await interaction.channel.send(embed=embed)
                    
                    # Try to send to the dedicated level-up announcements channel if it exists
                    level_channel = bot.get_channel(1348430879363735602)  # XP level up channel
                    if level_channel and level_channel.id != interaction.channel.id:
                        await level_channel.send(embed=embed)
            else:
                level, prestige, xp, coins = user_data
                old_level = level
                
                # Add coins right away
                new_coins = coins + total_coins
                
                # Calculate level ups and rewards
                old_level = level
                levels_gained = 0
                level_up_coins = 0
                new_xp = xp + total_xp
                
                # Check for level ups based on new XP
                while new_xp >= calculate_xp_needed(level):
                    new_xp -= calculate_xp_needed(level)
                    level += 1
                    levels_gained += 1
                    level_up_coins += xp_settings.get("level_up_coins", 150)  # Get coins per level from settings
                
                # Add both quest coins and level-up coins
                total_with_level_coins = total_coins + level_up_coins
                new_coins = coins + total_with_level_coins
                
                # Update the user's record
                await db.execute(
                    'UPDATE users SET level = ?, xp = ?, coins = ? WHERE user_id = ?',
                    (level, new_xp, new_coins, self.user_id)
                )
                
                # Send level up notification if level increased
                if level > old_level:
                    # Create a rich embed for level up
                    embed = discord.Embed(
                        title="🎊 LEVEL UP! 🎊",
                        description=f"<@{self.user_id}> has advanced from level {old_level} to **level {level}**!",
                        color=discord.Color.gold()
                    )
                    embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    embed.add_field(name="Quest Rewards", 
                                   value=f"✨ +{total_xp} XP\n🪙 +{total_coins} Coins from quests\n🎊 +{level_up_coins} Coins from leveling up!", 
                                   inline=False)
                    
                    # Calculate new benefits or unlocks if any
                    level_benefits = ""
                    if level % 5 == 0:  # Every 5 levels
                        level_benefits = f"🏆 You've reached a milestone level! Special perks may be available."
                    
                    if level_benefits:
                        embed.add_field(name="Level Benefits", value=level_benefits, inline=False)
                    
                    # Send to the current channel
                    await interaction.channel.send(embed=embed)
                    
                    # Try to send to the dedicated level-up announcements channel if it exists
                    level_channel = bot.get_channel(1348430879363735602)  # XP level up channel
                    if level_channel and level_channel.id != interaction.channel.id:
                        await level_channel.send(embed=embed)
                
            await db.commit()
        
        # Send a message with the rewards
        reward_message = f"🎉 You've claimed rewards from {len(completed_quests)} quests!\n\n"
        reward_message += f"**Total Rewards:**\n"
        reward_message += f"✨ XP: +{total_xp}\n"
        reward_message += f"🪙 Coins: +{total_coins} from quests\n"
        
        # If level-up coins were earned, show them too
        if 'level_up_coins' in locals() and level_up_coins > 0:
            reward_message += f"🎊 Bonus Coins: +{level_up_coins} from leveling up!\n\n"
        else:
            reward_message += "\n"
        
        # Show quest details
        for i, quest in enumerate(quest_details):
            quest_type = quest["type"].capitalize()
            reward_message += f"**Quest {i+1}:** {quest_type} ({quest['goal']})\n"
            reward_message += f"✨ +{quest['xp']} XP, 🪙 +{quest['coins']} Coins\n"
        
        await interaction.followup.send(reward_message, ephemeral=True)
        
        # Refresh the daily quest display
        await check_daily_quests(self.user_id, interaction.channel, interaction.user, interaction=interaction)
    
    @discord.ui.button(label="Mark As Done", style=discord.ButtonStyle.primary, emoji="🔄")
    async def mark_done_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your quest!", ephemeral=True)
            return
        
        # If we don't have quest data, we need to fetch it
        if not self.quest_data:
            async with aiosqlite.connect("leveling.db") as db:
                cursor = await db.execute('''
                    SELECT
                        p.quest_id,
                        q.quest_type,
                        q.goal_amount,
                        p.current_progress
                    FROM
                        user_quest_progress AS p
                    JOIN
                        daily_quests AS q ON p.quest_id = q.rowid
                    WHERE
                        p.user_id = ? AND q.active = 1 AND p.completed = 0
                ''', (self.user_id,))
                
                quests_to_update = await cursor.fetchall()
        else:
            # Use the quest data that was passed
            quests_to_update = self.quest_data
        
        if not quests_to_update:
            await interaction.response.send_message("❌ You don't have any quests to mark as done!", ephemeral=True)
            return
        
        # Defer the response since we'll be doing database operations
        await interaction.response.defer()
        
        # Update all quests to be completed
        updated = False
        async with aiosqlite.connect("leveling.db") as db:
            for quest in quests_to_update:
                quest_id = quest[0]
                goal_amount = quest[2]
                
                # Mark the quest as completed with full progress
                await db.execute('''
                    UPDATE user_quest_progress
                    SET current_progress = ?, completed = 1
                    WHERE user_id = ? AND quest_id = ?
                ''', (goal_amount, self.user_id, quest_id))
                updated = True
            
            if updated:
                await db.commit()
        
        # Send a success message
        success_message = "✅ Your quests have been marked as completed! You can now claim your rewards."
        await interaction.followup.send(success_message, ephemeral=True)
                
        # Refresh the daily quest display
        await check_daily_quests(self.user_id, interaction.channel, interaction.user, interaction=interaction)


# Daily Quest Commands

@bot.tree.command(name="dailyquestset", description="Configure the daily quests for server members")
async def dailyquestset(interaction: discord.Interaction):
    
    embed = discord.Embed(
        title="📋 Daily Quest Configuration",
        description="Select the type of daily quest you want to configure:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎙️ Voice Quest",
        value="Set up a quest for voice channel activity",
        inline=False
    )
    
    embed.add_field(
        name="💬 Chat Quest",
        value="Set up a quest for message activity",
        inline=False
    )
    
    embed.add_field(
        name="👍 Reaction Quest", 
        value="Set up a quest for reaction activity",
        inline=False
    )
    
    view = QuestTypeView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="stopevents", description="Stop all active XP and coin drop events")
async def stopevents(interaction: discord.Interaction):
    # Check if the user has permission to use this command
    has_permission = await check_permissions(interaction, "stopevents")
    if not has_permission:
        return
    
    await interaction.response.defer(ephemeral=True)
    
    stopped_events = []
    
    # Stop XP events
    for channel_id, task in list(xp_event_tasks.items()):
        try:
            if not task.done() and not task.cancelled():
                task.cancel()
                del xp_event_tasks[channel_id]
                channel = bot.get_channel(channel_id)
                channel_name = channel.name if channel else f"Channel {channel_id}"
                stopped_events.append(f"XP Event in #{channel_name}")
        except Exception as e:
            print(f"Error stopping XP event in channel {channel_id}: {e}")
    
    # Stop Coin events
    for channel_id, task in list(coin_event_tasks.items()):
        try:
            if not task.done() and not task.cancelled():
                task.cancel()
                del coin_event_tasks[channel_id]
                channel = bot.get_channel(channel_id)
                channel_name = channel.name if channel else f"Channel {channel_id}"
                stopped_events.append(f"Coin Event in #{channel_name}")
        except Exception as e:
            print(f"Error stopping Coin event in channel {channel_id}: {e}")
    
    # Create and send response embed
    embed = discord.Embed(
        title="🛑 Events Stopped",
        color=discord.Color.red()
    )
    
    if stopped_events:
        embed.description = "The following events have been stopped:\n• " + "\n• ".join(stopped_events)
    else:
        embed.description = "No active events were found to stop."
    
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
    
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="embed", description="Create and send a custom embed message")
async def embed(interaction: discord.Interaction, 
                title: str, 
                description: str, 
                color: str = "blue", 
                thumbnail: str = None, 
                footer: str = None, 
                image: str = None):
    # Check if the user has permission to use this command
    has_permission = await check_permissions(interaction, "embed")
    if not has_permission:
        return

    # Convert color string to discord.Color
    color_mapping = {
        "blue": discord.Color.blue(),
        "red": discord.Color.red(),
        "green": discord.Color.green(),
        "gold": discord.Color.gold(),
        "orange": discord.Color.orange(),
        "purple": discord.Color.purple(),
        "blurple": discord.Color.blurple(),
        "magenta": discord.Color.magenta(),
        "teal": discord.Color.teal(),
        "dark_blue": discord.Color.dark_blue(),
        "dark_green": discord.Color.dark_green(),
        "dark_red": discord.Color.dark_red(),
        "yellow": discord.Color.yellow()
    }
    
    # Get the color or default to blue
    embed_color = color_mapping.get(color.lower(), discord.Color.blue())
    
    # Create the embed
    embed = discord.Embed(
        title=title,
        description=description,
        color=embed_color
    )
    
    # Add thumbnail if provided
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    
    # Add footer if provided
    if footer:
        embed.set_footer(text=footer)
    
    # Add image if provided
    if image:
        embed.set_image(url=image)
    
    # Send the embed
    await interaction.response.send_message("✅ Sending your embed...", ephemeral=True)
    await interaction.channel.send(embed=embed)


@bot.tree.command(name="editleveling", description="Edit leveling system settings")
async def editleveling(interaction: discord.Interaction):
    """Edit leveling system settings - this command allows server owners to adjust
    various XP, coins, and other settings for the leveling system"""
    
    # Store the global variable that will be used to share settings between functions
    global xp_settings
    
    # Check if user has permission
    if interaction.user.id not in [1308527904497340467, 479711321399623681]:
        await interaction.response.send_message("❌ Only server owners can edit leveling settings!", ephemeral=True)
        return
    
    # Defer the response to avoid interaction timeout
    await interaction.response.defer(ephemeral=True)
        
    # Ensure the leveling_settings table exists before querying it
    try:
        # First try to use our enhanced fix_leveling_settings module with non-destructive repair
        try:
            print("Attempting to repair/ensure leveling_settings table exists before running command...")
            from fix_leveling_settings import repair_settings
            
            # Use the most robust repair function
            if repair_settings():
                print("✅ Successfully repaired leveling_settings table")
            else:
                print("⚠️ Repair reported failure, but we'll attempt to proceed anyway")
                
        except ImportError:
            print("⚠️ Could not import fix_leveling_settings module")
        except Exception as repair_error:
            print(f"⚠️ Warning: Failed to run table repair functions: {repair_error}")
        
        # Try the original reset function as a fallback if the first method failed
        try:
            from reset_leveling_settings import reset_leveling_settings
            await reset_leveling_settings()
            print("✅ Successfully reset leveling_settings table as fallback")
        except ImportError:
            print("⚠️ Could not import reset_leveling_settings module")
        except Exception as reset_error:
            print(f"⚠️ Warning: Fallback reset also failed: {reset_error}")

        # Even if the repair functions failed, attempt to create the table directly
        async with aiosqlite.connect("leveling.db") as db:
            try:
                print("Creating leveling_settings table directly as final fallback...")
                # Force create the table if it doesn't exist
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS leveling_settings (
                        setting_name TEXT PRIMARY KEY,
                        value INTEGER NOT NULL
                    )
                ''')
                await db.commit()
                print("✅ TABLE CREATE successful")
                
                # Check if the table has any data
                try:
                    cursor = await db.execute('SELECT COUNT(*) FROM leveling_settings')
                    count = await cursor.fetchone()
                    print(f"✅ COUNT query successful: {count}")
                    
                    if count is None or count[0] == 0:
                        # Table exists but is empty, insert default settings
                        print("Table exists but is empty, inserting default values...")
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
                        
                        for setting_name, value in default_settings:
                            await db.execute(
                                'INSERT INTO leveling_settings (setting_name, value) VALUES (?, ?)',
                                (setting_name, value)
                            )
                        
                        await db.commit()
                        print(f"✅ Created leveling_settings table and inserted default values")
                except Exception as count_error:
                    print(f"❌ Error checking table content: {count_error}")
                    # Handle the error by dropping and recreating the table
                    await db.execute("DROP TABLE IF EXISTS leveling_settings")
                    await db.execute('''
                        CREATE TABLE leveling_settings (
                            setting_name TEXT PRIMARY KEY,
                            value INTEGER NOT NULL
                        )
                    ''')
                    
                    # Insert default settings as fallback
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
                    
                    for setting_name, value in default_settings:
                        await db.execute(
                            'INSERT INTO leveling_settings (setting_name, value) VALUES (?, ?)',
                            (setting_name, value)
                        )
                    
                    await db.commit()
                    print(f"✅ Recreated leveling_settings table after error")
                
                # Now fetch the settings with extra error handling
                try:
                    cursor = await db.execute('SELECT setting_name, value FROM leveling_settings')
                    settings_list = await cursor.fetchall()
                    print(f"✅ SELECT query successful: {len(settings_list) if settings_list else 0} settings found")
                    
                    if not settings_list:
                        raise Exception("No settings found in the database")
                        
                    # Convert to dict and update global xp_settings
                    settings = dict(settings_list)
                    xp_settings = settings.copy()  # Update the global settings
                    print(f"✅ Loaded settings: {xp_settings}")
                except Exception as select_error:
                    print(f"❌ Error fetching settings: {select_error}")
                    # Use hardcoded defaults as fallback
                    settings = {
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
                    xp_settings = settings.copy()
                    print(f"⚠️ Using default settings due to database error: {xp_settings}")
            except Exception as db_error:
                print(f"❌ Database operation error: {db_error}")
                await interaction.followup.send(f"❌ Database error: {str(db_error)}. Using default settings.", ephemeral=True)
                
                # Use hardcoded defaults as fallback
                settings = {
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
                xp_settings = settings.copy()
                print(f"⚠️ Using default settings due to database error: {xp_settings}")
                    
    except Exception as e:
        error_msg = f"❌ Error accessing database: {str(e)}"
        print(f"Error in editleveling: {error_msg}")
        await interaction.followup.send(error_msg, ephemeral=True)
        
        # Use hardcoded defaults as last resort fallback
        settings = {
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
        xp_settings = settings.copy()
        print(f"⚠️ Using default settings due to outer exception: {xp_settings}")
        # Continue with the command using default settings
    
    embed = discord.Embed(
        title="⚙️ Leveling System Settings",
        description="Use the dropdown menu below to adjust the leveling system settings.",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Voice Chat Rewards", 
                   value=f"Active: {settings['voice_xp_per_minute']} XP and {settings['voice_coins_per_minute']} coins per minute\n"
                         f"AFK: {settings['afk_xp_per_minute']} XP and {settings['afk_coins_per_minute']} coins per minute",
                   inline=False)
    
    embed.add_field(name="Message Rewards",
                   value=f"XP per message: {settings['message_xp_min']}-{settings['message_xp_max']} XP",
                   inline=False)
    
    embed.add_field(name="Level Up",
                   value=f"Coins per level: {settings['level_up_coins']}\n"
                         f"Base XP per level: {settings['level_up_xp_base']}",
                   inline=False)
    
    # Save settings in a class attribute for accessibility
    class SettingData:
        current_settings = settings
    
    class SettingSelect(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="Voice XP Rate", value="voice_xp_per_minute", description="XP earned per minute in voice"),
                discord.SelectOption(label="Voice Coins Rate", value="voice_coins_per_minute", description="Coins earned per minute in voice"),
                discord.SelectOption(label="AFK XP Rate", value="afk_xp_per_minute", description="XP earned per minute while AFK"),
                discord.SelectOption(label="AFK Coins Rate", value="afk_coins_per_minute", description="Coins earned per minute while AFK"),
                discord.SelectOption(label="Level Up Coins", value="level_up_coins", description="Coins awarded on level up"),
                discord.SelectOption(label="Base XP Per Level", value="level_up_xp_base", description="Base XP needed per level"),
                discord.SelectOption(label="Min Message XP", value="message_xp_min", description="Minimum XP per message"),
                discord.SelectOption(label="Max Message XP", value="message_xp_max", description="Maximum XP per message")
            ]
            super().__init__(placeholder="Select setting to edit...", options=options)
            
        async def callback(self, interaction: discord.Interaction):
            setting = self.values[0]
            current_value = SettingData.current_settings.get(setting, 0)
            modal = EditValueModal(setting, current_value)
            await interaction.response.send_modal(modal)
    
    class EditValueModal(discord.ui.Modal):
        def __init__(self, setting: str, current_value: int):
            super().__init__(title=f"Edit {setting.replace('_', ' ').title()}")
            self.setting = setting
            self.value = discord.ui.TextInput(
                label="New Value",
                placeholder=f"Current value: {current_value}",
                default=str(current_value),
                required=True
            )
            self.add_item(self.value)
            
        async def on_submit(self, interaction: discord.Interaction):
            try:
                new_value = int(self.value.value)
                if new_value < 0:
                    raise ValueError("Value must be positive")
                
                # Import our settings manager
                from leveling_settings_manager import save_setting, load_settings, backup_database
                
                # Create a backup first for safety
                await backup_database()
                
                # Save the setting using our manager
                success = await save_setting(self.setting, new_value)
                if not success:
                    raise Exception(f"Failed to save setting {self.setting}")
                
                # Reload all settings to ensure consistency
                updated_settings = await load_settings()
                
                # Update both the global variable and the class attribute
                global xp_settings
                xp_settings.update(updated_settings)  # Update in place to ensure all references are updated
                SettingData.current_settings = updated_settings.copy()
                
                # Also update specific settings for backward compatibility
                if self.setting == "xp_min":
                    xp_config["min_xp"] = new_value
                elif self.setting == "xp_max":
                    xp_config["max_xp"] = new_value
                elif self.setting == "cooldown_seconds": 
                    xp_config["cooldown"] = new_value
                elif self.setting == "voice_xp_per_minute":
                    voice_rewards["xp_per_minute"] = new_value
                elif self.setting == "voice_coins_per_minute":
                    voice_rewards["coins_per_minute"] = new_value
                
                print(f"✅ Updated {self.setting} to {new_value}. New settings: {xp_settings}")
                
                # Create a new embed with updated settings
                updated_embed = discord.Embed(
                    title="⚙️ Leveling System Settings",
                    description="Use the dropdown menu below to adjust the leveling system settings.",
                    color=discord.Color.blue()
                )
                
                updated_embed.add_field(name="Voice Chat Rewards", 
                                 value=f"Active: {updated_settings['voice_xp_per_minute']} XP and {updated_settings['voice_coins_per_minute']} coins per minute\n"
                                       f"AFK: {updated_settings['afk_xp_per_minute']} XP and {updated_settings['afk_coins_per_minute']} coins per minute",
                                 inline=False)
                
                updated_embed.add_field(name="Message Rewards",
                                value=f"XP per message: {updated_settings['message_xp_min']}-{updated_settings['message_xp_max']} XP",
                                inline=False)
                
                updated_embed.add_field(name="Level Up",
                                value=f"Coins per level: {updated_settings['level_up_coins']}\n"
                                      f"Base XP per level: {updated_settings['level_up_xp_base']}",
                                inline=False)
                
                # Create new view
                new_view = SettingsView()
                
                # Send confirmation message
                await interaction.response.send_message(
                    f"✅ Successfully updated **{self.setting.replace('_', ' ').title()}** to **{new_value}**", 
                    ephemeral=True
                )
                
                # Send updated settings menu
                await interaction.followup.send(embed=updated_embed, view=new_view, ephemeral=True)
                
            except ValueError as e:
                await interaction.response.send_message(f"❌ Error: {str(e)}. Please enter a valid positive number!", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    class SettingsView(discord.ui.View):
        def __init__(self):
            super().__init__()
            self.add_item(SettingSelect())
    
    # Send the initial settings view
    await interaction.followup.send(embed=embed, view=SettingsView(), ephemeral=True)

@bot.tree.command(name="dbsync", description="Send database files to your DMs")
async def dbsync(interaction: discord.Interaction):
    """Send database files to the owner on demand"""
    await interaction.response.defer(ephemeral=True)
    
    # Only allow the bot owner to use this command
    if interaction.user.id != 1308527904497340467:
        await interaction.followup.send("❌ This command is only available to the bot owner.", ephemeral=True)
        return
    
    # Create a backup first to ensure it exists
    try:
        import shutil
        import os
        
        # Create backups directory if it doesn't exist
        os.makedirs("./backups", exist_ok=True)
        
        # Create a backup of the database with standard filename
        shutil.copy("leveling.db", "./backups/leveling_backup.db")
        print("✅ Created backup before sending files")
    except Exception as e:
        print(f"⚠️ Warning: Error creating backup before sync: {e}")
    
    # Send database files
    success = await send_database_to_user(interaction.user.id)
    
    if success:
        await interaction.followup.send("✅ Database files have been sent to your DMs!", ephemeral=True)
    else:
        await interaction.followup.send("❌ Failed to send database files. Please check that your DMs are open.", ephemeral=True)

@bot.tree.command(name="payvoicetime", description="Manually award voice time XP and coins to a user")
async def payvoicetime(interaction: discord.Interaction, member: discord.Member = None, hours: int = 0, minutes: int = 0):
    """Award XP and coins to a user as if they spent time in voice channels"""
    # Check permissions
    if not await check_permissions(interaction, "payvoicetime"):
        return
        
    # Validate inputs
    if not member:
        await interaction.response.send_message("❌ You must specify a member to award voice time to.", ephemeral=True)
        return
        
    if hours == 0 and minutes == 0:
        await interaction.response.send_message("❌ You must specify at least some time (hours or minutes).", ephemeral=True)
        return
        
    # Calculate total minutes
    total_minutes = (hours * 60) + minutes
    
    # Calculate rewards (1 coin and 2 XP per minute)
    coins_to_add = total_minutes  # 1 coin per minute
    xp_to_add = total_minutes * 2  # 2 XP per minute
    
    # Update user's record
    try:
        await interaction.response.defer(ephemeral=True)
        
        async with aiosqlite.connect("leveling.db") as db:
            # Check if user exists
            cursor = await db.execute('SELECT level, xp FROM users WHERE user_id = ?', (member.id,))
            user_data = await cursor.fetchone()
            
            if not user_data:
                # Create user if they don't exist
                await db.execute(
                    'INSERT INTO users (user_id, level, xp, coins) VALUES (?, ?, ?, ?)',
                    (member.id, 1, xp_to_add, coins_to_add)
                )
                await db.commit()
                
                await interaction.followup.send(
                    f"✅ Added {coins_to_add} coins and {xp_to_add} XP to {member.mention} for {hours}h {minutes}m of voice time.\n"
                    f"(Created new user record as they didn't exist in the database)",
                    ephemeral=True
                )
            else:
                # Update existing user
                await db.execute(
                    'UPDATE users SET coins = coins + ?, xp = xp + ? WHERE user_id = ?',
                    (coins_to_add, xp_to_add, member.id)
                )
                await db.commit()
                
                await interaction.followup.send(
                    f"✅ Added {coins_to_add} coins and {xp_to_add} XP to {member.mention} for {hours}h {minutes}m of voice time.",
                    ephemeral=True
                )
                
            # Try to notify the user via DM
            try:
                user = await bot.fetch_user(member.id)
                if user:
                    await user.send(
                        f"🎙️ You've been awarded {coins_to_add} coins and {xp_to_add} XP for {hours}h {minutes}m of voice time!"
                    )
            except Exception as e:
                print(f"Failed to send DM to {member.name}: {e}")
    
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)
        print(f"Error in payvoicetime command: {e}")

@bot.tree.command(name="removedq", description="Remove an existing daily quest")
async def removedq(interaction: discord.Interaction):
    # Check if there are any active quests to remove
    async with aiosqlite.connect("leveling.db") as db:
        cursor = await db.execute('''
            SELECT 
                rowid, 
                quest_type, 
                goal_amount, 
                xp_reward, 
                coin_reward,
                active 
            FROM daily_quests
        ''')
        quests = await cursor.fetchall()
    
    if not quests:
        await interaction.response.send_message("❌ There are no daily quests in the system.", ephemeral=True)
        return
    
    # Create an embed to show all quests
    embed = discord.Embed(
        title="📋 Remove Daily Quest",
        description="Select a quest to remove from the dropdown menu below.",
        color=discord.Color.red()
    )
    
    # Create a list of active and inactive quests for display
    active_quests = []
    inactive_quests = []
    
    for quest in quests:
        quest_id, quest_type, goal, xp, coins, active = quest
        status = "🟢 Active" if active else "🔴 Inactive"
        quest_details = f"**ID:** {quest_id} | **Type:** {quest_type.capitalize()} | **Goal:** {goal} | **Rewards:** {xp} XP, {coins} coins | **Status:** {status}"
        
        if active:
            active_quests.append(quest_details)
        else:
            inactive_quests.append(quest_details)
    
    # Add active quests to the embed
    if active_quests:
        embed.add_field(
            name="🟢 Active Quests",
            value="\n".join(active_quests),
            inline=False
        )
    
    # Add inactive quests to the embed
    if inactive_quests:
        embed.add_field(
            name="🔴 Inactive Quests",
            value="\n".join(inactive_quests),
            inline=False
        )
    
    # Create dropdown menu for quest removal
    class QuestRemovalView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.add_item(QuestSelector(quests))
    
    class QuestSelector(discord.ui.Select):
        def __init__(self, quests):
            options = []
            
            for quest in quests:
                quest_id, quest_type, goal, xp, coins, active = quest
                status = "🟢 Active" if active else "🔴 Inactive"
                option_label = f"ID: {quest_id} - {quest_type.capitalize()} Quest"
                option_desc = f"Goal: {goal}, Rewards: {xp} XP, {coins} coins, Status: {'Active' if active else 'Inactive'}"
                
                options.append(discord.SelectOption(
                    label=option_label,
                    description=option_desc,
                    value=str(quest_id),
                    emoji="🟢" if active else "🔴"
                ))
            
            super().__init__(
                placeholder="Select a quest to remove...",
                min_values=1,
                max_values=1,
                options=options
            )
        
        async def callback(self, interaction: discord.Interaction):
            quest_id = int(self.values[0])
            
            # Confirm removal
            confirm_view = ConfirmRemovalView(quest_id)
            
            # Find the quest details
            selected_quest = None
            for quest in quests:
                if quest[0] == quest_id:
                    selected_quest = quest
                    break
            
            if selected_quest:
                _, quest_type, goal, xp, coins, active = selected_quest
                status = "🟢 Active" if active else "🔴 Inactive"
                
                confirm_embed = discord.Embed(
                    title="❓ Confirm Quest Removal",
                    description=f"Are you sure you want to remove this quest?\n\n" +
                               f"**ID:** {quest_id}\n" +
                               f"**Type:** {quest_type.capitalize()}\n" +
                               f"**Goal:** {goal}\n" +
                               f"**Rewards:** {xp} XP, {coins} coins\n" +
                               f"**Status:** {status}",
                    color=discord.Color.yellow()
                )
                
                await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)
            else:
                await interaction.response.send_message("❌ Could not find the selected quest.", ephemeral=True)
    
    class ConfirmRemovalView(discord.ui.View):
        def __init__(self, quest_id):
            super().__init__(timeout=60)
            self.quest_id = quest_id
        
        @discord.ui.button(label="Confirm Removal", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            try:
                async with aiosqlite.connect("leveling.db") as db:
                    # First, deactivate the quest
                    await db.execute('''
                        UPDATE daily_quests 
                        SET active = 0 
                        WHERE rowid = ?
                    ''', (self.quest_id,))
                    
                    # Then, update any user progress for this quest
                    await db.execute('''
                        UPDATE user_quest_progress
                        SET completed = 1, claimed = 1
                        WHERE quest_id = ? AND completed = 0
                    ''', (self.quest_id,))
                    
                    await db.commit()
                
                success_embed = discord.Embed(
                    title="✅ Quest Removed",
                    description=f"The daily quest with ID {self.quest_id} has been successfully deactivated.\n\nAny user progress for this quest has been marked as completed and claimed.",
                    color=discord.Color.green()
                )
                
                await interaction.response.send_message(embed=success_embed, ephemeral=True)
            except Exception as e:
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"Failed to remove the quest: {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
        
        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("❌ Quest removal cancelled.", ephemeral=True)
    
    # Send the initial embed with the dropdown
    await interaction.response.send_message(embed=embed, view=QuestRemovalView(), ephemeral=True)


# Helper function for dailyquest command - works with natural language processing and slash commands
async def check_daily_quests(user_id, channel=None, user=None, interaction=None):
    """Process daily quest request from a user in a non-command way or slash command"""
    
    try:
        # Check if user has active quests
        async with aiosqlite.connect("leveling.db") as db:
            # Get all active quests from the system
            cursor = await db.execute('SELECT daily_quests.rowid, quest_type, goal_amount, xp_reward, coin_reward FROM daily_quests WHERE active = 1')
            active_quests = await cursor.fetchall()
            
            if not active_quests:
                if interaction:
                    await interaction.followup.send("❌ There are no active daily quests at the moment. Please check back later!", ephemeral=True)
                elif channel:
                    await channel.send(f"❌ <@{user_id}> There are no active daily quests at the moment. Please check back later!")
                return
        
            # Set expiration time for quests (24 hours from now)
            expires_at = (datetime.now() + timedelta(days=1)).timestamp()
            
            # Check which active quests the user doesn't have yet
            for quest in active_quests:
                quest_id = quest[0]
                
                # Check if user already has this quest
                cursor = await db.execute('''
                    SELECT user_id FROM user_quest_progress
                    WHERE user_id = ? AND quest_id = ? AND expires_at > ?
                ''', (user_id, quest_id, datetime.now().timestamp()))
                
                existing_quest = await cursor.fetchone()
                
                if not existing_quest:
                    # Assign new quest to user
                    await db.execute('''
                        INSERT INTO user_quest_progress 
                        (user_id, quest_id, current_progress, completed, claimed, expires_at)
                        VALUES (?, ?, 0, 0, 0, ?)
                    ''', (user_id, quest_id, expires_at))
            
            await db.commit()
            
            # Get user's quest progress
            cursor = await db.execute('''
                SELECT
                    q.rowid AS quest_id,
                    q.quest_type,
                    q.goal_amount,
                    q.xp_reward,
                    q.coin_reward,
                    p.current_progress,
                    p.completed,
                    p.claimed,
                    p.expires_at
                FROM
                    daily_quests AS q
                JOIN
                    user_quest_progress AS p ON q.rowid = p.quest_id
                WHERE
                    p.user_id = ? AND q.active = 1 AND p.expires_at > ?
            ''', (user_id, datetime.now().timestamp()))
            
            user_quests = await cursor.fetchall()
            
            if not user_quests:
                if interaction:
                    await interaction.followup.send("❌ There are no active daily quests at the moment. Please check back later!", ephemeral=True)
                elif channel:
                    await channel.send(f"❌ <@{user_id}> There are no active daily quests at the moment. Please check back later!")
                return
                
        # Create embed with quest information
    except Exception as e:
        print(f"Error in check_daily_quests: {e}")
        if interaction:
            await interaction.followup.send("❌ An error occurred while checking your daily quests. Please try again later.", ephemeral=True)
        elif channel:
            await channel.send(f"❌ <@{user_id}> An error occurred while checking your daily quests. Please try again later.")
        return
    embed = discord.Embed(
        title="📋 Your Daily Quests",
        description="Complete these quests to earn XP and coins!",
        color=discord.Color.blue()
    )
    
    all_completed = True
    all_claimed = True
    
    for quest in user_quests:
        quest_id, quest_type, goal, xp, coins, progress, completed, claimed, expires_at = quest
        
        # Format the quest type for display
        quest_name = {
            "voice": "Voice Activity",
            "chat": "Chat Messages",
            "reaction": "Reactions Added"
        }.get(quest_type, quest_type.capitalize())
        
        # Create progress bar (10 segments)
        progress_percent = min(progress / goal * 100, 100) if goal > 0 else 0
        progress_segments = int(progress_percent / 10)
        progress_bar = "▰" * progress_segments + "▱" * (10 - progress_segments)
        
        # Status indicators
        status = "✅ Completed" if completed else f"⏳ In Progress ({progress}/{goal})"
        if completed and claimed:
            status = "🏆 Claimed"
        
        # Update tracking flags
        if not completed:
            all_completed = False
        if not claimed and completed:
            all_claimed = False
        
        # Calculate time remaining
        expires_datetime = datetime.fromtimestamp(expires_at)
        time_remaining = expires_datetime - datetime.now()
        hours_remaining = int(time_remaining.total_seconds() / 3600)
        minutes_remaining = int((time_remaining.total_seconds() % 3600) / 60)
        
        # Format quest field
        field_value = (
            f"**Progress**: {progress}/{goal} {quest_type.capitalize()}\n"
            f"**Progress Bar**: {progress_bar} ({int(progress_percent)}%)\n"
            f"**Rewards**: {xp} XP, {coins} 🪙\n"
            f"**Status**: {status}\n"
            f"**Expires**: In {hours_remaining}h {minutes_remaining}m"
        )
        
        embed.add_field(
            name=f"{quest_name}",
            value=field_value,
            inline=False
        )
    
    # Add the claim button if there are completed but unclaimed quests
    if interaction:
        # When using the slash command, respond through the interaction
        if all_completed and not all_claimed:
            view = DailyQuestView(user_id)
            embed.add_field(
                name="✅ All Quests Completed!",
                value="Click the 'Claim Rewards' button below to claim your rewards!",
                inline=False
            )
            
            # Check if this is a DM - if so, don't use ephemeral messages
            is_dm = interaction.guild is None
            await interaction.followup.send(embed=embed, view=view, ephemeral=not is_dm)
        elif all_completed and all_claimed:
            embed.add_field(
                name="🏆 All Rewards Claimed!",
                value="You've completed all daily quests and claimed your rewards. Check back tomorrow for new quests!",
                inline=False
            )
            
            # Check if this is a DM - if so, don't use ephemeral messages
            is_dm = interaction.guild is None
            await interaction.followup.send(embed=embed, ephemeral=not is_dm)
        else:
            # No quests or quests in progress
            # Check if this is a DM - if so, don't use ephemeral messages
            is_dm = interaction.guild is None
            await interaction.followup.send(embed=embed, ephemeral=not is_dm)
    elif channel:
        # When using natural language, respond to the channel
        if all_completed and not all_claimed:
            view = DailyQuestView(user_id)
            embed.add_field(
                name="✅ All Quests Completed!",
                value="Click the 'Claim Rewards' button below to claim your rewards!",
                inline=False
            )
            await channel.send(content=f"<@{user_id}> Here are your daily quests:", embed=embed, view=view)
        elif all_completed and all_claimed:
            embed.add_field(
                name="🏆 All Rewards Claimed!",
                value="You've completed all daily quests and claimed your rewards. Check back tomorrow for new quests!",
                inline=False
            )
            await channel.send(content=f"<@{user_id}> Here are your daily quests:", embed=embed)
        else:
            # No quests or quests in progress
            await channel.send(content=f"<@{user_id}> Here are your daily quests:", embed=embed)


# Event listeners for tracking quest progress
# The on_message handler for chat quests is combined with the main one at the top of the file
# to prevent conflicts between multiple handlers

@bot.event
async def on_reaction_add(reaction, user):
    # Ignore bot reactions
    if user.bot:
        return
        
    # Get the current date/time
    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Use the database pool for more reliable access
    try:
        from db_pool import get_db_pool
        db_pool = await get_db_pool()
        
        # Track daily reaction count in server_stats 
        await db_pool.execute('''
            INSERT INTO server_stats (date, reaction_count, last_updated)
            VALUES (?, 1, ?)
            ON CONFLICT(date) DO UPDATE SET
            reaction_count = reaction_count + 1,
            last_updated = ?
        ''', (today, current_time, current_time))
        
        # Store individual user reaction data
        emoji_str = str(reaction.emoji)
        message_id = reaction.message.id
        
        # Store in user_reactions table for tracking
        await db_pool.execute('''
            INSERT INTO user_reactions (user_id, message_id, emoji, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user.id, message_id, emoji_str, current_time))
    except Exception as e:
        print(f"Error recording reaction data: {e}")
    
    # Process reaction for reaction quests
    try:
        # Use the database pool here too
        from db_pool import get_db_pool
        db_pool = await get_db_pool()
        
        # Check if the user has an active reaction quest
        cursor = await db_pool.execute('''
                SELECT
                    p.quest_id,
                    q.goal_amount,
                    p.current_progress,
                    p.completed
                FROM
                    user_quest_progress AS p
                JOIN
                    daily_quests AS q ON p.quest_id = q.rowid
                WHERE
                    p.user_id = ? AND q.quest_type = 'reaction' AND q.active = 1 
                    AND p.expires_at > ? AND p.completed = 0
            ''', (user.id, datetime.now().timestamp()))
        
        quest_data = await cursor.fetchone()
        
        if quest_data:
            quest_id, goal, current_progress, completed = quest_data
            
            # Update progress
            new_progress = current_progress + 1
            is_completed = new_progress >= goal
            
            await db_pool.execute('''
                UPDATE user_quest_progress
                SET current_progress = ?, completed = ?
                WHERE user_id = ? AND quest_id = ?
            ''', (new_progress, is_completed, user.id, quest_id))
                
            # Send notification when quest is completed
            if is_completed and not completed:
                try:
                    await user.send(
                        f"🎉 **Quest Completed!** You've completed your daily reaction quest! "
                        f"Use the /dailyquest command to view and claim your rewards."
                    )
                except:
                    # Can't DM the user, continue silently
                    pass
    except Exception as e:
        print(f"Error tracking reaction quest progress: {e}")


# Dictionary to store voice activity timestamps
voice_time_tracker = {}

# Function to load voice sessions from database on startup
async def load_voice_sessions():
    """Voice sessions functionality has been removed"""
    print("Voice sessions loading has been removed - this is just a placeholder function")
    return

# Voice channel integration has been removed
@bot.event
async def on_voice_state_update(member, before, after):
    """
    Voice state update handler for tracking time in voice channels and awarding XP and coins
    This will award 1 coin and 2 XP per minute in voice channels
    """
    
    # Previous voice channel functionality has been removed
    # Track voice channel join time for XP and coins (not for activity events)
    if after.channel and not before.channel:  # User joined VC
        current_time = datetime.now().timestamp()
        voice_join_times[member.id] = discord.utils.utcnow()
        # Also track for voice quest and XP
        voice_time_tracker[member.id] = current_time
        
        # Save to database for persistence across restarts
        try:
            async with aiosqlite.connect("leveling.db") as db:
                await db.execute('''
                    INSERT OR REPLACE INTO voice_sessions
                    (user_id, channel_id, guild_id, join_time)
                    VALUES (?, ?, ?, ?)
                ''', (member.id, after.channel.id, after.channel.guild.id, current_time))
                await db.commit()
                print(f"DEBUG: {member.name} joined voice channel at {datetime.now()} - Session saved to DB")
        except Exception as e:
            print(f"Error saving voice session to database: {e}")
    
    elif before.channel and not after.channel:  # User left VC
        print(f"DEBUG: {member.name} left voice channel at {datetime.now()}")
        # Calculate time spent and award rewards
        voice_time = None
        
        # Remove from database when they leave
        try:
            async with aiosqlite.connect("leveling.db") as db:
                await db.execute('''
                    DELETE FROM voice_sessions WHERE user_id = ?
                ''', (member.id,))
                await db.commit()
        except Exception as e:
            print(f"Error removing voice session from database: {e}")
        
        # Regular coin rewards for voice time (not activity coins)
        if member.id in voice_join_times:
            duration = (discord.utils.utcnow() - voice_join_times[member.id]).total_seconds()
            
            # Voice activity no longer awards activity coins
            try:
                # Award 1 coin per minute and 2 XP per minute
                voice_coins = int(duration // 60)  # 1 coin per minute
                voice_xp = int(duration // 60) * 2  # 2 XP per minute
                
                if voice_coins > 0 or voice_xp > 0:  # Only update if they earned at least something
                    async with aiosqlite.connect("leveling.db") as db:
                        # Update both XP and coins at once
                        await db.execute(
                            'UPDATE users SET coins = coins + ?, xp = xp + ? WHERE user_id = ?',
                            (voice_coins, voice_xp, member.id))
                        await db.commit()
                        print(f"Added {voice_coins} coins and {voice_xp} XP to {member.name} for {duration:.1f} seconds in voice channel")
                        
                        # Try to send a DM about the rewards
                        try:
                            user = await bot.fetch_user(member.id)
                            if user:
                                await user.send(f"🎙️ Thanks for being active in voice channels! You earned {voice_coins} coins and {voice_xp} XP for spending {int(duration // 60)} minutes in voice chat.")
                        except Exception as dm_error:
                            # Don't worry if DM fails
                            print(f"Failed to send voice rewards DM to {member.name}: {dm_error}")
            except Exception as e:
                print(f"Error in voice activity tracking: {e}")
            
            # Remove the join time regardless of event status
            del voice_join_times[member.id]
        
        # Now check voice time tracker for XP and coin rewards 
        if member.id in voice_time_tracker:
            try:
                join_time = voice_time_tracker.get(member.id)
                if join_time:
                    time_spent = datetime.now().timestamp() - join_time
                    minutes_spent = int(time_spent / 60)
                    
                    print(f"DEBUG: {member.name} spent {minutes_spent} minutes in voice (from {time_spent:.1f} seconds)")
                    
                    if minutes_spent > 0:
                        # Award XP and coins for voice activity (2 XP and 1 coin per minute)
                        xp_earned = minutes_spent * voice_rewards["xp_per_minute"]
                        coins_earned = minutes_spent * voice_rewards["coins_per_minute"]
                        
                        # No longer track voice activity for activity events - only count messages
                        activity_coins_earned = 0  # Always 0 to follow "1 message = 1 coin" rule
                        
                        async with aiosqlite.connect("leveling.db") as db:
                            # Get current user data
                            cursor = await db.execute('SELECT level, xp, coins, prestige FROM users WHERE user_id = ?', (member.id,))
                            user_data = await cursor.fetchone()
                            
                            if user_data:
                                level, xp, coins, prestige = user_data
                                
                                # Update XP and coins
                                new_xp = xp + xp_earned
                                new_coins = coins + coins_earned
                                
                                # Check for level up
                                xp_needed = calculate_xp_needed(level)
                                new_level = level
                                level_up_message = ""
                                levels_gained = 0
                                coins_for_leveling = 0
                                
                                # Get level up coins from database settings
                                level_up_coins = xp_settings.get("level_up_coins", 150)  # Default to 150 if not found
                                
                                while new_xp >= xp_needed:
                                    new_xp -= xp_needed
                                    new_level += 1
                                    levels_gained += 1
                                    coins_for_leveling += level_up_coins  # Add dynamic coins per level gained
                                    
                                    # Check for prestige (at level 101)
                                    if new_level == 101:
                                        new_level = 1
                                        prestige += 1
                                        level_up_message = f"🌟 **PRESTIGE UP!** 🌟\n{member.mention} advanced to Prestige {prestige}! (+{level_up_coins} 🪙)"
                                        
                                    # Update XP needed for next level
                                    xp_needed = calculate_xp_needed(new_level)
                                
                                # Add leveling coins to total coins
                                new_coins += coins_for_leveling
                                
                                # Update the database with all values
                                await db.execute(
                                    'UPDATE users SET level = ?, xp = ?, coins = ?, prestige = ?, activity_coins = activity_coins + ? WHERE user_id = ?',
                                    (new_level, new_xp, new_coins, prestige, activity_coins_earned, member.id)
                                )
                                
                                # Initialize level_channel variable
                                level_channel = None
                                
                                # Send level up message if needed
                                if new_level > level and not level_up_message:
                                    # Regular level up
                                    level_channel = bot.get_channel(1348430879363735602)  # Level up channel ID
                                    if level_channel:
                                        # Include coins awarded for leveling up in the message
                                        level_up_message = f"🎉 {member.mention} leveled up to level {new_level}! 🚀 (+{coins_for_leveling} 🪙)"
                                        
                                if level_up_message and level_channel:
                                    # Just send the message directly without animation
                                    await level_channel.send(level_up_message)
                                    
                            else:
                                # Create new user entry with activity coins
                                await db.execute(
                                    'INSERT INTO users (user_id, level, xp, coins, prestige, activity_coins) VALUES (?, ?, ?, ?, ?, ?)',
                                    (member.id, 1, xp_earned, coins_earned, 0, activity_coins_earned)
                                )
                            
                            # Update voice quest progress
                            cursor = await db.execute('''
                                SELECT
                                    p.quest_id,
                                    q.goal_amount,
                                    p.current_progress,
                                    p.completed
                                FROM
                                    user_quest_progress AS p
                                JOIN
                                    daily_quests AS q ON p.quest_id = q.rowid
                                WHERE
                                    p.user_id = ? AND q.quest_type = 'voice' AND q.active = 1 
                                    AND p.expires_at > ? AND p.completed = 0
                            ''', (member.id, datetime.now().timestamp()))
                            
                            quest_data = await cursor.fetchone()
                            
                            if quest_data:
                                quest_id, goal, current_progress, completed = quest_data
                                
                                # Update progress
                                new_progress = current_progress + minutes_spent
                                is_completed = new_progress >= goal
                                
                                # Cap progress at goal
                                if new_progress > goal:
                                    new_progress = goal
                                
                                await db.execute('''
                                    UPDATE user_quest_progress
                                    SET current_progress = ?, completed = ?
                                    WHERE user_id = ? AND quest_id = ?
                                ''', (new_progress, is_completed, member.id, quest_id))
                            
                            # Commit all changes
                            await db.commit()
                            
                            # Send notification about XP and coins earned if substantial amount
                            if minutes_spent >= 5:  # Only notify for 5+ minutes
                                try:
                                    # Add level up info to the DM message if applicable
                                    level_info = ""
                                    if levels_gained > 0:
                                        level_info = f"\n🎊 You've leveled up to level {new_level}! (+{coins_for_leveling} 🪙 for leveling up)"
                                    
                                    # DM the user
                                    await member.send(f"You earned {xp_earned} XP and {coins_earned} coins for spending {minutes_spent} minutes in voice channels! ({voice_rewards['xp_per_minute']} XP and {voice_rewards['coins_per_minute']} coin per minute){level_info}")
                                except Exception as e:
                                    # Failed to DM, ignore
                                    print(f"Failed to DM {member.name}: {e}")
                                
                                # Send notification when quest is completed
                                if is_completed and not completed:
                                    try:
                                        await member.send(
                                            f"🎉 **Quest Completed!** You've completed your daily voice quest! "
                                            f"Use the /dailyquest command to view and claim your rewards."
                                        )
                                    except:
                                        # Can't DM the user, continue silently
                                        pass
                
                # Clean up the tracker
                del voice_time_tracker[member.id]
                
            except Exception as e:
                print(f"Error tracking voice quest progress: {e}")
    
    # Handle moving between voice channels
    elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
        # User moved to a different voice channel, update the join time
        voice_time_tracker[member.id] = datetime.now().timestamp()
        print(f"DEBUG: {member.name} moved to a different voice channel at {datetime.now()}")


@bot.tree.command(name="serverstats", description="View server message and user activity statistics")
async def serverstats(interaction: discord.Interaction):
    today = datetime.now().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    async with aiosqlite.connect("leveling.db") as db:
        # Get today's message count from message_log for persistence across bot restarts
        cursor = await db.execute('''
            SELECT COUNT(*) 
            FROM message_log 
            WHERE DATE(timestamp) = DATE('now')
        ''')
        today_message_count = await cursor.fetchone()
        today_message_count = today_message_count[0] if today_message_count else 0
        
        # Get today's reaction count from server_stats
        cursor = await db.execute('SELECT reaction_count, last_updated FROM server_stats WHERE date = ?', (today,))
        reaction_stats = await cursor.fetchone()
        
        if not reaction_stats:
            reaction_count = 0
            last_updated = None
        else:
            reaction_count = reaction_stats[0]
            last_updated = reaction_stats[1]
        
        # Get total server statistics (all time)
        cursor = await db.execute('SELECT COUNT(*) FROM message_log')
        total_messages = await cursor.fetchone()
        total_messages = total_messages[0] if total_messages else 0
        
        cursor = await db.execute('SELECT SUM(reaction_count) FROM server_stats')
        total_reactions = await cursor.fetchone()
        total_reactions = total_reactions[0] if total_reactions and total_reactions[0] is not None else 0
        
        # Get user count statistics
        cursor = await db.execute('SELECT COUNT(*) FROM users')
        user_count = await cursor.fetchone()
        user_count = user_count[0] if user_count else 0
        
        # Get active users (users who sent at least one message today)
        cursor = await db.execute('''
            SELECT COUNT(DISTINCT user_id) 
            FROM message_log 
            WHERE DATE(timestamp) = DATE('now')
        ''')
        active_users = await cursor.fetchone()
        active_users = active_users[0] if active_users else 0
        
        # Get message statistics by hour for today
        cursor = await db.execute('''
            SELECT strftime('%H', timestamp) as hour, COUNT(*) 
            FROM message_log 
            WHERE DATE(timestamp) = DATE('now') 
            GROUP BY hour 
            ORDER BY hour
        ''')
        hourly_stats = await cursor.fetchall()
        
        # Calculate most active hour
        most_active_hour = max(hourly_stats, key=lambda x: x[1]) if hourly_stats else (None, 0)
        
        # Get the most recent update time
        cursor = await db.execute('''
            SELECT MAX(timestamp) 
            FROM message_log
        ''')
        most_recent = await cursor.fetchone()
        most_recent_timestamp = most_recent[0] if most_recent and most_recent[0] else None
            
    # Format the last updated time and calculate time since last update
    if most_recent_timestamp:
        last_updated_text = most_recent_timestamp
        try:
            last_updated_time = datetime.strptime(most_recent_timestamp, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            diff = now - last_updated_time
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if diff.days > 0:
                time_since_update = f" ({diff.days}d {hours}h {minutes}m ago)"
            elif hours > 0:
                time_since_update = f" ({hours}h {minutes}m ago)"
            elif minutes > 0:
                time_since_update = f" ({minutes}m {seconds}s ago)"
            else:
                time_since_update = f" ({seconds}s ago)"
        except Exception as e:
            print(f"Error calculating time difference: {e}")
            time_since_update = ""
    else:
        last_updated_text = "Never updated"
        time_since_update = ""
    
    embed = discord.Embed(
        title="📊 Server Statistics Dashboard",
        description=f"**Stats for {today}**\n📝 Last updated: {last_updated_text}{time_since_update}\n⏰ Current time: {current_time}",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    # Today's stats
    embed.add_field(name="📝 Today's Messages", value=f"{today_message_count:,}", inline=True)
    embed.add_field(name="💫 Today's Reactions", value=f"{reaction_count:,}", inline=True)
    embed.add_field(name="👥 Active Users Today", value=f"{active_users:,}", inline=True)
    
    # All-time stats
    embed.add_field(name="📜 Total Messages", value=f"{total_messages:,}", inline=True)
    embed.add_field(name="✨ Total Reactions", value=f"{total_reactions:,}", inline=True)
    embed.add_field(name="👤 Registered Users", value=f"{user_count:,}", inline=True)
    
    # Activity pattern
    if most_active_hour[0] is not None:
        hour_int = int(most_active_hour[0])
        hour_format = f"{hour_int}:00-{hour_int+1}:00"
        embed.add_field(name="⏰ Most Active Hour", value=f"{hour_format} ({most_active_hour[1]} messages)", inline=False)
    
    # Add footer with instructions
    embed.set_footer(text="Stats are persistent across bot restarts • Use /resetstats to reset today's stats")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="resetstats", description="Reset today's server stats")
async def resetstats(interaction: discord.Interaction):
    # Only allow staff to reset stats
    allowed_roles = [1338482857974169683]  # Staff role
    if not (any(role.id in allowed_roles for role in interaction.user.roles) or interaction.user.id == 1308527904497340467):
        await interaction.response.send_message("❌ Only Staff can reset server stats!", ephemeral=True)
        return
        
    today = datetime.now().strftime("%Y-%m-%d")
    today_start = f"{today} 00:00:00"
    today_end = f"{today} 23:59:59"
    
    async with aiosqlite.connect("leveling.db") as db:
        # Delete today's message logs for complete reset
        await db.execute('''
            DELETE FROM message_log
            WHERE timestamp BETWEEN ? AND ?
        ''', (today_start, today_end))
        
        # Also reset server_stats for consistency
        await db.execute('DELETE FROM server_stats WHERE date = ?', (today,))
        await db.commit()
        
    await interaction.response.send_message("✅ Today's server stats have been reset! Message logs and reaction counts for today have been cleared.", ephemeral=True)


@bot.tree.command(name="useractivity", description="Check a user's activity statistics (messages and reactions)")
async def useractivity(interaction: discord.Interaction, member: discord.Member = None):
    """View detailed activity statistics for a user"""
    # If member is not provided, default to the user who ran the command
    if member is None:
        member = interaction.user
    
    try:
        # Get the database connection pool
        from db_pool import get_db_pool
        db_pool = await get_db_pool()
        
        # Format current time for display
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get message count (total and recent)
        cursor = await db_pool.execute('''
            SELECT COUNT(*) 
            FROM message_log 
            WHERE user_id = ?
        ''', (member.id,))
        total_messages = await cursor.fetchone()
        total_messages = total_messages[0] if total_messages else 0
        
        # Get recent messages (last 7 days)
        cursor = await db_pool.execute('''
            SELECT COUNT(*) 
            FROM message_log 
            WHERE user_id = ? AND timestamp > datetime('now', '-7 days')
        ''', (member.id,))
        recent_messages = await cursor.fetchone()
        recent_messages = recent_messages[0] if recent_messages else 0
        
        # Get last message time
        cursor = await db_pool.execute('''
            SELECT MAX(timestamp)
            FROM message_log
            WHERE user_id = ?
        ''', (member.id,))
        last_message_time = await cursor.fetchone()
        
        # Format last message time more nicely
        if last_message_time and last_message_time[0]:
            # Parse the timestamp from database
            timestamp = datetime.fromisoformat(last_message_time[0].replace('Z', '+00:00'))
            
            # Calculate time difference
            time_diff = datetime.now() - timestamp
            
            if time_diff.days > 0:
                last_active = f"{time_diff.days} days ago"
            elif time_diff.seconds // 3600 > 0:
                last_active = f"{time_diff.seconds // 3600} hours ago"
            elif time_diff.seconds // 60 > 0:
                last_active = f"{time_diff.seconds // 60} minutes ago"
            else:
                last_active = f"{time_diff.seconds} seconds ago"
        else:
            last_active = "No messages found"
        
        # Get reaction count
        cursor = await db_pool.execute('''
            SELECT COUNT(*) 
            FROM user_reactions 
            WHERE user_id = ?
        ''', (member.id,))
        total_reactions = await cursor.fetchone()
        total_reactions = total_reactions[0] if total_reactions else 0
        
        # Get recent reactions (last 7 days)
        cursor = await db_pool.execute('''
            SELECT COUNT(*) 
            FROM user_reactions 
            WHERE user_id = ? AND timestamp > datetime('now', '-7 days')
        ''', (member.id,))
        recent_reactions = await cursor.fetchone()
        recent_reactions = recent_reactions[0] if recent_reactions else 0
        
        # Get last reaction time
        cursor = await db_pool.execute('''
            SELECT MAX(timestamp)
            FROM user_reactions
            WHERE user_id = ?
        ''', (member.id,))
        last_reaction_time = await cursor.fetchone()
        last_reaction = "No reactions found" if not last_reaction_time or not last_reaction_time[0] else last_reaction_time[0]
        
        # Voice channel functionality has been removed
        
        # Get user's level information
        cursor = await db_pool.execute('''
            SELECT level, xp, prestige, coins, activity_coins
            FROM users
            WHERE user_id = ?
        ''', (member.id,))
        user_data = await cursor.fetchone()
        
        if user_data:
            level, xp, prestige, coins, activity_coins = user_data
        else:
            level, xp, prestige, coins, activity_coins = 0, 0, 0, 0, 0
        
        # Create an embed with all the information
        embed = discord.Embed(
            title=f"Activity Statistics for {member.display_name}",
            description=f"Detailed activity metrics for {member.mention}",
            color=discord.Color.blue()
        )
        
        # Level and XP section
        prestige_str = f"Prestige {prestige} " if prestige > 0 else ""
        embed.add_field(
            name="Level Progress",
            value=f"**{prestige_str}Level:** {level}\n**XP:** {xp}/{calculate_xp_needed(level)}\n**Coins:** {coins}",
            inline=False
        )
        
        # Message statistics
        embed.add_field(
            name="Message Activity",
            value=f"**Total Messages:** {total_messages}\n**Last 7 Days:** {recent_messages}\n**Last Active:** {last_active}",
            inline=True
        )
        
        # Reaction statistics
        embed.add_field(
            name="Reaction Activity",
            value=f"**Total Reactions:** {total_reactions}\n**Last 7 Days:** {recent_reactions}",
            inline=True
        )
        
        # Voice channel section has been removed
        
        # Add footer with timestamp
        embed.set_footer(text=f"Data as of {current_time}")
        
        # Set user avatar as thumbnail
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        print(f"Error in useractivity command: {e}")
        await interaction.response.send_message(f"❌ An error occurred while fetching activity data: {e}", ephemeral=True)


# /invites command has been removed


# /inviteleaderboard command has been removed


# /allinvites command has been removed

async def get_user_name_from_db(user_id):
    """Get a user's name from the database (previously used invite tracking, now modified)"""
    try:
        # Use our connection pool for better reliability
        from db_pool import get_db_pool
        db_pool = await get_db_pool()
        
        # Try to get user information from the users table if it exists
        user_record = await db_pool.fetchone('''
            SELECT user_id
            FROM users
            WHERE user_id = ?
            LIMIT 1
        ''', (user_id,))
        
        if user_record:
            # Try to fetch user from Discord API
            try:
                user = await bot.fetch_user(user_id)
                return user.name
            except:
                pass
        
        # Fall back to generic ID if nothing found
        return f"User {user_id}"
        
    except Exception as e:
        print(f"Error getting user name from DB: {e}")
        return f"User {user_id}"


# /inviteinfo command has been removed


# /setinvites command has been removed

# /inviterewardlogs command has been removed


# Moderation Panel Functions
async def send_moderation_panel():
    """
    Create and send a moderation panel to the designated channel.
    This panel will allow users to easily access moderation commands.
    """
    # Use the global channel ID for moderation panel
    # This channel was set at the top of the file
    
    # Get the channel
    channel = bot.get_channel(MODERATION_PANEL_CHANNEL)
    if not channel:
        try:
            channel = await bot.fetch_channel(MODERATION_PANEL_CHANNEL)
        except:
            print(f"❌ Could not find moderation panel channel with ID {MODERATION_PANEL_CHANNEL}")
            return
    
    # Delete existing messages in the channel (clear old panels)
    async for message in channel.history(limit=10):
        try:
            await message.delete()
        except:
            pass
    
    # Create the moderation panel embed
    embed = discord.Embed(
        title="🛡️ The Grid Moderation Panel",
        description="Use the buttons below to moderate server members. Anyone can use these commands!\n\n"
                    "**Available Actions:**\n"
                    "• **Kick** - Remove a user from the server (they can rejoin)\n"
                    "• **Ban** - Permanently remove a user from the server\n"
                    "• **Unban** - Remove a ban on a user\n"
                    "• **Mute** - Temporarily prevent a user from sending messages\n"
                    "• **Unmute** - Remove a mute from a user\n"
                    "• **Warn** - Give a user a warning\n"
                    "• **Check Warnings** - View a user's warnings",
        color=discord.Color.blue()
    )
    
    embed.set_footer(text="These moderation commands are available to all members")
    
    # Create the view with buttons for each moderation action
    view = ModerationPanelView()
    
    # Send the panel to the channel
    await channel.send(embed=embed, view=view)
    print(f"✅ Moderation panel sent to channel ID: {MODERATION_PANEL_CHANNEL}")

# Moderation Panel UI Components
class ModerationPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Set timeout to None to make the buttons persistent
    
    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, custom_id="mod_panel:kick", emoji="👢")
    async def kick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(KickModal())
    
    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, custom_id="mod_panel:ban", emoji="🔨")
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BanModal())
    
    @discord.ui.button(label="Unban", style=discord.ButtonStyle.primary, custom_id="mod_panel:unban", emoji="🔓")
    async def unban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UnbanModal())
    
    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, custom_id="mod_panel:mute", emoji="🔇")
    async def mute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MuteModal())
    
    @discord.ui.button(label="Unmute", style=discord.ButtonStyle.secondary, custom_id="mod_panel:unmute", emoji="🔊")
    async def unmute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(UnmuteModal())
    
    @discord.ui.button(label="Warn", style=discord.ButtonStyle.primary, custom_id="mod_panel:warn", emoji="⚠️")
    async def warn_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WarnModal())
    
    @discord.ui.button(label="Check Warnings", style=discord.ButtonStyle.primary, custom_id="mod_panel:check_warnings", emoji="📋")
    async def check_warnings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CheckWarningsModal())

class KickModal(discord.ui.Modal, title="Kick Member"):
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user ID to kick",
        required=True
    )
    
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Enter the reason for kicking",
        required=False,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get the member
            try:
                member = await interaction.guild.fetch_member(int(self.user_id.value))
            except:
                await interaction.followup.send("❌ Could not find member with that ID. Make sure the ID is correct.", ephemeral=True)
                return
            
            # Kick the member
            try:
                await member.kick(reason=self.reason.value or "No reason provided")
                
                # Send confirmation
                embed = discord.Embed(
                    title="👢 User Kicked",
                    description=f"{member.mention} has been kicked.\nReason: {self.reason.value or 'No reason provided'}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # Send to mod logs
                mod_channel = interaction.client.get_channel(MOD_LOGS_CHANNEL)
                if mod_channel:
                    log_embed = discord.Embed(
                        title="Moderation Log - Kick",
                        description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {self.reason.value or 'No reason provided'}",
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow()
                    )
                    await mod_channel.send(embed=log_embed)
            except Exception as e:
                await interaction.followup.send(f"❌ Failed to kick user: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

class BanModal(discord.ui.Modal, title="Ban Member"):
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user ID to ban",
        required=True
    )
    
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Enter the reason for banning",
        required=False,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get the member
            try:
                member = await interaction.guild.fetch_member(int(self.user_id.value))
            except:
                await interaction.followup.send("❌ Could not find member with that ID. Make sure the ID is correct.", ephemeral=True)
                return
            
            # Ban the member
            try:
                await member.ban(reason=self.reason.value or "No reason provided")
                
                # Send confirmation
                embed = discord.Embed(
                    title="🔨 User Banned",
                    description=f"{member.mention} has been banned.\nReason: {self.reason.value or 'No reason provided'}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # Send to mod logs
                mod_channel = interaction.client.get_channel(MOD_LOGS_CHANNEL)
                if mod_channel:
                    log_embed = discord.Embed(
                        title="Moderation Log - Ban",
                        description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {self.reason.value or 'No reason provided'}",
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow()
                    )
                    await mod_channel.send(embed=log_embed)
            except Exception as e:
                await interaction.followup.send(f"❌ Failed to ban user: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

class UnbanModal(discord.ui.Modal, title="Unban User"):
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user ID to unban",
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get the user
            try:
                user = await interaction.client.fetch_user(int(self.user_id.value))
            except:
                await interaction.followup.send("❌ Could not find user with that ID. Make sure the ID is correct.", ephemeral=True)
                return
            
            # Unban the user
            try:
                await interaction.guild.unban(user)
                
                # Send confirmation
                embed = discord.Embed(
                    title="🔓 User Unbanned",
                    description=f"{user.mention} has been unbanned.",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # Send to mod logs
                mod_channel = interaction.client.get_channel(MOD_LOGS_CHANNEL)
                if mod_channel:
                    log_embed = discord.Embed(
                        title="Moderation Log - Unban",
                        description=f"**User:** {user.mention}\n**Moderator:** {interaction.user.mention}",
                        color=discord.Color.green(),
                        timestamp=discord.utils.utcnow()
                    )
                    await mod_channel.send(embed=log_embed)
            except Exception as e:
                await interaction.followup.send(f"❌ Failed to unban user: {str(e)}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

class MuteModal(discord.ui.Modal, title="Mute Member"):
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user ID to mute",
        required=True
    )
    
    duration = discord.ui.TextInput(
        label="Duration",
        placeholder="Duration format: number + unit (s/m/h/d) e.g. 10m for 10 minutes",
        required=True
    )
    
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Enter the reason for muting",
        required=False,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get the member
            try:
                member = await interaction.guild.fetch_member(int(self.user_id.value))
            except:
                await interaction.followup.send("❌ Could not find member with that ID. Make sure the ID is correct.", ephemeral=True)
                return
            
            # Validate the duration format
            if not self.duration.value or len(self.duration.value) < 2:
                await interaction.followup.send("❌ Invalid duration format! Use a number followed by s/m/h/d (e.g., 10m)", ephemeral=True)
                return
                
            # Get the time unit (last character) and time value (everything else)
            time_unit = self.duration.value[-1].lower()
            
            # Make sure time value is numeric
            try:
                time_value = int(self.duration.value[:-1])
            except ValueError:
                await interaction.followup.send("❌ Invalid duration format! Time value must be a number.", ephemeral=True)
                return
                
            # Define conversion factors to seconds
            time_dict = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}

            # Validate the time unit
            if time_unit not in time_dict:
                await interaction.followup.send("❌ Invalid time unit! Use s (seconds), m (minutes), h (hours), or d (days)", ephemeral=True)
                return
                
            # Check if duration is too long (Discord max is 28 days)
            seconds = time_value * time_dict[time_unit]
            if seconds > 2419200:  # 28 days in seconds
                await interaction.followup.send("❌ Timeout duration too long! Maximum is 28 days.", ephemeral=True)
                return
            
            # Calculate timeout duration
            timeout_until = discord.utils.utcnow() + timedelta(seconds=seconds)
            
            # Apply the timeout
            await member.timeout(timeout_until, reason=self.reason.value or "No reason provided")
            
            # Format a user-friendly duration string
            duration_str = self.duration.value
            if time_unit == 's':
                duration_str = f"{time_value} second{'s' if time_value != 1 else ''}"
            elif time_unit == 'm':
                duration_str = f"{time_value} minute{'s' if time_value != 1 else ''}"
            elif time_unit == 'h':
                duration_str = f"{time_value} hour{'s' if time_value != 1 else ''}"
            elif time_unit == 'd':
                duration_str = f"{time_value} day{'s' if time_value != 1 else ''}"
                
            # Create success embed
            embed = discord.Embed(
                title="🔇 User Muted", 
                description=f"{member.mention} has been muted for {duration_str}.\nReason: {self.reason.value or 'No reason provided'}", 
                color=discord.Color.red()
            )
            embed.set_footer(text=f"Timeout will expire at: {timeout_until.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            await interaction.followup.send(embed=embed, ephemeral=True)

            # Send mod log
            mod_channel = interaction.client.get_channel(MOD_LOGS_CHANNEL)
            if mod_channel:
                log_embed = discord.Embed(
                    title="Moderation Log - Mute",
                    description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Duration:** {duration_str}\n**Reason:** {self.reason.value or 'No reason provided'}\n**Expires:** {timeout_until.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                await mod_channel.send(embed=log_embed)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

class UnmuteModal(discord.ui.Modal, title="Unmute Member"):
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user ID to unmute",
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get the member
            try:
                member = await interaction.guild.fetch_member(int(self.user_id.value))
            except:
                await interaction.followup.send("❌ Could not find member with that ID. Make sure the ID is correct.", ephemeral=True)
                return
            
            # Check if the member is actually muted
            if not member.is_timed_out():
                await interaction.followup.send(f"ℹ️ {member.mention} is not currently muted/timed out.", ephemeral=True)
                return
                
            # Remove the timeout
            await member.timeout(None)
            
            # Create success embed
            embed = discord.Embed(
                title="🔊 User Unmuted", 
                description=f"{member.mention} has been unmuted.", 
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            # Send mod log
            mod_channel = interaction.client.get_channel(MOD_LOGS_CHANNEL)
            if mod_channel:
                log_embed = discord.Embed(
                    title="Moderation Log - Unmute",
                    description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow()
                )
                await mod_channel.send(embed=log_embed)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

class WarnModal(discord.ui.Modal, title="Warn Member"):
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user ID to warn",
        required=True
    )
    
    reason = discord.ui.TextInput(
        label="Reason",
        placeholder="Enter the reason for warning",
        required=True,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get the member
            try:
                member = await interaction.guild.fetch_member(int(self.user_id.value))
            except:
                await interaction.followup.send("❌ Could not find member with that ID. Make sure the ID is correct.", ephemeral=True)
                return
                
            # Add warning
            if member.id not in warnings_db:
                warnings_db[member.id] = []
            
            warnings_db[member.id].append(self.reason.value)
            
            # Send confirmation
            embed = discord.Embed(
                title="⚠️ Warning Added", 
                description=f"{member.mention} has been warned.\nReason: {self.reason.value}\nTotal Warnings: {len(warnings_db[member.id])}", 
                color=discord.Color.yellow()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            # Send mod log
            mod_channel = interaction.client.get_channel(MOD_LOGS_CHANNEL)
            if mod_channel:
                log_embed = discord.Embed(
                    title="Moderation Log - Warning",
                    description=f"**User:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {self.reason.value}\n**Total Warnings:** {len(warnings_db[member.id])}",
                    color=discord.Color.yellow(),
                    timestamp=discord.utils.utcnow()
                )
                await mod_channel.send(embed=log_embed)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

class CheckWarningsModal(discord.ui.Modal, title="Check Member Warnings"):
    user_id = discord.ui.TextInput(
        label="User ID",
        placeholder="Enter the user ID to check warnings",
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Get the member
            try:
                member = await interaction.guild.fetch_member(int(self.user_id.value))
            except:
                await interaction.followup.send("❌ Could not find member with that ID. Make sure the ID is correct.", ephemeral=True)
                return
            
            # Check warnings
            if member.id not in warnings_db or not warnings_db[member.id]:
                await interaction.followup.send(f"{member.mention} has no warnings.", ephemeral=True)
                return
            
            # Create warnings list
            warnings_list = "\n".join([f"{i+1}. {w}" for i, w in enumerate(warnings_db[member.id])])
            
            # Send warnings
            embed = discord.Embed(
                title="⚠️ User Warnings", 
                description=f"Warnings for {member.mention}:\n{warnings_list}", 
                color=discord.Color.yellow()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

# Countdown command
@bot.tree.command(name="countdown", description="Start a countdown timer that will send messages at specified intervals")
async def countdown(
    interaction: discord.Interaction,
    duration: int,
    time_unit: str,
    interval: str,
    channel: discord.TextChannel = None
):
    """
    Start a countdown timer that sends messages at specified intervals.
    
    Parameters:
    - duration: The total duration for the countdown
    - time_unit: Unit for the duration (min/hour/day)
    - interval: How often to send updates (format: 30m, 1h, 2d)
    - channel: The channel to send countdown messages to (default: current channel)
    
    Examples:
    /countdown 60 min 10m #announcements
    /countdown 24 hour 1h #general
    /countdown 7 day 1d #events
    """
    # Only allow two specific users to use this command
    if interaction.user.id not in [1308527904497340467, 479711321399623681]:
        await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        return
    
    # Set the channel to current channel if not specified
    if channel is None:
        channel = interaction.channel
    
    # Validate time units
    valid_units = {
        "min": 60,
        "hour": 3600,
        "day": 86400
    }
    
    # Convert duration to seconds
    if time_unit.lower() not in valid_units:
        await interaction.response.send_message(
            f"❌ Invalid time unit! Please use one of: {', '.join(valid_units.keys())}", 
            ephemeral=True
        )
        return
    
    total_seconds = duration * valid_units[time_unit.lower()]
    
    # Parse interval (e.g., "30m", "1h", "12h", "1d")
    interval_value = ""
    interval_unit = ""
    for char in interval:
        if char.isdigit():
            interval_value += char
        else:
            interval_unit += char
    
    # Validate interval format
    if not interval_value or not interval_unit:
        await interaction.response.send_message(
            "❌ Invalid interval format! Use format like 30m, 1h, or 1d.", 
            ephemeral=True
        )
        return
    
    # Map interval unit to seconds
    interval_unit = interval_unit.lower()
    interval_unit_mapping = {
        "m": 60,
        "min": 60,
        "h": 3600,
        "hour": 3600,
        "d": 86400,
        "day": 86400
    }
    
    if interval_unit not in interval_unit_mapping:
        await interaction.response.send_message(
            f"❌ Invalid interval unit! Please use one of: m, h, d", 
            ephemeral=True
        )
        return
    
    # Calculate interval in seconds
    interval_seconds = int(interval_value) * interval_unit_mapping[interval_unit]
    
    # Ensure interval isn't larger than total countdown
    if interval_seconds > total_seconds:
        await interaction.response.send_message(
            "❌ Interval cannot be larger than the total countdown duration!", 
            ephemeral=True
        )
        return
    
    # Create a unique ID for this countdown
    countdown_id = f"{interaction.user.id}_{int(time.time())}"
    
    # Calculate end time
    end_time = discord.utils.utcnow() + timedelta(seconds=total_seconds)
    
    # Store countdown info
    active_countdowns[countdown_id] = {
        "channel_id": channel.id,
        "end_time": end_time,
        "interval": interval_seconds,
        "last_message": discord.utils.utcnow(),
        "total_seconds": total_seconds
    }
    
    # Create confirmation embed
    embed = discord.Embed(
        title="⏰ Countdown Timer Started",
        description=f"Countdown for {duration} {time_unit}(s) has been started!",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="⏱️ Duration",
        value=f"{duration} {time_unit}(s) ({total_seconds} seconds)"
    )
    
    embed.add_field(
        name="🔄 Update Interval",
        value=f"Every {interval} ({interval_seconds} seconds)"
    )
    
    embed.add_field(
        name="🏁 End Time",
        value=f"<t:{int(end_time.timestamp())}:F> (<t:{int(end_time.timestamp())}:R>)"
    )
    
    embed.add_field(
        name="📢 Channel",
        value=channel.mention,
        inline=False
    )
    
    # Send confirmation
    await interaction.response.send_message(embed=embed)
    
    # Send initial countdown message to the target channel
    remaining = total_seconds
    days, remainder = divmod(remaining, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    time_parts = []
    if days > 0:
        time_parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        time_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        time_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 and not (days > 0 or hours > 0 or minutes > 0):
        time_parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    time_str = ", ".join(time_parts)
    
    initial_embed = discord.Embed(
        title="⏰ Countdown Started",
        description=f"Time remaining: **{time_str}**",
        color=discord.Color.gold()
    )
    
    initial_embed.add_field(
        name="⏱️ Ends At",
        value=f"<t:{int(end_time.timestamp())}:F> (<t:{int(end_time.timestamp())}:R>)"
    )
    
    # Send initial message
    countdown_msg = await channel.send(embed=initial_embed)
    
    # Start countdown task
    async def countdown_task():
        try:
            # Continue until countdown is done
            while discord.utils.utcnow() < end_time:
                # Wait for the next interval
                await asyncio.sleep(interval_seconds)
                
                # Get remaining time
                remaining = (end_time - discord.utils.utcnow()).total_seconds()
                if remaining <= 0:
                    break
                
                # Calculate time components
                days, remainder = divmod(int(remaining), 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                time_parts = []
                if days > 0:
                    time_parts.append(f"{days} day{'s' if days != 1 else ''}")
                if hours > 0:
                    time_parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
                if minutes > 0:
                    time_parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
                if seconds > 0 and not (days > 0 or hours > 0 or minutes > 0):
                    time_parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
                
                time_str = ", ".join(time_parts)
                
                # Create update embed
                update_embed = discord.Embed(
                    title="⏰ Countdown Update",
                    description=f"Time remaining: **{time_str}**",
                    color=discord.Color.gold()
                )
                
                update_embed.add_field(
                    name="⏱️ Ends At",
                    value=f"<t:{int(end_time.timestamp())}:F> (<t:{int(end_time.timestamp())}:R>)"
                )
                
                # Send update
                try:
                    target_channel = bot.get_channel(channel.id)
                    if target_channel:
                        await target_channel.send(embed=update_embed)
                except Exception as e:
                    print(f"Error sending countdown update: {e}")
            
            # Final message
            try:
                final_embed = discord.Embed(
                    title="⏰ Countdown Finished!",
                    description="The countdown has ended!",
                    color=discord.Color.green()
                )
                
                target_channel = bot.get_channel(channel.id)
                if target_channel:
                    await target_channel.send(embed=final_embed)
            except Exception as e:
                print(f"Error sending final countdown message: {e}")
                
            # Remove countdown from active countdowns
            if countdown_id in active_countdowns:
                del active_countdowns[countdown_id]
                
        except asyncio.CancelledError:
            # Handle cancellation
            if countdown_id in active_countdowns:
                del active_countdowns[countdown_id]
            print(f"Countdown {countdown_id} cancelled")
        except Exception as e:
            print(f"Error in countdown task: {e}")
            # Clean up on error
            if countdown_id in active_countdowns:
                del active_countdowns[countdown_id]
    
    # Start the countdown task
    bot.loop.create_task(countdown_task())

# Status command to control bot status messages
@bot.tree.command(name="status", description="Send a status message or update the bot status")
@app_commands.describe(
    status_type="The type of status message to send (on, off, maintenance)",
    update_persistent="Whether to update the persistent bot status message (default: False)"
)
@app_commands.choices(status_type=[
    app_commands.Choice(name="Bot Online", value="on"),
    app_commands.Choice(name="Bot Offline", value="off"),
    app_commands.Choice(name="Bot Maintenance", value="maintenance")
])
async def status_command(
    interaction: discord.Interaction, 
    status_type: str,
    update_persistent: bool = False
):
    """
    Send a status message to the designated status channel or update the persistent bot status.
    
    Parameters:
    - status_type: The type of status message to send (on, off, maintenance)
    - update_persistent: Whether to update the persistent bot status message (True/False)
    
    Only certain roles can use this command.
    """
    global bot_status_message_id
    
    await interaction.response.defer(ephemeral=True)
    
    # Check if the user has permission
    if interaction.user.id not in [1308527904497340467, 479711321399623681]:
        await interaction.followup.send("❌ You don't have permission to use this command!", ephemeral=True)
        return
    
    # If update_persistent is True, update the persistent bot status message
    if update_persistent:
        if status_type == "on":
            # Update to online
            new_message_id = await bot_status.create_or_update_bot_status_message(bot, bot_status_message_id)
            if new_message_id:
                bot_status_message_id = new_message_id
                await interaction.followup.send("✅ Updated persistent bot status to online", ephemeral=True)
            else:
                await interaction.followup.send("❌ Failed to update persistent bot status to online", ephemeral=True)
        elif status_type == "off":
            # Update to offline
            await bot_status.set_bot_status_offline(bot, bot_status_message_id)
            await interaction.followup.send("✅ Updated persistent bot status to offline", ephemeral=True)
        elif status_type == "maintenance":
            # Update to maintenance
            success = await set_bot_maintenance()
            if success:
                await interaction.followup.send("✅ Updated persistent bot status to maintenance", ephemeral=True)
            else:
                await interaction.followup.send("❌ Failed to update persistent bot status to maintenance", ephemeral=True)
        return
    
    # Otherwise, just send a status message (non-persistent)
    success = await bot_status.send_status_message(bot, status_type)
    
    if success:
        await interaction.followup.send(f"✅ Status message sent successfully: {status_type}", ephemeral=True)
    else:
        await interaction.followup.send(f"❌ Failed to send status message. Please check the logs.", ephemeral=True)

# Define shutdown handlers
def handle_exit_signal(signum, frame):
    """Handle exit signals to gracefully shut down the bot"""
    print(f"Received exit signal: {signum}")
    
    # Schedule the offline status update in the event loop
    # This needs to run before the bot shuts down
    if bot.loop.is_running():
        bot.loop.create_task(set_bot_offline())
        
        # Let the offline status task complete before exiting
        import time
        time.sleep(1)  # Small delay to allow the task to run
        
    print("Bot is shutting down...")
    
    # This will raise SystemExit and allow bot.close() to be called
    import sys
    sys.exit(0)

# Register the signal handlers
signal.signal(signal.SIGINT, handle_exit_signal)  # Handles Ctrl+C
signal.signal(signal.SIGTERM, handle_exit_signal)  # Handles termination signal

# Get bot token from environment
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("⚠️ Please set the DISCORD_TOKEN environment variable with your bot token!")
    exit(1)

try:
    bot.run(TOKEN)
except KeyboardInterrupt:
    print("Bot stopped by keyboard interrupt")
except Exception as e:
    print(f"Bot stopped due to error: {e}")
finally:
    print("Bot has been shut down")
