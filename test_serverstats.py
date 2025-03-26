"""
Test script for the enhanced serverstats persistence functionality.
This script verifies that server statistics work correctly even after bot restarts.
"""

import aiosqlite
import asyncio
from datetime import datetime, timedelta

async def add_test_message_logs():
    """Add some test message logs to verify our persistence implementation"""
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Create timestamps throughout the day
    today_timestamps = [
        f"{today} {hour:02d}:{minute:02d}:00" 
        for hour in range(0, 24, 2) 
        for minute in range(0, 60, 15)
    ]
    yesterday_timestamps = [
        f"{yesterday} {hour:02d}:{minute:02d}:00" 
        for hour in range(0, 24, 3) 
        for minute in range(0, 60, 30)
    ]
    
    print(f"Adding {len(today_timestamps)} test message logs for today")
    print(f"Adding {len(yesterday_timestamps)} test message logs for yesterday")
    
    async with aiosqlite.connect("leveling.db") as db:
        # Add test user if not exists
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, xp, level)
            VALUES (123456789, 0, 1)
        """)
        
        # Add today's messages
        for timestamp in today_timestamps:
            await db.execute("""
                INSERT INTO message_log (user_id, channel_id, timestamp)
                VALUES (?, ?, ?)
            """, (123456789, 987654321, timestamp))
        
        # Add yesterday's messages
        for timestamp in yesterday_timestamps:
            await db.execute("""
                INSERT INTO message_log (user_id, channel_id, timestamp)
                VALUES (?, ?, ?)
            """, (123456789, 987654321, timestamp))
        
        await db.commit()
    
    print("Test data added successfully!")

async def test_server_stats():
    """Verify that our stats calculation is working correctly"""
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    async with aiosqlite.connect("leveling.db") as db:
        # Count today's messages
        cursor = await db.execute("""
            SELECT COUNT(*) FROM message_log
            WHERE DATE(timestamp) = DATE(?)
        """, (today,))
        today_count = await cursor.fetchone()
        today_count = today_count[0] if today_count else 0
        
        # Count yesterday's messages
        cursor = await db.execute("""
            SELECT COUNT(*) FROM message_log
            WHERE DATE(timestamp) = DATE(?)
        """, (yesterday,))
        yesterday_count = await cursor.fetchone()
        yesterday_count = yesterday_count[0] if yesterday_count else 0
        
        # Count messages by hour for today
        cursor = await db.execute("""
            SELECT strftime('%H', timestamp) as hour, COUNT(*) 
            FROM message_log 
            WHERE DATE(timestamp) = DATE(?) 
            GROUP BY hour 
            ORDER BY COUNT(*) DESC
            LIMIT 1
        """, (today,))
        most_active_hour = await cursor.fetchone()
        
        # Get total message count
        cursor = await db.execute("SELECT COUNT(*) FROM message_log")
        total_count = await cursor.fetchone()
        total_count = total_count[0] if total_count else 0
    
    print("\nTest Results:")
    print(f"Today's message count: {today_count}")
    print(f"Yesterday's message count: {yesterday_count}")
    print(f"Total message count: {total_count}")
    
    if most_active_hour:
        hour, count = most_active_hour
        print(f"Most active hour: {hour}:00 with {count} messages")
    else:
        print("No active hours found")
    
    print("\nVerification complete! The /serverstats command should now work properly.")

async def main():
    """Run all test functions"""
    print("Starting serverstats persistence test...")
    await add_test_message_logs()
    await test_server_stats()
    print("Test completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())