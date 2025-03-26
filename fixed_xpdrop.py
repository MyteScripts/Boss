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
        
        # Update user data in database using our connection pool
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