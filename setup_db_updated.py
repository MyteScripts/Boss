
import aiosqlite

async def setup_db():
    try:
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

            # Create command_permissions table to store permissions
            await db.execute('''
                CREATE TABLE IF NOT EXISTS command_permissions (
                    command_name TEXT NOT NULL,
                    permission_value TEXT NOT NULL,
                    PRIMARY KEY (command_name, permission_value)
                )
            ''')

            # Create role section assignments table
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
            
            # Create server stats table for message tracking
            await db.execute('''
                CREATE TABLE IF NOT EXISTS server_stats (
                    guild_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    total_messages INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, date)
                )
            ''')
            
            # Create user activity tracking table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS activity_tracking (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            
            # Create activity event state table for persistence
            await db.execute('''
                CREATE TABLE IF NOT EXISTS activity_event_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    active INTEGER DEFAULT 0,
                    end_time TEXT,
                    prize TEXT
                )
            ''')
            
            # Insert default activity event state if not exists
            await db.execute(
                'INSERT OR IGNORE INTO activity_event_state (id, active, end_time, prize) VALUES (1, 0, NULL, NULL)'
            )

            # Create leveling settings table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS leveling_settings (
                    setting_name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
            ''')

            # Insert default settings if table is empty
            cursor = await db.execute('SELECT COUNT(*) FROM leveling_settings')
            count = await cursor.fetchone()

            if count[0] == 0:
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

                for setting, value in default_settings:
                    await db.execute('INSERT INTO leveling_settings (setting_name, value) VALUES (?, ?)',
                                   (setting, value))

            # Check if level_roles table is empty, and if so, add default role mappings
            cursor = await db.execute('SELECT COUNT(*) FROM level_roles')
            count = await cursor.fetchone()

            if count[0] == 0:
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

                for level, role_id in default_level_roles.items():
                    await db.execute(
                        'INSERT INTO level_roles (level, role_id) VALUES (?, ?)',
                        (level, role_id)
                    )

            # Create message_log table for tracking individual messages with timestamps
            await db.execute('''
                CREATE TABLE IF NOT EXISTS message_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create invite_tracking table for better invite tracking
            await db.execute('''
                CREATE TABLE IF NOT EXISTS invite_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inviter_id INTEGER NOT NULL,
                    invited_user_id INTEGER NOT NULL,
                    invited_user_name TEXT NOT NULL,
                    invite_code TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            ''')
            
            # Create invite_cache table to track invites and their uses
            await db.execute('''
                CREATE TABLE IF NOT EXISTS invite_cache (
                    code TEXT PRIMARY KEY,
                    uses INTEGER NOT NULL,
                    creator_id INTEGER NOT NULL,
                    max_uses INTEGER,
                    created_at REAL NOT NULL,
                    expires_at REAL
                )
            ''')
            
            # Create modern invite tracking tables
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

    except Exception as e:
        print(f"Error in initial DB setup: {e}")
        raise e
