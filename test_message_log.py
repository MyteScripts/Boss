"""
Test script to verify the message_log table exists and is working properly.
This script:
1. Checks if the message_log table exists
2. Adds a test message record
3. Retrieves and displays the record
"""

import asyncio
import aiosqlite
from datetime import datetime

async def test_message_log_table():
    """Test if the message_log table exists and functions correctly"""
    try:
        async with aiosqlite.connect("leveling.db") as db:
            # Check if the table exists by trying to get its schema
            cursor = await db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='message_log'")
            schema = await cursor.fetchone()
            
            if not schema:
                print("❌ message_log table does not exist!")
                return False
            
            print("✅ message_log table exists with schema:")
            print(schema[0])
            
            # Add a test record
            test_user_id = 999999999
            test_channel_id = 888888888
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            await db.execute(
                "INSERT INTO message_log (user_id, channel_id, timestamp) VALUES (?, ?, ?)",
                (test_user_id, test_channel_id, current_time)
            )
            await db.commit()
            
            print(f"✅ Added test record with timestamp {current_time}")
            
            # Retrieve the record
            cursor = await db.execute(
                "SELECT * FROM message_log WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (test_user_id,)
            )
            record = await cursor.fetchone()
            
            if record:
                print("✅ Successfully retrieved record:")
                print(f"  ID: {record[0]}")
                print(f"  User ID: {record[1]}")
                print(f"  Channel ID: {record[2]}")
                print(f"  Timestamp: {record[3]}")
                
                # Delete the test record to clean up
                await db.execute("DELETE FROM message_log WHERE id = ?", (record[0],))
                await db.commit()
                print("✅ Test record deleted successfully")
                
                return True
            else:
                print("❌ Failed to retrieve test record")
                return False
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

async def main():
    """Run the test functions"""
    print("=== Testing message_log table ===")
    success = await test_message_log_table()
    
    if success:
        print("\n✅ All tests passed! The message_log table is working properly.")
    else:
        print("\n❌ Tests failed. The message_log table is not working correctly.")

if __name__ == "__main__":
    asyncio.run(main())