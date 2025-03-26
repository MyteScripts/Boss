import asyncio
import aiosqlite
import datetime

async def create_invite_tables():
    """Create the missing invite tables that are needed for proper invite tracking"""
    print("🔄 Creating missing invite tables (invites, invite_counts, invite_reward_logs)...")
    
    try:
        async with aiosqlite.connect("leveling.db") as db:
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
            print("✅ Successfully created missing invite tables")
            
            # Verify the tables exist
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name='invites' OR name='invite_counts' OR name='invite_reward_logs')")
            tables = [row[0] async for row in cursor]
            print(f"✅ Verified tables: {', '.join(tables)}")
            
    except Exception as e:
        print(f"❌ Error creating invite tables: {e}")

if __name__ == "__main__":
    asyncio.run(create_invite_tables())