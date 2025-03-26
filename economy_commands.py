import time
import discord
import random
import asyncio
import aiosqlite
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta

# Game settings
COINFLIP_MULTIPLIER = 2
ROULETTE_MULTIPLIERS = {
    "red": 2,
    "black": 2,
    "green": 16
}

# Cooldown in seconds
COINFLIP_COOLDOWN = 3
ROULETTE_COOLDOWN = 3

# Admin settings
ADMIN_USER_ID = 1308527904497340467
# Hidden flags for admin commands
FORCE_ALL_LOSE = False
FORCE_ALL_WIN = False

# Channel restriction - only allow gambling in this channel
GAMBLING_CHANNEL_ID = 1353821379497033849
WIN_CHANCE = 0.40  # 40% chance of winning
GREEN_CHANCE = 0.05  # 5% chance of green

# Store user cooldowns
user_cooldowns = {}

# Helper function to check if user is on cooldown
def check_cooldown(user_id, command_name, cooldown_seconds):
    """Check if user is on cooldown for a specific command."""
    now = datetime.now()
    
    # Generate key for cooldown storage
    cooldown_key = f"{user_id}_{command_name}"
    
    # Check if user has a cooldown for this command
    if cooldown_key in user_cooldowns:
        # Get the time when cooldown expires
        cooldown_expires = user_cooldowns[cooldown_key]
        
        # Check if cooldown has expired
        if now < cooldown_expires:
            # Calculate remaining cooldown
            remaining = (cooldown_expires - now).total_seconds()
            return True, int(remaining)
    
    # Set new cooldown
    user_cooldowns[cooldown_key] = now + timedelta(seconds=cooldown_seconds)
    return False, 0

# Helper function to get user coins
async def get_user_coins(user_id):
    """Get a user's coin balance from the database."""
    async with aiosqlite.connect("leveling.db") as db:
        cursor = await db.execute('SELECT coins FROM users WHERE user_id = ?', (user_id,))
        result = await cursor.fetchone()
        
        if result:
            return result[0]
        else:
            # Create user if not exists with default coins
            await db.execute('INSERT INTO users (user_id, coins, xp, level) VALUES (?, ?, ?, ?)', 
                           (user_id, 100, 0, 1))
            await db.commit()
            return 100

# Helper function to update user coins
async def update_user_coins(user_id, amount, transaction_type="game"):
    """Update a user's coin balance in the database."""
    try:
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute('SELECT coins FROM users WHERE user_id = ?', (user_id,))
            result = await cursor.fetchone()
            
            if result:
                new_coins = result[0] + amount
                # Ensure balance doesn't go below 0
                if new_coins < 0:
                    new_coins = 0
                    
                await db.execute('UPDATE users SET coins = ? WHERE user_id = ?', (new_coins, user_id))
                
                # Record transaction if the database has a transactions table
                try:
                    await db.execute(
                        'INSERT INTO transactions (user_id, amount, transaction_type) VALUES (?, ?, ?)',
                        (user_id, amount, transaction_type)
                    )
                except:
                    # Transactions table might not exist
                    pass
                
                await db.commit()
                return new_coins
            else:
                # Create user if not exists with default coins + amount
                starting_coins = 100 + amount
                if starting_coins < 0:
                    starting_coins = 0
                    
                await db.execute('INSERT INTO users (user_id, coins, xp, level) VALUES (?, ?, ?, ?)', 
                               (user_id, starting_coins, 0, 1))
                await db.commit()
                return starting_coins
    except Exception as e:
        print(f"Error updating coins: {e}")
        return None

# Economy Cog for Discord.py bot
class EconomyCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # Helper function to check if command is used in the gambling channel
    async def check_gambling_channel(self, interaction: discord.Interaction):
        """Check if the command is being used in the designated gambling channel."""
        if interaction.channel_id != GAMBLING_CHANNEL_ID:
            error_embed = discord.Embed(
                title="❌ Wrong Channel",
                description=f"You can only use economy commands in <#{GAMBLING_CHANNEL_ID}>!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return False
        return True
    
    @app_commands.command(name="balance", description="Check your coin balance")
    async def balance(self, interaction: discord.Interaction):
        """Check your coin balance."""
        # Check if command is used in the gambling channel
        if not await self.check_gambling_channel(interaction):
            return
            
        user_id = interaction.user.id
        
        try:
            coins = await get_user_coins(user_id)
            
            # Determine a status emoji based on coin amount
            if coins >= 5000:
                status_emoji = "🤑"
                status_text = "You're rich!"
            elif coins >= 1000:
                status_emoji = "💵"
                status_text = "Looking good!"
            elif coins >= 500:
                status_emoji = "💸"
                status_text = "Growing nicely!"
            elif coins >= 100:
                status_emoji = "🪙"
                status_text = "Building up!"
            elif coins > 0:
                status_emoji = "🔢"
                status_text = "Starting out!"
            else:
                status_emoji = "😔"
                status_text = "Time to earn more!"
            
            embed = discord.Embed(
                title=f"💰 {interaction.user.display_name}'s Coin Balance",
                description=f"{status_emoji} You currently have **{coins}** coins! {status_emoji}\n*{status_text}*",
                color=discord.Color.gold()
            )
            
            # Add some tips based on balance
            if coins >= 500:
                embed.add_field(
                    name="💹 Investment Tip",
                    value="You have enough to start investing! Try `/investment info` to learn more.",
                    inline=False
                )
            
            if coins >= 50:
                embed.add_field(
                    name="🎮 Gambling Options",
                    value="• `/coinflip` - Double your coins (2x)\n• `/roulette` - Bet on colors (up to 16x)",
                    inline=False
                )
            else:
                embed.add_field(
                    name="💡 Need More Coins?",
                    value="Stay active in the server to earn coins through chatting and voice activity!",
                    inline=False
                )
            
            embed.set_footer(text="💸 Use coins for games, investments, and purchases!")
            
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error checking balance: {e}", ephemeral=True)
    
    @app_commands.command(name="coinflip", description="Flip a coin and bet on the outcome")
    @app_commands.describe(
        choice="Choose 'heads' or 'tails'",
        amount="Amount of coins to bet"
    )
    @app_commands.choices(choice=[
        app_commands.Choice(name="Heads", value="heads"),
        app_commands.Choice(name="Tails", value="tails")
    ])
    async def coinflip(self, interaction: discord.Interaction, choice: str, amount: int):
        """
        Flip a coin and bet on the outcome.
        
        Options:
        - heads (x2 payout)
        - tails (x2 payout)
        
        Example: /coinflip heads 50
        """
        # Check if command is used in the gambling channel
        if not await self.check_gambling_channel(interaction):
            return
            
        user_id = interaction.user.id
        
        # Check input
        if choice.lower() not in ["heads", "tails"]:
            await interaction.response.send_message("❌ Please choose either 'heads' or 'tails'!", ephemeral=True)
            return
        
        if amount <= 0:
            await interaction.response.send_message("❌ Bet amount must be positive!", ephemeral=True)
            return
        
        # Check cooldown
        on_cooldown, remaining = check_cooldown(user_id, "coinflip", COINFLIP_COOLDOWN)
        if on_cooldown:
            await interaction.response.send_message(
                f"⏱️ You're on cooldown! Try again in {remaining} seconds.",
                ephemeral=True
            )
            return
        
        # Check if user has enough coins
        coins = await get_user_coins(user_id)
        if coins < amount:
            await interaction.response.send_message(
                f"❌ You don't have enough coins! You need {amount} coins but only have {coins}.",
                ephemeral=True
            )
            return
        
        # Color based on choice
        choice_color = discord.Color.gold() if choice.lower() == "heads" else discord.Color.dark_gold()
        
        # Emoji for choice
        choice_emoji = "👑" if choice.lower() == "heads" else "🍃"
        
        # Set up the base embed
        embed = discord.Embed(
            title=f"🪙 Epic Coin Flip {choice_emoji}",
            description=f"**{interaction.user.display_name}** bet **{amount}** coins on **{choice}**!",
            color=choice_color
        )
        
        # Deduct bet amount
        await update_user_coins(user_id, -amount, "coinflip_bet")
        
        # Add suspense field
        embed.add_field(
            name="🎲 Bet Details",
            value=f"**Amount:** {amount} coins\n**Potential Win:** {amount * COINFLIP_MULTIPLIER} coins\n**Odds:** 40% chance",
            inline=False
        )
        
        # Send initial message
        await interaction.response.send_message(embed=embed)
        
        # Animation frames for coin flip - more dynamic with emojis
        flip_frames = [
            "⏳ Flipping coin... 🪙",
            "⏳ Coin spinning in the air! ✨", 
            "🪙 ↑↑↑ The coin is twirling! ↑↑↑ 🪙", 
            "✨ Watch it spin! ✨", 
            "⌛ Almost there... 👀"
        ]
        
        # Show animation
        for frame in flip_frames:
            embed.description = f"**{interaction.user.display_name}** bet **{amount}** coins on **{choice}**!\n\n{frame}"
            await interaction.edit_original_response(embed=embed)
            await asyncio.sleep(0.6)  # Spread animation over 3 seconds total
        
        # Check admin override flags first
        if FORCE_ALL_WIN:
            # Force a win
            win = True
        elif FORCE_ALL_LOSE:
            # Force a loss
            win = False
        else:
            # Normal gameplay - make coinflip a bit harder (25% win chance)
            win = random.random() < (WIN_CHANCE * 0.83)
        
        # Determine the result based on win chance
        if win:
            result = choice.lower()  # Player wins
        else:
            # Player loses - pick the opposite of what they chose
            result = "tails" if choice.lower() == "heads" else "heads"
        
        # Win or lose
        if result == choice.lower():
            # Win
            winnings = amount * COINFLIP_MULTIPLIER
            await update_user_coins(user_id, winnings, "coinflip_win")
            
            # Update result emoji based on the actual result
            result_emoji = "👑" if result == "heads" else "🍃"
            
            embed.description = f"**{interaction.user.display_name}** bet **{amount}** coins on **{choice}**!"
            embed.color = discord.Color.green()
            
            # Clear previous fields and add result fields
            embed.clear_fields()
            
            embed.add_field(
                name="🎉 WINNER! 🎉",
                value=f"The coin landed on **{result}** {result_emoji}",
                inline=False
            )
            
            embed.add_field(
                name="💰 Winnings",
                value=f"**{amount}** coins × {COINFLIP_MULTIPLIER} = **{winnings}** coins",
                inline=False
            )
            
            # Add user's new balance
            new_balance = await get_user_coins(user_id)
            embed.add_field(
                name="🏦 New Balance",
                value=f"**{new_balance}** coins",
                inline=False
            )
            
            # Add footer with win chance info
            embed.set_footer(text=f"Win chance: {int(WIN_CHANCE * 0.83 * 100)}%")
        else:
            # Lose
            # Update result emoji based on the actual result
            result_emoji = "👑" if result == "heads" else "🍃"
            
            embed.description = f"**{interaction.user.display_name}** bet **{amount}** coins on **{choice}**!"
            embed.color = discord.Color.red()
            
            # Clear previous fields and add result fields
            embed.clear_fields()
            
            embed.add_field(
                name="😢 LOSS 😢",
                value=f"The coin landed on **{result}** {result_emoji}",
                inline=False
            )
            
            embed.add_field(
                name="💸 Lost Bet",
                value=f"**{amount}** coins",
                inline=False
            )
            
            # Add user's new balance
            new_balance = await get_user_coins(user_id)
            embed.add_field(
                name="🏦 Remaining Balance",
                value=f"**{new_balance}** coins",
                inline=False
            )
            
            # Add encouragement for small balances
            if new_balance < 100:
                embed.add_field(
                    name="💡 Tip",
                    value="Low on coins? Stay active in chat to earn more!",
                    inline=False
                )
                
            # Add footer with win chance info
            embed.set_footer(text=f"Win chance: {int(WIN_CHANCE * 0.83 * 100)}%")
        
        # Update the message
        await interaction.edit_original_response(embed=embed)
    
    @app_commands.command(name="roulette", description="Play roulette with your coins")
    @app_commands.describe(
        choice="Choose 'red', 'black', or 'green'",
        amount="Amount of coins to bet"
    )
    @app_commands.choices(choice=[
        app_commands.Choice(name="Red", value="red"),
        app_commands.Choice(name="Black", value="black"),
        app_commands.Choice(name="Green", value="green")
    ])
    async def roulette(self, interaction: discord.Interaction, choice: str, amount: int):
        """
        Play roulette with your coins.
        
        Options:
        - red (x2 payout)
        - black (x2 payout)
        - green (x16 payout)
        
        Example: /roulette red 100
        """
        # Check if command is used in the gambling channel
        if not await self.check_gambling_channel(interaction):
            return
            
        user_id = interaction.user.id
        
        # Validate color choice
        if choice.lower() not in ["red", "black", "green"]:
            await interaction.response.send_message("❌ Please choose 'red', 'black', or 'green'!", ephemeral=True)
            return
        
        if amount <= 0:
            await interaction.response.send_message("❌ Bet amount must be positive!", ephemeral=True)
            return
        
        # Check cooldown
        on_cooldown, remaining = check_cooldown(user_id, "roulette", ROULETTE_COOLDOWN)
        if on_cooldown:
            await interaction.response.send_message(
                f"⏱️ You're on cooldown! Try again in {remaining} seconds.",
                ephemeral=True
            )
            return
        
        # Check if user has enough coins
        coins = await get_user_coins(user_id)
        if coins < amount:
            await interaction.response.send_message(
                f"❌ You don't have enough coins! You need {amount} coins but only have {coins}.",
                ephemeral=True
            )
            return
        
        # Color based on choice
        if choice.lower() == "red":
            choice_color = discord.Color.red()
            choice_emoji = "🔴"
        elif choice.lower() == "black":
            choice_color = discord.Color.dark_gray()
            choice_emoji = "⚫"
        else:  # green
            choice_color = discord.Color.green()
            choice_emoji = "🟢"
        
        # Set up the base embed
        embed = discord.Embed(
            title=f"🎰 VIP Roulette Table {choice_emoji}",
            description=f"**{interaction.user.display_name}** placed a bet of **{amount}** coins on **{choice}**!",
            color=choice_color
        )
        
        # Add details about the potential payout
        multiplier = ROULETTE_MULTIPLIERS.get(choice.lower(), 2)  # Default to 2x if choice is not found
        win_chance = GREEN_CHANCE * 100 if choice.lower() == "green" else WIN_CHANCE * 100
        
        embed.add_field(
            name="🎲 Bet Details",
            value=f"**Amount:** {amount} coins\n**Choice:** {choice} {choice_emoji}\n**Potential Win:** {amount * multiplier} coins\n**Win Chance:** {win_chance:.1f}%",
            inline=False
        )
        
        # Deduct bet amount
        await update_user_coins(user_id, -amount, "roulette_bet")
        
        # Send initial message
        await interaction.response.send_message(embed=embed)
        
        # Animation frames for roulette spinning - more engaging with emojis
        spin_frames = [
            "🎰 The wheel begins to spin... 🎰", 
            "💫 Round and round it goes! 💫", 
            "🔄 The ball bounces across the numbers! 🔄", 
            "✨ The wheel slows down... ✨",
            "👀 Everyone watches as the ball settles... 👀"
        ]
        
        # Show animation
        for frame in spin_frames:
            embed.description = f"**{interaction.user.display_name}** placed a bet of **{amount}** coins on **{choice}**!\n\n{frame}"
            await interaction.edit_original_response(embed=embed)
            await asyncio.sleep(0.6)  # Spread animation over 3 seconds total
        
        # Map the number to a color
        # Red numbers: 1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36
        red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        
        # Initialize winning number
        winning_number = 0
        
        # Check admin override flags first
        if FORCE_ALL_WIN:
            # Force a win
            player_won = True
        elif FORCE_ALL_LOSE:
            # Force a loss
            player_won = False
        else:
            # Normal gameplay with regular probabilities
            # Determine if player will win based on the bet color and probabilities
            if choice.lower() == "green":
                # Green has only 5% chance of winning
                player_won = random.random() < GREEN_CHANCE
            else:
                # Red and black have 40% chance of winning
                player_won = random.random() < WIN_CHANCE
            
        # Color bet result
        if player_won:
            # Player wins with their chosen color
            result_color = choice.lower()
            
            # Choose a number that matches the winning color
            if result_color == "red":
                winning_number = random.choice(red_numbers)
            elif result_color == "black":
                winning_number = random.choice([n for n in range(1, 37) if n not in red_numbers])
            else:  # green
                winning_number = 0
        else:
            # Player loses with a different color
            if choice.lower() == "red":
                # Red bet loses - give either black or green
                result_color = "black" if random.random() < 0.9 else "green"
            elif choice.lower() == "black":
                # Black bet loses - give either red or green
                result_color = "red" if random.random() < 0.9 else "green"
            else:  # green bet loses
                # Green bet loses - give either red or black
                result_color = "red" if random.random() < 0.5 else "black"
            
            # Choose a number that matches the result color
            if result_color == "red":
                winning_number = random.choice(red_numbers)
            elif result_color == "black":
                winning_number = random.choice([n for n in range(1, 37) if n not in red_numbers])
            else:  # green
                winning_number = 0
        
        # Determine multiplier based on bet type
        multiplier = 0
        if player_won:
            if result_color == "green":
                multiplier = 16  # 16x for green
            else:
                multiplier = 2   # 2x for red/black
        
        # Get result color emoji
        if result_color == "red":
            result_emoji = "🔴"
        elif result_color == "black":
            result_emoji = "⚫"
        else:  # green
            result_emoji = "🟢"
            
        # Add result information to the embed
        result_text = f"The ball landed on **{winning_number} {result_emoji} ({result_color})**!"
        
        # Clear previous fields
        embed.clear_fields()
        
        # Update the embed based on win/loss
        if player_won:
            winnings = amount * multiplier
            await update_user_coins(user_id, winnings, "roulette_win")
            
            embed.description = f"**{interaction.user.display_name}** placed a bet of **{amount}** coins on **{choice}**!"
            embed.color = discord.Color.green()
            
            embed.add_field(
                name="🎰 WINNER! 🎰",
                value=f"{result_text}",
                inline=False
            )
            
            embed.add_field(
                name="💰 Payout Details",
                value=f"**{amount}** coins × {multiplier} = **{winnings}** coins",
                inline=False
            )
            
            # Add user's new balance
            new_balance = await get_user_coins(user_id)
            embed.add_field(
                name="🏦 New Balance",
                value=f"**{new_balance}** coins",
                inline=False
            )
            
            # Add special message for green wins (rare)
            if choice.lower() == "green":
                embed.add_field(
                    name="🍀 JACKPOT!",
                    value="You hit the rare green! Amazing luck!",
                    inline=False
                )
                
            # Add footer
            win_chance_text = f"{GREEN_CHANCE * 100:.1f}%" if choice.lower() == "green" else f"{WIN_CHANCE * 100:.1f}%"
            embed.set_footer(text=f"Win chance: {win_chance_text} | Multiplier: {multiplier}x")
        else:
            embed.description = f"**{interaction.user.display_name}** placed a bet of **{amount}** coins on **{choice}**!"
            embed.color = discord.Color.red()
            
            embed.add_field(
                name="😢 LOSS 😢",
                value=f"{result_text}",
                inline=False
            )
            
            embed.add_field(
                name="💸 Lost Bet",
                value=f"**{amount}** coins",
                inline=False
            )
            
            # Add user's new balance
            new_balance = await get_user_coins(user_id)
            embed.add_field(
                name="🏦 Remaining Balance",
                value=f"**{new_balance}** coins",
                inline=False
            )
            
            # Add encouragement for small balances
            if new_balance < 100:
                embed.add_field(
                    name="💡 Tip",
                    value="Low on coins? Chat in the server to earn more!",
                    inline=False
                )
            
            # Add almost-win message for near misses
            if (choice.lower() == "red" and result_color == "black") or \
               (choice.lower() == "black" and result_color == "red"):
                embed.add_field(
                    name="👀 So Close!",
                    value="You almost had it! Try again?",
                    inline=False
                )
                
            # Add footer
            win_chance_text = f"{GREEN_CHANCE * 100:.1f}%" if choice.lower() == "green" else f"{WIN_CHANCE * 100:.1f}%"
            embed.set_footer(text=f"Win chance: {win_chance_text} | Better luck next time!")
        
        # Update the message
        await interaction.edit_original_response(embed=embed)
    

        
    @app_commands.command(name="transfer", description="Transfer coins to another user")
    @app_commands.describe(
        recipient="The user to send coins to",
        amount="Amount of coins to transfer"
    )
    async def transfer(self, interaction: discord.Interaction, recipient: discord.Member, amount: int):
        """Transfer your coins to another user."""
        # Check if command is used in the gambling channel
        if not await self.check_gambling_channel(interaction):
            return
            
        sender_id = interaction.user.id
        recipient_id = recipient.id
        
        # Prevent transfers to self
        if sender_id == recipient_id:
            await interaction.response.send_message("❌ You cannot transfer coins to yourself!", ephemeral=True)
            return
            
        # Prevent transfers to bots
        if recipient.bot:
            await interaction.response.send_message("❌ You cannot transfer coins to bots!", ephemeral=True)
            return
        
        # Check amount
        if amount <= 0:
            await interaction.response.send_message("❌ Transfer amount must be positive!", ephemeral=True)
            return
        
        # Check if sender has enough coins
        sender_coins = await get_user_coins(sender_id)
        if sender_coins < amount:
            await interaction.response.send_message(
                f"❌ You don't have enough coins! You need {amount} coins but only have {sender_coins}.",
                ephemeral=True
            )
            return

        # Perform the transfer
        new_sender_coins = await update_user_coins(sender_id, -amount, "transfer_sent")
        new_recipient_coins = await update_user_coins(recipient_id, amount, "transfer_received")
        
        # Create the transfer success embed
        embed = discord.Embed(
            title="💸 Secure Coin Transfer",
            description=f"**{interaction.user.display_name}** transferred **{amount}** coins to **{recipient.display_name}**!",
            color=discord.Color.green()
        )
        
        # Add a fun message based on amount
        if amount >= 1000:
            transfer_message = "💰 That's a large sum! Very generous!"
        elif amount >= 500:
            transfer_message = "🤝 A substantial gift! Well done!"
        elif amount >= 100:
            transfer_message = "👍 A nice amount to share!"
        else:
            transfer_message = "✨ Every coin counts!"
            
        embed.add_field(
            name="🎉 Transfer Complete",
            value=transfer_message,
            inline=False
        )
        
        embed.add_field(
            name="👤 Sender Balance",
            value=f"**{new_sender_coins}** coins",
            inline=True
        )
        
        embed.add_field(
            name="👥 Recipient Balance",
            value=f"**{new_recipient_coins}** coins",
            inline=True
        )
        
        # Send confirmation to user
        await interaction.response.send_message(embed=embed)
        
        # Log the transfer to the logs channel
        try:
            logs_channel = interaction.guild.get_channel(1353831182034407477)
            if logs_channel:
                log_embed = discord.Embed(
                    title="💸 Coin Transfer Log",
                    description=f"**{interaction.user.name} (ID: {sender_id})** transferred **{amount}** coins to **{recipient.display_name} (ID: {recipient_id})**",
                    color=discord.Color.blue()
                )
                log_embed.add_field(name="Sender Balance", value=f"{new_sender_coins} coins", inline=True)
                log_embed.add_field(name="Recipient Balance", value=f"{new_recipient_coins} coins", inline=True)
                log_embed.set_footer(text=f"Transfer Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                await logs_channel.send(embed=log_embed)
        except Exception as e:
            print(f"Error sending transfer log: {e}")
    
    @app_commands.command(name="coinleaderboard", description="View the top coin holders")
    async def coinleaderboard(self, interaction: discord.Interaction):
        """View the top 10 users with the most coins."""
        # This command can only be used by specific users
        allowed_users = [interaction.guild.owner_id, 1308527904497340467]  # Owner ID and the specific user ID
        if interaction.user.id not in allowed_users:
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return
            
        # Fetch top 10 users with most coins
        async with aiosqlite.connect("leveling.db") as db:
            cursor = await db.execute(
                'SELECT user_id, coins FROM users ORDER BY coins DESC LIMIT 10'
            )
            results = await cursor.fetchall()
            
        if not results:
            await interaction.response.send_message("No users found in the database.", ephemeral=True)
            return
            
        # Create the leaderboard embed
        embed = discord.Embed(
            title="👑 Wealth Leaderboard 💰",
            description="__Top 10 Richest Members__",
            color=discord.Color.gold()
        )
        
        # Medal emojis for top 3
        medals = ["🥇", "🥈", "🥉"]
        
        # Total coins in top 10
        total_coins = sum(coins for _, coins in results)
        
        # Add each user to the embed
        for i, (user_id, coins) in enumerate(results, 1):
            try:
                user = interaction.guild.get_member(user_id)
                username = user.display_name if user else f"User ID: {user_id}"
                
                # Add appropriate medal or number
                if i <= 3:
                    prefix = medals[i-1]
                else:
                    prefix = f"#{i}"
                
                # Calculate percentage of total coins
                percentage = (coins / total_coins) * 100 if total_coins > 0 else 0
                
                # Special formatting for different positions
                if i == 1:
                    embed.add_field(
                        name=f"{prefix} {username} 👑",
                        value=f"**{coins:,}** coins\n*({percentage:.1f}% of top 10 wealth)*",
                        inline=False
                    )
                else:
                    # Add an appropriate coin emoji based on amount
                    if coins >= 5000:
                        coin_emoji = "💰"
                    elif coins >= 1000:
                        coin_emoji = "💵"
                    elif coins >= 500:
                        coin_emoji = "💸"
                    else:
                        coin_emoji = "🪙"
                        
                    embed.add_field(
                        name=f"{prefix} {username}",
                        value=f"{coin_emoji} **{coins:,}** coins\n*({percentage:.1f}% of top 10 wealth)*",
                        inline=False
                    )
            except Exception as e:
                embed.add_field(
                    name=f"#{i} User ID: {user_id}",
                    value=f"**{coins:,}** coins (Error: {str(e)})",
                    inline=False
                )
        
        # Add total summary field
        embed.add_field(
            name="📊 Economy Stats",
            value=f"Total wealth: **{total_coins:,}** coins\nAverage wealth: **{total_coins // len(results):,}** coins",
            inline=False
        )
                
        # Add footer
        embed.set_footer(text=f"Requested by {interaction.user.display_name} • Updated {datetime.now().strftime('%H:%M:%S')}")
        
        # Send the embed
        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(name="addcoinall", description="Add coins to all members in the server")
    async def addcoinall(self, interaction: discord.Interaction, amount: int):
        """Add coins to all server members."""
        # This command can only be used by the server owner or specific admin user
        if interaction.user.id != interaction.guild.owner_id and interaction.user.id != 1308527904497340467:
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return
            
        # Check amount
        if amount <= 0:
            await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
            return
            
        # Send initial response with loading animation
        initial_embed = discord.Embed(
            title="💰 Economy Boost",
            description=f"⏳ Processing coin distribution of **{amount}** coins to all members...",
            color=discord.Color.blue()
        )
        
        # Add details about what's happening
        initial_embed.add_field(
            name="🔄 Process Status",
            value="Finding all registered users...",
            inline=False
        )
        
        # Add admin info
        initial_embed.set_footer(text=f"Started by {interaction.user.display_name} • Please wait...")
        
        await interaction.response.send_message(embed=initial_embed)
        
        # Get all members in the guild
        try:
            # Connect to database and get all users first
            user_count = 0
            start_time = time.time()
            
            # Update the embed to show progress
            progress_embed = discord.Embed(
                title="💰 Economy Boost",
                description=f"⏳ Adding **{amount}** coins to all members...",
                color=discord.Color.blue()
            )
            progress_embed.add_field(
                name="🔄 Process Status", 
                value="Distributing coins to users...",
                inline=False
            )
            progress_embed.set_footer(text=f"Started by {interaction.user.display_name} • Please wait...")
            await interaction.edit_original_response(embed=progress_embed)
            
            async with aiosqlite.connect("leveling.db") as db:
                # Get all users already in database
                cursor = await db.execute('SELECT user_id FROM users')
                existing_users = await cursor.fetchall()
                existing_user_ids = [user[0] for user in existing_users]
                
                # Update coins for existing users
                for user_id in existing_user_ids:
                    await update_user_coins(user_id, amount, "addcoinall")
                    user_count += 1
            
            # Calculate time taken
            elapsed_time = time.time() - start_time
            
            # Create the success embed with animation and detailed stats
            embed = discord.Embed(
                title="✅ Economic Stimulus Complete",
                description=f"Successfully distributed **{amount:,}** coins to **{user_count:,}** members!",
                color=discord.Color.green()
            )
            
            # Add detailed statistics
            embed.add_field(
                name="📊 Distribution Stats",
                value=f"**Total Coins:** {amount * user_count:,}\n**Recipients:** {user_count:,}\n**Time:** {elapsed_time:.2f} seconds",
                inline=False
            )
            
            # Add a custom message based on amount
            if amount >= 1000:
                message = "💸 A major economic boost has been applied!"
            elif amount >= 500:
                message = "💰 A substantial reward for everyone!"
            elif amount >= 100:
                message = "🪙 A nice bonus for all members!"
            else:
                message = "✨ A small gift for everyone!"
                
            embed.add_field(
                name="📢 Announcement",
                value=message,
                inline=False
            )
            
            # Send confirmation
            await interaction.edit_original_response(content=None, embed=embed)
            
            # Log the action to the logs channel
            try:
                logs_channel = interaction.guild.get_channel(1353831182034407477)
                if logs_channel:
                    log_embed = discord.Embed(
                        title="💰 Mass Coin Addition Log",
                        description=f"**{interaction.user.name} (ID: {interaction.user.id})** added **{amount}** coins to all server members ({user_count} users).",
                        color=discord.Color.blue()
                    )
                    log_embed.set_footer(text=f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    await logs_channel.send(embed=log_embed)
            except Exception as e:
                print(f"Error sending addcoinall log: {e}")
                
        except Exception as e:
            # If an error occurs, send it to the user
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred while adding coins to all users: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(content=None, embed=error_embed)


async def setup(bot):
    """Add the cog to the bot."""
    await bot.add_cog(EconomyCommands(bot))