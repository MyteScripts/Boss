"""
Invite tracking system for Discord bot
This module tracks who invited whom and logs invite activity
"""

import discord
import asyncio
import aiosqlite
import datetime
from discord import app_commands
from discord.ext import commands
from typing import Dict, Optional, List, Tuple
from db_pool import get_db_pool

# Invite tracking cache
guild_invites = {}

async def setup_invite_tables():
    """Create necessary database tables for invite tracking if they don't exist."""
    try:
        # Try importing from db_pool first for better connection management
        try:
            from db_pool import get_db_pool
            print("Using DB pool for invite tables creation")
            db_pool = await get_db_pool()
            
            # Check if we already have the old invite_tracking and invite_cache tables
            results = await db_pool.fetchall("SELECT name FROM sqlite_master WHERE type='table' AND (name='invite_tracking' OR name='invite_cache')", ())
            existing_tables = [row[0] for row in results]
            
            if 'invite_tracking' in existing_tables and 'invite_cache' in existing_tables:
                print("⚠️ Using existing invite_tracking and invite_cache tables instead of creating new ones")
                print("ℹ️ This bot is using the existing invite tracking system")
                return
            
            # If we don't have the old tables or we're setting up a new system, create the new tables
            print("🔄 Setting up new invite tracking tables (invites, invite_counts, invite_reward_logs)")
            
            # Create invite tracking table
            await db_pool.execute('''
                CREATE TABLE IF NOT EXISTS invites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    inviter_id INTEGER,
                    guild_id INTEGER NOT NULL,
                    join_time REAL NOT NULL,
                    invite_code TEXT,
                    is_fake INTEGER DEFAULT 0,
                    is_left INTEGER DEFAULT 0,
                    leave_time REAL DEFAULT NULL
                )
            ''')
            
            # Create invite counts table 
            await db_pool.execute('''
                CREATE TABLE IF NOT EXISTS invite_counts (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    regular INTEGER DEFAULT 0,
                    leaves INTEGER DEFAULT 0,
                    fake INTEGER DEFAULT 0,
                    bonus INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            
            # Create invite rewards logs table
            await db_pool.execute('''
                CREATE TABLE IF NOT EXISTS invite_reward_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    reward_type TEXT NOT NULL,
                    reward_amount INTEGER NOT NULL,
                    invite_count INTEGER NOT NULL,
                    timestamp REAL NOT NULL
                )
            ''')
            
            print("✅ Successfully created invite tracking tables using DB pool")
            return
            
        except (ImportError, Exception) as e:
            print(f"⚠️ Couldn't use DB pool, falling back to direct connection: {e}")
            pass
        
        # Fallback to direct connection if db_pool failed
        async with aiosqlite.connect("leveling.db") as db:
            # Check if we already have the old invite_tracking and invite_cache tables
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name='invite_tracking' OR name='invite_cache')")
            existing_tables = [row[0] async for row in cursor]
            
            if 'invite_tracking' in existing_tables and 'invite_cache' in existing_tables:
                print("⚠️ Using existing invite_tracking and invite_cache tables instead of creating new ones")
                print("ℹ️ This bot is using the existing invite tracking system")
                return
                
            # If we don't have the old tables or we're setting up a new system, create the new tables
            print("🔄 Setting up new invite tracking tables (invites, invite_counts, invite_reward_logs)")
            
            # Create invite tracking table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS invites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    inviter_id INTEGER,
                    guild_id INTEGER NOT NULL,
                    join_time REAL NOT NULL,
                    invite_code TEXT,
                    is_fake INTEGER DEFAULT 0,
                    is_left INTEGER DEFAULT 0,
                    leave_time REAL DEFAULT NULL
                )
            ''')
            
            # Create invite counts table 
            await db.execute('''
                CREATE TABLE IF NOT EXISTS invite_counts (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    regular INTEGER DEFAULT 0,
                    leaves INTEGER DEFAULT 0,
                    fake INTEGER DEFAULT 0,
                    bonus INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            
            # Create invite rewards logs table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS invite_reward_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    reward_type TEXT NOT NULL,
                    reward_amount INTEGER NOT NULL,
                    invite_count INTEGER NOT NULL,
                    timestamp REAL NOT NULL
                )
            ''')
            
            await db.commit()
            print("✅ Successfully created invite tracking tables using direct connection")
            
    except Exception as e:
        print(f"❌ Critical error setting up invite tables: {e}")

async def fetch_guild_invites(guild):
    """Fetch all invites for a guild and cache them."""
    try:
        invites = await guild.invites()
        return {invite.code: invite for invite in invites}
    except discord.HTTPException as e:
        print(f"Error fetching invites for guild {guild.id}: {e}")
        return {}
    except discord.Forbidden:
        print(f"Bot doesn't have permission to fetch invites in guild {guild.id}")
        return {}

async def initialize_invite_cache(bot):
    """Initialize the invite cache for all guilds the bot is in."""
    global guild_invites
    print("Initializing invite cache...")
    
    for guild in bot.guilds:
        guild_invites[guild.id] = await fetch_guild_invites(guild)
    
    print(f"Cached invites for {len(guild_invites)} guilds")

async def update_invite_data(user_id, inviter_id, guild_id, invite_code=None, is_fake=False):
    """Update invite data in the database."""
    now = datetime.datetime.now().timestamp()
    
    try:
        # Try using db_pool first
        try:
            from db_pool import get_db_pool
            db_pool = await get_db_pool()
            
            # Add the invite record
            await db_pool.execute('''
                INSERT INTO invites (user_id, inviter_id, guild_id, join_time, invite_code, is_fake)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, inviter_id, guild_id, now, invite_code, 1 if is_fake else 0))
            
            if not is_fake and inviter_id:
                # Update inviter's counts
                await db_pool.execute('''
                    INSERT INTO invite_counts (user_id, guild_id, regular)
                    VALUES (?, ?, 1)
                    ON CONFLICT(user_id, guild_id) DO UPDATE
                    SET regular = regular + 1
                ''', (inviter_id, guild_id))
            elif is_fake and inviter_id:
                # Update fake invite count
                await db_pool.execute('''
                    INSERT INTO invite_counts (user_id, guild_id, fake)
                    VALUES (?, ?, 1)
                    ON CONFLICT(user_id, guild_id) DO UPDATE
                    SET fake = fake + 1
                ''', (inviter_id, guild_id))
                
            return
            
        except Exception as e:
            print(f"⚠️ Couldn't use DB pool for update_invite_data, falling back to direct connection: {e}")
    
        # Fallback to direct connection
        async with aiosqlite.connect("leveling.db") as db:
            # Add the invite record
            await db.execute('''
                INSERT INTO invites (user_id, inviter_id, guild_id, join_time, invite_code, is_fake)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, inviter_id, guild_id, now, invite_code, 1 if is_fake else 0))
            
            if not is_fake and inviter_id:
                # Update inviter's counts
                await db.execute('''
                    INSERT INTO invite_counts (user_id, guild_id, regular)
                    VALUES (?, ?, 1)
                    ON CONFLICT(user_id, guild_id) DO UPDATE
                    SET regular = regular + 1
                ''', (inviter_id, guild_id))
            elif is_fake and inviter_id:
                # Update fake invite count
                await db.execute('''
                    INSERT INTO invite_counts (user_id, guild_id, fake)
                    VALUES (?, ?, 1)
                    ON CONFLICT(user_id, guild_id) DO UPDATE
                    SET fake = fake + 1
                ''', (inviter_id, guild_id))
            
            await db.commit()
            
    except Exception as e:
        print(f"❌ Error in update_invite_data: {e}")

async def mark_user_left(user_id, guild_id):
    """Mark a user as having left the server in the database."""
    now = datetime.datetime.now().timestamp()
    
    try:
        # Try using db_pool first
        try:
            from db_pool import get_db_pool
            db_pool = await get_db_pool()
            
            # Find their most recent invite
            result = await db_pool.fetchone('''
                SELECT id, inviter_id, is_fake
                FROM invites
                WHERE user_id = ? AND guild_id = ? AND is_left = 0
                ORDER BY join_time DESC
                LIMIT 1
            ''', (user_id, guild_id))
            
            if result:
                invite_id, inviter_id, is_fake = result
                
                # Mark as left
                await db_pool.execute('''
                    UPDATE invites
                    SET is_left = 1, leave_time = ?
                    WHERE id = ?
                ''', (now, invite_id))
                
                # Update inviter's counts if this was a valid invite and we know who invited
                if not is_fake and inviter_id:
                    await db_pool.execute('''
                        INSERT INTO invite_counts (user_id, guild_id, leaves)
                        VALUES (?, ?, 1)
                        ON CONFLICT(user_id, guild_id) DO UPDATE
                        SET leaves = leaves + 1
                    ''', (inviter_id, guild_id))
                
                return
            
        except Exception as e:
            print(f"⚠️ Couldn't use DB pool for mark_user_left, falling back to direct connection: {e}")
        
        # Fallback to direct connection
        async with aiosqlite.connect("leveling.db") as db:
            # Find their most recent invite
            cursor = await db.execute('''
                SELECT id, inviter_id, is_fake
                FROM invites
                WHERE user_id = ? AND guild_id = ? AND is_left = 0
                ORDER BY join_time DESC
                LIMIT 1
            ''', (user_id, guild_id))
            
            invite_record = await cursor.fetchone()
            
            if invite_record:
                invite_id, inviter_id, is_fake = invite_record
                
                # Mark as left
                await db.execute('''
                    UPDATE invites
                    SET is_left = 1, leave_time = ?
                    WHERE id = ?
                ''', (now, invite_id))
                
                # Update inviter's counts if this was a valid invite and we know who invited
                if not is_fake and inviter_id:
                    await db.execute('''
                        INSERT INTO invite_counts (user_id, guild_id, leaves)
                        VALUES (?, ?, 1)
                        ON CONFLICT(user_id, guild_id) DO UPDATE
                        SET leaves = leaves + 1
                    ''', (inviter_id, guild_id))
                
                await db.commit()
                
    except Exception as e:
        print(f"❌ Error in mark_user_left: {e}")

async def find_inviter(guild_id, member) -> Tuple[Optional[int], str, bool]:
    """
    Find who invited a member by comparing invite counts before and after they joined.
    Returns a tuple of (inviter_id, invite_code, is_fake)
    
    Special cases:
    - If the user joined through a vanity URL, returns (None, "VANITY", False)
    - If inviter cannot be determined, returns (None, "", False)
    - If self-invite, returns (user_id, invite_code, True)
    """
    global guild_invites
    
    if guild_id not in guild_invites:
        # Initialize guild invites if they don't exist yet
        try:
            guild_invites[guild_id] = await fetch_guild_invites(member.guild)
            print(f"Initialized invite tracking for guild {guild_id} with {len(guild_invites[guild_id])} invites")
        except Exception as e:
            print(f"Failed to initialize invite tracking for guild {guild_id}: {e}")
        return None, "", False
    
    invites_before = guild_invites[guild_id]
    
    try:
        # Get the updated invites
        invites_after = await fetch_guild_invites(member.guild)
        guild_invites[guild_id] = invites_after
        
        # Track which invites had their use count increase
        used_invites = []
        
        # First check for invites with increased use count - this is the most reliable method
        for invite_code, invite in invites_after.items():
            if invite_code in invites_before:
                if invite.uses > invites_before[invite_code].uses:
                    # This invite's use count increased, so it was likely used
                    used_invites.append((
                        invite_code, 
                        invite,
                        invite.uses - invites_before[invite_code].uses  # Calculate difference in uses
                    ))
        
        # If we found exactly one invite with increased uses, it's almost certainly the one used
        if len(used_invites) == 1:
            invite_code, invite, _ = used_invites[0]
            inviter_id = invite.inviter.id
            # Check for self-invites
            if inviter_id == member.id:
                return inviter_id, invite_code, True
            return inviter_id, invite_code, False
            
        # Next check for new invites with use count = 1
        # This checks for invites created after our previous check
        new_invites = []
        for invite_code, invite in invites_after.items():
            if invite_code not in invites_before and invite.uses == 1:
                new_invites.append((invite_code, invite))
        
        # If we found exactly one new invite with 1 use, it's likely the one used
        if len(new_invites) == 1:
            invite_code, invite = new_invites[0]
            inviter_id = invite.inviter.id
            if inviter_id == member.id:
                return inviter_id, invite_code, True
            return inviter_id, invite_code, False
        
        # If we're here and the guild has a vanity URL, assume it was used
        # (unless another invite specifically incremented, which we checked above)
        try:
            if member.guild.vanity_url_code:
                print(f"User {member.name} likely joined using the vanity URL: {member.guild.vanity_url_code}")
                return None, "VANITY", False
        except AttributeError:
            pass
            
        # If we couldn't determine the invite, just return empty values
        # The on_member_join handler will show this as a vanity invite anyway
        return None, "", False
        
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"Error updating invites for guild {guild_id}: {e}")
        return None, "", False

async def get_invite_counts(user_id, guild_id=None):
    """Get a user's invite counts from the database."""
    try:
        # Try using db_pool first
        try:
            from db_pool import get_db_pool
            db_pool = await get_db_pool()
            
            query = '''
                SELECT guild_id, regular, leaves, fake, bonus
                FROM invite_counts
                WHERE user_id = ?
            '''
            params = [user_id]
            
            if guild_id:
                query += " AND guild_id = ?"
                params.append(guild_id)
            
            results = await db_pool.fetchall(query, tuple(params))
            
            if guild_id:
                # Return single guild results
                if results:
                    return {
                        "guild_id": results[0][0],
                        "regular": results[0][1],
                        "leaves": results[0][2],
                        "fake": results[0][3],
                        "bonus": results[0][4],
                        "total": results[0][1] - results[0][2] + results[0][4]  # regular - leaves + bonus
                    }
                return {
                    "guild_id": guild_id,
                    "regular": 0,
                    "leaves": 0,
                    "fake": 0,
                    "bonus": 0,
                    "total": 0
                }
            else:
                # Return all guilds
                counts = {}
                for row in results:
                    guild_id, regular, leaves, fake, bonus = row
                    counts[guild_id] = {
                        "regular": regular,
                        "leaves": leaves,
                        "fake": fake,
                        "bonus": bonus,
                        "total": regular - leaves + bonus
                    }
                return counts
                
        except Exception as e:
            print(f"⚠️ Couldn't use DB pool for get_invite_counts, falling back to direct connection: {e}")
    
        # Fallback to direct connection
        async with aiosqlite.connect("leveling.db") as db:
            query = '''
                SELECT guild_id, regular, leaves, fake, bonus
                FROM invite_counts
                WHERE user_id = ?
            '''
            params = [user_id]
            
            if guild_id:
                query += " AND guild_id = ?"
                params.append(guild_id)
            
            cursor = await db.execute(query, params)
            results = await cursor.fetchall()
            
            if guild_id:
                # Return single guild results
                if results:
                    return {
                        "guild_id": results[0][0],
                        "regular": results[0][1],
                        "leaves": results[0][2],
                        "fake": results[0][3],
                        "bonus": results[0][4],
                        "total": results[0][1] - results[0][2] + results[0][4]  # regular - leaves + bonus
                    }
                return {
                    "guild_id": guild_id,
                    "regular": 0,
                    "leaves": 0,
                    "fake": 0,
                    "bonus": 0,
                    "total": 0
                }
            else:
                # Return all guilds
                counts = {}
                for row in results:
                    guild_id, regular, leaves, fake, bonus = row
                    counts[guild_id] = {
                        "regular": regular,
                        "leaves": leaves,
                        "fake": fake,
                        "bonus": bonus,
                        "total": regular - leaves + bonus
                    }
                return counts
                
    except Exception as e:
        print(f"❌ Error in get_invite_counts: {e}")
        # Return empty data on error
        if guild_id:
            return {
                "guild_id": guild_id,
                "regular": 0,
                "leaves": 0,
                "fake": 0,
                "bonus": 0,
                "total": 0
            }
        return {}

async def set_user_invites(user_id, guild_id, count):
    """Manually set a user's invite count."""
    async with aiosqlite.connect("leveling.db") as db:
        # First check if user exists in the invite_counts table
        cursor = await db.execute('''
            SELECT regular, bonus
            FROM invite_counts
            WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id))
        
        result = await cursor.fetchone()
        
        if result:
            current_regular, current_bonus = result
            # Calculate the bonus needed to reach the desired total
            new_bonus = count - (current_regular - 0)  # regular - leaves
            
            await db.execute('''
                UPDATE invite_counts
                SET bonus = ?
                WHERE user_id = ? AND guild_id = ?
            ''', (new_bonus, user_id, guild_id))
        else:
            # If user doesn't exist, add them with the count as bonus
            await db.execute('''
                INSERT INTO invite_counts (user_id, guild_id, regular, leaves, fake, bonus)
                VALUES (?, ?, 0, 0, 0, ?)
            ''', (user_id, guild_id, count))
        
        await db.commit()
        
async def reset_user_invites(user_id, guild_id):
    """Reset a user's invite count to zero."""
    try:
        # Try using the DB pool
        db_pool = await get_db_pool()
        
        # Reset the user's bonus invites to 0
        await db_pool.execute('''
            UPDATE invite_counts
            SET regular = 0, leaves = 0, fake = 0, bonus = 0
            WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id))
        
        return True
    except Exception as e:
        print(f"⚠️ Couldn't use DB pool for reset_user_invites, falling back to direct connection: {e}")
        
        # Fallback to direct connection
        async with aiosqlite.connect("leveling.db") as db:
            await db.execute('''
                UPDATE invite_counts
                SET regular = 0, leaves = 0, fake = 0, bonus = 0
                WHERE user_id = ? AND guild_id = ?
            ''', (user_id, guild_id))
            
            await db.commit()
            
        return True

async def reset_all_invites(guild_id):
    """Reset invite counts for all users in a guild."""
    try:
        # Try using the DB pool
        db_pool = await get_db_pool()
        await db_pool.execute('''
            UPDATE invite_counts
            SET regular = 0, leaves = 0, fake = 0, bonus = 0
            WHERE guild_id = ?
        ''', (guild_id,))
        
        # Get the number of users affected
        cursor = await db_pool.fetchall('''
            SELECT COUNT(*)
            FROM invite_counts
            WHERE guild_id = ?
        ''', (guild_id,))
        
        return cursor[0][0] if cursor else 0
    except Exception as e:
        print(f"⚠️ Couldn't use DB pool for reset_all_invites, falling back to direct connection: {e}")
        
        # Fallback to direct connection
        async with aiosqlite.connect("leveling.db") as db:
            await db.execute('''
                UPDATE invite_counts
                SET regular = 0, leaves = 0, fake = 0, bonus = 0
                WHERE guild_id = ?
            ''', (guild_id,))
            
            # Get the number of users affected
            cursor = await db.execute('''
                SELECT COUNT(*)
                FROM invite_counts
                WHERE guild_id = ?
            ''', (guild_id,))
            
            count = await cursor.fetchone()
            await db.commit()
            
            return count[0] if count else 0

async def add_user_bonus_invites(user_id, guild_id, amount):
    """Add bonus invites to a user."""
    async with aiosqlite.connect("leveling.db") as db:
        await db.execute('''
            INSERT INTO invite_counts (user_id, guild_id, bonus)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE
            SET bonus = bonus + ?
        ''', (user_id, guild_id, amount, amount))
        
        await db.commit()

async def get_invited_users(inviter_id, guild_id=None, include_leaves=False):
    """Get a list of users invited by a specific user."""
    async with aiosqlite.connect("leveling.db") as db:
        query = '''
            SELECT user_id, join_time, is_left
            FROM invites
            WHERE inviter_id = ? AND is_fake = 0
        '''
        params = [inviter_id]
        
        if guild_id:
            query += " AND guild_id = ?"
            params.append(guild_id)
        
        if not include_leaves:
            query += " AND is_left = 0"
        
        query += " ORDER BY join_time DESC"
        
        cursor = await db.execute(query, params)
        results = await cursor.fetchall()
        
        return [{"user_id": row[0], "join_time": row[1], "has_left": bool(row[2])} for row in results]

async def get_top_inviters(guild_id, limit=10):
    """Get the top inviters for a guild."""
    async with aiosqlite.connect("leveling.db") as db:
        cursor = await db.execute('''
            SELECT user_id, regular, leaves, bonus
            FROM invite_counts
            WHERE guild_id = ?
            ORDER BY (regular - leaves + bonus) DESC, regular DESC
            LIMIT ?
        ''', (guild_id, limit))
        
        results = await cursor.fetchall()
        
        return [
            {
                "user_id": row[0],
                "regular": row[1],
                "leaves": row[2],
                "bonus": row[3],
                "total": row[1] - row[2] + row[3]
            }
            for row in results
        ]

async def get_all_invites_leaderboard(limit=100):
    """Get the top inviters across all guilds."""
    async with aiosqlite.connect("leveling.db") as db:
        cursor = await db.execute('''
            SELECT user_id, SUM(regular) as total_regular, SUM(leaves) as total_leaves, SUM(bonus) as total_bonus
            FROM invite_counts
            GROUP BY user_id
            ORDER BY (SUM(regular) - SUM(leaves) + SUM(bonus)) DESC, SUM(regular) DESC
            LIMIT ?
        ''', (limit,))
        
        results = await cursor.fetchall()
        
        return [
            {
                "user_id": row[0],
                "regular": row[1],
                "leaves": row[2],
                "bonus": row[3],
                "total": row[1] - row[2] + row[3]
            }
            for row in results
        ]

async def log_invite_reward(user_id, reward_type, reward_amount, invite_count):
    """Log an invite reward given to a user."""
    now = datetime.datetime.now().timestamp()
    
    async with aiosqlite.connect("leveling.db") as db:
        await db.execute('''
            INSERT INTO invite_reward_logs (user_id, reward_type, reward_amount, invite_count, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, reward_type, reward_amount, invite_count, now))
        
        await db.commit()

async def get_reward_logs(user_id=None, limit=20):
    """Get reward logs, optionally filtered by user."""
    async with aiosqlite.connect("leveling.db") as db:
        query = '''
            SELECT user_id, reward_type, reward_amount, invite_count, timestamp
            FROM invite_reward_logs
        '''
        params = []
        
        if user_id:
            query += " WHERE user_id = ?"
            params.append(user_id)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor = await db.execute(query, params)
        results = await cursor.fetchall()
        
        return [
            {
                "user_id": row[0],
                "reward_type": row[1],
                "reward_amount": row[2],
                "invite_count": row[3],
                "timestamp": row[4]
            }
            for row in results
        ]

async def get_user_inviter(user_id, guild_id):
    """Find who invited a specific user."""
    async with aiosqlite.connect("leveling.db") as db:
        cursor = await db.execute('''
            SELECT inviter_id, join_time, invite_code
            FROM invites
            WHERE user_id = ? AND guild_id = ?
            ORDER BY join_time DESC
            LIMIT 1
        ''', (user_id, guild_id))
        
        result = await cursor.fetchone()
        
        if result:
            return {
                "inviter_id": result[0],
                "join_time": result[1],
                "invite_code": result[2]
            }
        return None

class InviteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logs_channel_id = 1354491891579752448  # Channel ID for invite logs
        
    async def get_logs_channel(self):
        """Get the logs channel for invite tracking."""
        channel = self.bot.get_channel(self.logs_channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(self.logs_channel_id)
            except discord.HTTPException:
                print(f"Cannot find logs channel with ID {self.logs_channel_id}")
                return None
        return channel
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize invite tracking when the bot is ready."""
        print("🔄 Setting up invite tracking tables...")
        try:
            await setup_invite_tables()
            print("✅ Invite tables created successfully")
        except Exception as e:
            print(f"❌ Error creating invite tables: {e}")
            
        print("🔄 Initializing invite cache...")
        try:
            await initialize_invite_cache(self.bot)
            print("✅ Invite cache initialized")
        except Exception as e:
            print(f"❌ Error initializing invite cache: {e}")
            
        print("✅ Invite tracking system initialization complete")
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Cache invites when the bot joins a new guild."""
        guild_invites[guild.id] = await fetch_guild_invites(guild)
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Remove invite cache when the bot leaves a guild."""
        if guild.id in guild_invites:
            del guild_invites[guild.id]
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        """Update invite cache when a new invite is created."""
        if invite.guild.id not in guild_invites:
            guild_invites[invite.guild.id] = {}
        
        guild_invites[invite.guild.id][invite.code] = invite
    
    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        """Update invite cache when an invite is deleted."""
        if invite.guild.id in guild_invites and invite.code in guild_invites[invite.guild.id]:
            del guild_invites[invite.guild.id][invite.code]
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Track who invited the member when they join."""
        if member.bot:
            return
        
        inviter_id, invite_code, is_fake = await find_inviter(member.guild.id, member)
        
        # Update database with invite info
        await update_invite_data(member.id, inviter_id, member.guild.id, invite_code, is_fake)
        
        # Send log to the logs channel
        logs_channel = await self.get_logs_channel()
        if logs_channel:
            # Handle genuine vanity URL case
            if invite_code == "VANITY" and member.guild.vanity_url_code:
                # Plain text message for vanity URL as requested
                await logs_channel.send(f"{member.mention} joined by vanity invite")
                return
            
            # Handle normal invite case where an inviter was found
            if inviter_id:
                try:
                    inviter = await self.bot.fetch_user(inviter_id)
                    
                    if is_fake:
                        await logs_channel.send(f"{member.mention} joined using their own invite")
                    else:
                        # Get inviter's updated stats
                        counts = await get_invite_counts(inviter_id, member.guild.id)
                        
                        # Simple text message format exactly as requested
                        await logs_channel.send(
                            f"{member.mention} joined by using {inviter.mention} invite link. {inviter.mention} invites now are {counts['total']}"
                        )
                except Exception as e:
                    print(f"Error fetching inviter: {e}")
                    # Fallback to more accurate message instead of claiming it was a vanity invite
                    await logs_channel.send(f"{member.mention} joined the server, but couldn't track invite details")
            else:
                # If no inviter was identified, we won't default to showing vanity invite anymore
                # Only show "joined by vanity invite" when we're certain it's a vanity URL
                if member.guild.vanity_url_code:
                    await logs_channel.send(f"{member.mention} joined by vanity invite")
                else:
                    # More neutral message when we're unsure
                    await logs_channel.send(f"{member.mention} joined the server (invite unknown)")
            
            try:
                pass  # Placeholder for any future additional logging if needed
            except discord.HTTPException as e:
                print(f"Failed to send invite log: {e}")
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Track when a member leaves and update the database."""
        if member.bot:
            return
        
        await mark_user_left(member.id, member.guild.id)
        
        # Get who invited them
        inviter_info = await get_user_inviter(member.id, member.guild.id)
        
        # Send log to the logs channel
        logs_channel = await self.get_logs_channel()
        if logs_channel:
            # Basic message about member leaving
            leave_message = f"{member} has left the server"
            
            # Add info about who invited them if available
            if inviter_info and inviter_info["inviter_id"]:
                inviter_id = inviter_info["inviter_id"]
                try:
                    inviter = await self.bot.fetch_user(inviter_id)
                    
                    # Get inviter's updated stats
                    counts = await get_invite_counts(inviter_id, member.guild.id)
                    
                    # Add inviter info to the message
                    leave_message += f". They were invited by {inviter.mention}. {inviter.mention} invites now are {counts['total']}"
                except:
                    leave_message += f". They were invited by Unknown User ({inviter_id})"
            
            try:
                await logs_channel.send(leave_message)
            except discord.HTTPException as e:
                print(f"Failed to send invite log: {e}")
    
    @app_commands.command(name="invites", description="Check how many invites you or another user has")
    async def invites(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """Check how many invites you or another user has."""
        # Check if in DM
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
            
        try:
            await interaction.response.defer()
            
            # Get the proper target member
            if member:
                target = member
            else:
                # If no member specified, use the interaction user
                if isinstance(interaction.user, discord.Member):
                    target = interaction.user
                else:
                    # We need to fetch the Member object if we only have a User
                    target = await interaction.guild.fetch_member(interaction.user.id)
            
            # Now get invite counts for target
            counts = await get_invite_counts(target.id, interaction.guild.id)
            
            embed = discord.Embed(
                title="Invite Counts",
                description=f"Invite information for {target.mention}",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="Regular", value=str(counts["regular"]), inline=True)
            embed.add_field(name="Left", value=str(counts["leaves"]), inline=True)
            embed.add_field(name="Fake", value=str(counts["fake"]), inline=True)
            embed.add_field(name="Bonus", value=str(counts["bonus"]), inline=True)
            embed.add_field(name="Total", value=str(counts["total"]), inline=True)
            
            # Get people they've invited who are still in the server
            invited_users = await get_invited_users(target.id, interaction.guild.id, include_leaves=False)
            currently_in_server = len(invited_users)
            
            embed.add_field(name="Currently In Server", value=str(currently_in_server), inline=True)
            
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.set_footer(text=f"User ID: {target.id}")
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error in /invites command: {e}")
            await interaction.followup.send("An error occurred while getting invite information.", ephemeral=True)
    
    @app_commands.command(name="inviteleaderboard", description="Display the top inviters in the server")
    async def inviteleaderboard(self, interaction: discord.Interaction):
        """Display the top inviters in the server."""
        # Check if in DM
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
            
        try:
            await interaction.response.defer()
            
            top_inviters = await get_top_inviters(interaction.guild.id, limit=10)
            
            if not top_inviters:
                await interaction.followup.send("No invite data found for this server.")
                return
            
            embed = discord.Embed(
                title="Invite Leaderboard",
                description="Top inviters in this server",
                color=discord.Color.gold()
            )
            
            leaderboard_text = ""
            for idx, inviter in enumerate(top_inviters, 1):
                try:
                    user = await self.bot.fetch_user(inviter["user_id"])
                    username = user.name if user else f"Unknown User ({inviter['user_id']})"
                except:
                    username = f"Unknown User ({inviter['user_id']})"
                
                leaderboard_text += f"**{idx}.** {username}: **{inviter['total']}** invites "
                leaderboard_text += f"({inviter['regular']} regular, {inviter['leaves']} left, {inviter['bonus']} bonus)\n"
            
            embed.description = leaderboard_text
            embed.set_footer(text=f"Server ID: {interaction.guild.id}")
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error in /inviteleaderboard command: {e}")
            await interaction.followup.send("An error occurred while getting the invite leaderboard.", ephemeral=True)
    
    @app_commands.command(name="allinvites", description="Display the top inviters across all servers")
    @app_commands.default_permissions(administrator=True)
    async def allinvites(self, interaction: discord.Interaction):
        """Display the top inviters across all servers."""
        try:
            # Check if in DM - need to verify admin status differently in DMs
            if not interaction.guild:
                # Only super admins can use this in DMs
                if interaction.user.id not in [1308527904497340467, 479711321399623681]:
                    await interaction.response.send_message("❌ This command can only be used by server admins.", ephemeral=True)
                    return
            else:
                # In a guild, check for admin permissions
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
                    return
                    
            await interaction.response.defer()
            
            top_inviters = await get_all_invites_leaderboard(limit=10)
            
            if not top_inviters:
                await interaction.followup.send("No invite data found.")
                return
            
            embed = discord.Embed(
                title="Global Invite Leaderboard",
                description="Top inviters across all servers",
                color=discord.Color.gold()
            )
            
            leaderboard_text = ""
            for idx, inviter in enumerate(top_inviters, 1):
                try:
                    user = await self.bot.fetch_user(inviter["user_id"])
                    username = user.name if user else f"Unknown User ({inviter['user_id']})"
                except:
                    username = f"Unknown User ({inviter['user_id']})"
                
                leaderboard_text += f"**{idx}.** {username}: **{inviter['total']}** invites "
                leaderboard_text += f"({inviter['regular']} regular, {inviter['leaves']} left, {inviter['bonus']} bonus)\n"
            
            embed.description = leaderboard_text
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error in /allinvites command: {e}")
            await interaction.followup.send("An error occurred while getting the global invite leaderboard.", ephemeral=True)
    
    @app_commands.command(name="inviteinfo", description="Check who invited a specific user")
    async def inviteinfo(self, interaction: discord.Interaction, member: discord.Member):
        """Check who invited a specific user."""
        # Check if in DM
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
            
        try:
            await interaction.response.defer()
            
            inviter_info = await get_user_inviter(member.id, interaction.guild.id)
            
            if not inviter_info or not inviter_info["inviter_id"]:
                await interaction.followup.send(f"I couldn't find who invited {member.mention}.", ephemeral=True)
                return
            
            try:
                inviter = await self.bot.fetch_user(inviter_info["inviter_id"])
                inviter_name = inviter.name if inviter else f"Unknown User ({inviter_info['inviter_id']})"
                inviter_mention = inviter.mention if inviter else f"Unknown User ({inviter_info['inviter_id']})"
            except:
                inviter_name = f"Unknown User ({inviter_info['inviter_id']})"
                inviter_mention = f"Unknown User ({inviter_info['inviter_id']})"
            
            join_time = datetime.datetime.fromtimestamp(inviter_info["join_time"])
            
            embed = discord.Embed(
                title="Invite Information",
                description=f"{member.mention} was invited by {inviter_mention}",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="Inviter", value=inviter_name, inline=True)
            embed.add_field(name="Join Date", value=f"<t:{int(inviter_info['join_time'])}:F>", inline=True)
            
            if inviter_info["invite_code"]:
                embed.add_field(name="Invite Code", value=inviter_info["invite_code"], inline=True)
            
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"User ID: {member.id} | Inviter ID: {inviter_info['inviter_id']}")
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error in /inviteinfo command: {e}")
            await interaction.followup.send("An error occurred while getting invite information.", ephemeral=True)
    
    @app_commands.command(name="setinvites", description="Manually set a user's invite count")
    @app_commands.default_permissions(administrator=True)
    async def setinvites(self, interaction: discord.Interaction, member: discord.Member, count: int):
        """Manually set a user's invite count."""
        # Check if in DM
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
            
        try:
            # Check if user has admin permissions
            if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
                # Special case for super admins
                if interaction.user.id not in [1308527904497340467, 479711321399623681]:
                    await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
                    return
            
            await interaction.response.defer()
            
            if count < 0:
                await interaction.followup.send("❌ Invite count cannot be negative.", ephemeral=True)
                return
            
            # Get the current counts before updating
            before_counts = await get_invite_counts(member.id, interaction.guild.id)
            
            # Update the invite count
            await set_user_invites(member.id, interaction.guild.id, count)
            
            # Get the updated counts
            after_counts = await get_invite_counts(member.id, interaction.guild.id)
            
            embed = discord.Embed(
                title="Updated Invite Count",
                description=f"Set {member.mention}'s invite count to **{count}**",
                color=discord.Color.green()
            )
            
            embed.add_field(name="Before", value=str(before_counts["total"]), inline=True)
            embed.add_field(name="After", value=str(after_counts["total"]), inline=True)
            embed.add_field(name="Difference", value=str(after_counts["total"] - before_counts["total"]), inline=True)
            
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Updated by {interaction.user.name}")
            
            await interaction.followup.send(embed=embed)
            
            # Log the update to the logs channel
            logs_channel = await self.get_logs_channel()
            if logs_channel:
                log_embed = discord.Embed(
                    title="Invite Count Updated",
                    description=f"{interaction.user.mention} updated {member.mention}'s invite count",
                    color=discord.Color.yellow()
                )
                
                log_embed.add_field(name="Before", value=str(before_counts["total"]), inline=True)
                log_embed.add_field(name="After", value=str(after_counts["total"]), inline=True)
                log_embed.add_field(name="Difference", value=str(after_counts["total"] - before_counts["total"]), inline=True)
                
                log_embed.set_thumbnail(url=member.display_avatar.url)
                log_embed.set_footer(text=f"Updated by {interaction.user.name} ({interaction.user.id})")
                log_embed.timestamp = datetime.datetime.now()
                
                try:
                    await logs_channel.send(embed=log_embed)
                except discord.HTTPException as e:
                    print(f"Failed to send invite log: {e}")
        except Exception as e:
            print(f"Error in /setinvites command: {e}")
            await interaction.followup.send("❌ An error occurred while updating invite count.", ephemeral=True)
    
    @app_commands.command(name="resetinvites", description="Reset invite counts for a member or all members")
    @app_commands.default_permissions(administrator=True)
    async def resetinvites(
        self, 
        interaction: discord.Interaction, 
        member: Optional[discord.Member] = None,
        all_members: Optional[bool] = False
    ):
        """
        Reset invite counts for a specific member or all members.
        
        Parameters:
        - member: The member to reset invites for (optional)
        - all_members: Set to True to reset invites for all members (optional)
        """
        try:
            # Check if in DM - need to verify admin status differently in DMs
            if not interaction.guild:
                # Only super admins can use this in DMs
                if interaction.user.id not in [1308527904497340467, 479711321399623681]:
                    await interaction.response.send_message("❌ This command can only be used by server admins.", ephemeral=True)
                    return
            else:
                # In a guild, check for admin permissions
                if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
                    return
            
            # Validate parameters
            if not member and not all_members:
                await interaction.response.send_message(
                    "❌ You must either specify a member or set all_members to True.", 
                    ephemeral=True
                )
                return
                
            await interaction.response.defer()
            
            # Reset invites based on parameters
            if all_members:
                # Reset all invites in the server
                affected_count = await reset_all_invites(interaction.guild.id)
                
                embed = discord.Embed(
                    title="Invites Reset",
                    description=f"✅ Successfully reset invite counts for all members in the server.",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="Affected Members",
                    value=f"{affected_count} member{'s' if affected_count != 1 else ''}"
                )
                
                embed.set_footer(text=f"Reset by {interaction.user.name}")
                
                await interaction.followup.send(embed=embed)
                
                # Log the reset to the logs channel
                logs_channel = await self.get_logs_channel()
                if logs_channel:
                    log_embed = discord.Embed(
                        title="Server Invites Reset",
                        description=f"{interaction.user.mention} has reset invite counts for all members",
                        color=discord.Color.yellow()
                    )
                    
                    log_embed.add_field(
                        name="Affected Members",
                        value=f"{affected_count} member{'s' if affected_count != 1 else ''}"
                    )
                    
                    log_embed.set_footer(text=f"Reset by {interaction.user.name} ({interaction.user.id})")
                    log_embed.timestamp = datetime.datetime.now()
                    
                    try:
                        await logs_channel.send(embed=log_embed)
                    except discord.HTTPException as e:
                        print(f"Failed to send invite reset log: {e}")
            else:
                # Reset invites for a specific member
                if member is None:
                    await interaction.followup.send("❌ No member specified for reset.", ephemeral=True)
                    return
                
                # Get the current counts before reset
                before_counts = await get_invite_counts(member.id, interaction.guild.id)
                
                # Reset the member's invites
                await reset_user_invites(member.id, interaction.guild.id)
                
                # Get the updated counts
                after_counts = await get_invite_counts(member.id, interaction.guild.id)
                
                embed = discord.Embed(
                    title="Invites Reset",
                    description=f"✅ Successfully reset invite count for {member.mention}",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="Before", value=str(before_counts.get("total", 0)), inline=True)
                embed.add_field(name="After", value=str(after_counts.get("total", 0)), inline=True)
                
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"Reset by {interaction.user.name}")
                
                await interaction.followup.send(embed=embed)
                
                # Log the reset to the logs channel
                logs_channel = await self.get_logs_channel()
                if logs_channel:
                    log_embed = discord.Embed(
                        title="Member Invites Reset",
                        description=f"{interaction.user.mention} has reset invite count for {member.mention}",
                        color=discord.Color.yellow()
                    )
                    
                    log_embed.add_field(name="Before", value=str(before_counts.get("total", 0)), inline=True)
                    log_embed.add_field(name="After", value=str(after_counts.get("total", 0)), inline=True)
                    
                    log_embed.set_thumbnail(url=member.display_avatar.url)
                    log_embed.set_footer(text=f"Reset by {interaction.user.name} ({interaction.user.id})")
                    log_embed.timestamp = datetime.datetime.now()
                    
                    try:
                        await logs_channel.send(embed=log_embed)
                    except discord.HTTPException as e:
                        print(f"Failed to send invite reset log: {e}")
        except Exception as e:
            print(f"Error in /resetinvites command: {e}")
            await interaction.followup.send("❌ An error occurred while resetting invite count.", ephemeral=True)
    
    @app_commands.command(name="inviterewardlogs", description="View the logs of invite rewards")
    @app_commands.default_permissions(administrator=True)
    async def inviterewardlogs(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """View the logs of invite rewards."""
        try:
            # Check if in DM - need to verify admin status differently in DMs
            if not interaction.guild:
                # Only super admins can use this in DMs
                if interaction.user.id not in [1308527904497340467, 479711321399623681]:
                    await interaction.response.send_message("❌ This command can only be used by server admins.", ephemeral=True)
                    return
            else:
                # In a guild, check for admin permissions
                if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
                    return
                    
            await interaction.response.defer()
            
            user_id = member.id if member else None
            logs = await get_reward_logs(user_id, limit=10)
            
            if not logs:
                await interaction.followup.send("No invite reward logs found.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="Invite Reward Logs",
                description=f"Recent invite rewards {f'for {member.mention}' if member else ''}",
                color=discord.Color.blue()
            )
            
            for log in logs:
                try:
                    user = await self.bot.fetch_user(log["user_id"])
                    username = user.name if user else f"Unknown User ({log['user_id']})"
                except:
                    username = f"Unknown User ({log['user_id']})"
                
                reward_time = datetime.datetime.fromtimestamp(log["timestamp"])
                field_name = f"{username} - {log['reward_type']} reward"
                field_value = f"Amount: **{log['reward_amount']}** • Invites: **{log['invite_count']}**\n"
                field_value += f"Time: <t:{int(log['timestamp'])}:R>"
                
                embed.add_field(name=field_name, value=field_value, inline=False)
            
            embed.set_footer(text="Invite reward system")
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error in /inviterewardlogs command: {e}")
            await interaction.followup.send("❌ An error occurred while getting invite reward logs.", ephemeral=True)

async def setup(bot):
    """Add the cog to the bot."""
    await bot.add_cog(InviteTracker(bot))