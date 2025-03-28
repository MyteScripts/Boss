import discord
from datetime import datetime
import aiosqlite

# Bot Status Message Channel ID
BOT_STATUS_CHANNEL_ID = 1354920943503409323

# Function to create or update the bot status message
async def create_or_update_bot_status_message(bot, message_id=None):
    """Create or update the bot status message in the designated channel"""
    try:
        # Get the status channel
        channel = bot.get_channel(BOT_STATUS_CHANNEL_ID)
        if not channel:
            print(f"❌ Could not find status channel with ID {BOT_STATUS_CHANNEL_ID}")
            return None
        
        # Create the status message content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed = discord.Embed(
            title="📊 Bot Status",
            description="The bot is currently online and operational.",
            color=discord.Color.green()
        )
        embed.add_field(name="Status", value="✅ Online", inline=True)
        embed.add_field(name="Last Updated", value=timestamp, inline=True)
        embed.add_field(name="Server Count", value=str(len(bot.guilds)), inline=True)
        embed.set_footer(text=f"Bot version: 1.0.0 | Started at {timestamp}")
        
        # Try to fetch existing message
        try:
            if message_id:
                try:
                    # Try to edit existing message
                    message = await channel.fetch_message(message_id)
                    await message.edit(embed=embed)
                    print(f"✅ Updated bot status message (ID: {message_id})")
                    return message_id
                except (discord.NotFound, discord.HTTPException, discord.Forbidden):
                    # Message was deleted or can't be edited, create a new one
                    message_id = None
            
            # If we reach here, we need to create a new message
            message = await channel.send(embed=embed)
            print(f"✅ Created new bot status message (ID: {message.id})")
            return message.id
        except Exception as e:
            print(f"❌ Error updating bot status message: {e}")
            return None
    except Exception as e:
        print(f"❌ Error in create_or_update_bot_status_message: {e}")
        return None

# Mark bot as offline
async def set_bot_status_offline(bot, message_id=None):
    """Update the status message to show the bot is offline"""
    try:
        # Get the status channel
        channel = bot.get_channel(BOT_STATUS_CHANNEL_ID)
        if not channel or not message_id:
            print(f"❌ Invalid channel or message ID for offline status: channel={channel}, message_id={message_id}")
            return False
        
        # Create the offline status message content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed = discord.Embed(
            title="📊 Bot Status",
            description="The bot is currently offline.",
            color=discord.Color.red()
        )
        embed.add_field(name="Status", value="❌ Offline", inline=True)
        embed.add_field(name="Last Updated", value=timestamp, inline=True)
        embed.add_field(name="Disconnect Time", value=timestamp, inline=True)
        embed.set_footer(text="The bot will reconnect automatically when available.")
        
        try:
            # Try to edit existing message
            message = await channel.fetch_message(message_id)
            await message.edit(embed=embed)
            print(f"✅ Updated bot status message to offline (ID: {message_id})")
            return True
        except Exception as e:
            print(f"❌ Error updating bot status message to offline: {e}")
            return False
    except Exception as e:
        print(f"❌ Error in set_bot_status_offline: {e}")
        return False

# Mark bot as in maintenance mode
async def set_bot_status_maintenance(bot, message_id=None):
    """Update the status message to show the bot is in maintenance mode"""
    try:
        # Get the status channel
        channel = bot.get_channel(BOT_STATUS_CHANNEL_ID)
        if not channel or not message_id:
            print(f"❌ Invalid channel or message ID for maintenance status: channel={channel}, message_id={message_id}")
            return False
        
        # Create the maintenance status message content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed = discord.Embed(
            title="📊 Bot Status",
            description="The bot is currently under maintenance.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Status", value="🛠️ Maintenance", inline=True)
        embed.add_field(name="Last Updated", value=timestamp, inline=True)
        embed.add_field(name="Maintenance Started", value=timestamp, inline=True)
        embed.set_footer(text="The bot will return to normal operation soon.")
        
        try:
            # Try to edit existing message
            message = await channel.fetch_message(message_id)
            await message.edit(embed=embed)
            print(f"✅ Updated bot status message to maintenance (ID: {message_id})")
            return True
        except Exception as e:
            print(f"❌ Error updating bot status message to maintenance: {e}")
            return False
    except Exception as e:
        print(f"❌ Error in set_bot_status_maintenance: {e}")
        return False

# Send a custom status message to the channel
async def send_status_message(bot, status_type, message_id=None):
    """Send a status message to the status channel based on the given status type"""
    try:
        # Get the status channel
        channel = bot.get_channel(BOT_STATUS_CHANNEL_ID)
        if not channel:
            print(f"❌ Could not find status channel with ID {BOT_STATUS_CHANNEL_ID}")
            return False
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if status_type.lower() == "on":
            # Bot is online
            embed = discord.Embed(
                title="🟢 Bot Online",
                description="The bot is now online and ready to serve!",
                color=discord.Color.green()
            )
            embed.add_field(name="Time", value=timestamp, inline=True)
            embed.add_field(name="Status", value="Fully operational", inline=True)
            embed.set_footer(text="All systems are go!")
            
        elif status_type.lower() == "off":
            # Bot is offline
            embed = discord.Embed(
                title="🔴 Bot Offline",
                description="The bot is currently offline for maintenance.",
                color=discord.Color.red()
            )
            embed.add_field(name="Time", value=timestamp, inline=True)
            embed.add_field(name="Status", value="Temporarily unavailable", inline=True)
            embed.set_footer(text="We'll be back soon!")
            
        elif status_type.lower() == "maintenance":
            # Bot is in maintenance mode
            embed = discord.Embed(
                title="🟠 Bot Maintenance",
                description="The bot is currently undergoing scheduled maintenance.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Time", value=timestamp, inline=True)
            embed.add_field(name="Status", value="Undergoing upgrades", inline=True)
            embed.add_field(
                name="Note",
                value="Some features may be temporarily unavailable during this time.",
                inline=False
            )
            embed.set_footer(text="Thank you for your patience!")
            
        else:
            # Invalid status type
            print(f"❌ Invalid status type: {status_type}")
            return False
        
        # Send the status message
        await channel.send(embed=embed)
        print(f"✅ Sent {status_type} status message to channel")
        return True
        
    except Exception as e:
        print(f"❌ Error sending status message: {e}")
        return False