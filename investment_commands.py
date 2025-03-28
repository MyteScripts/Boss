import discord
import asyncio
import aiosqlite
import random
from datetime import datetime, timedelta
from discord import app_commands, ui
from discord.ext import commands, tasks

# Investment types and their properties with cool emojis
INVESTMENTS = {
    "grocery_store": {
        "name": "🛒 Grocery Store",
        "cost": 500,
        "hourly_return": 10,
        "max_holding": 200,
        "maintenance_drain": 3,  # percentage per hour
        "risk_level": "Low",
        "risk_color": discord.Color.green(),
        "emoji": "🛒",
        "description": "A small neighborhood grocery store selling essential items."
    },
    "retail_shop": {
        "name": "🛍️ Retail Shop",
        "cost": 1200,
        "hourly_return": 25,
        "max_holding": 300,
        "maintenance_drain": 4,
        "risk_level": "Medium",
        "risk_color": discord.Color.yellow(),
        "emoji": "🛍️",
        "description": "A trendy retail shop selling clothing and accessories."
    },
    "restaurant": {
        "name": "🍽️ Restaurant",
        "cost": 2000,
        "hourly_return": 60,
        "max_holding": 400,
        "maintenance_drain": 5,
        "risk_level": "High",
        "risk_color": discord.Color.red(),
        "emoji": "🍽️",
        "description": "A popular restaurant with a diverse menu and loyal customers."
    },
    "private_company": {
        "name": "🏢 Private Company",
        "cost": 3500,
        "hourly_return": 100,
        "max_holding": 600,
        "maintenance_drain": 3.5,
        "risk_level": "Medium",
        "risk_color": discord.Color.orange(),
        "emoji": "🏢",
        "description": "A thriving tech company with innovative products."
    },
    "real_estate": {
        "name": "🏘️ Real Estate",
        "cost": 5000,
        "hourly_return": 50,
        "max_holding": 300,
        "maintenance_drain": 2.5,
        "risk_level": "Low",
        "risk_color": discord.Color.green(),
        "emoji": "🏘️",
        "description": "Prime property investments that generate steady rental income."
    }
}

# Risk events that can occur when maintenance is low (with cool emojis)
RISK_EVENTS = {
    "grocery_store": [
        "📦 A supply chain issue has affected your grocery store! Shipments delayed.",
        "🧪 Health inspectors found violations in your grocery store. Heavy fines imposed!",
        "❄️ Refrigeration units failed in your grocery store. All frozen products spoiled!",
        "🔥 A fire broke out in your grocery store! Stock destroyed and shop damaged.",
        "🌋 An earthquake damaged your grocery store structure! Repairs needed urgently.",
        "🐜 Pest infestation discovered in your grocery store! Health department involved."
    ],
    "retail_shop": [
        "🔨 Your retail shop was broken into overnight! Merchandise stolen.",
        "💻 Your retail shop's inventory system crashed. Records lost!",
        "⚡ A power outage damaged electronics in your retail shop. Insurance denied!",
        "🔥 A fire spread from neighboring shop and damaged your retail inventory!",
        "🌋 An earthquake damaged your retail shop! Expensive displays destroyed.",
        "🐜 Termites discovered in your retail shop's wooden fixtures! Store closed."
    ],
    "restaurant": [
        "🔥 A fire broke out in your restaurant kitchen! Equipment destroyed.",
        "🤢 Food poisoning outbreak traced to your restaurant! Lawsuits pending.",
        "🚫 Health department shut down your restaurant temporarily! Reputation damaged.",
        "🔥 A major fire destroyed most of your restaurant! Insurance processing delayed.",
        "🌋 An earthquake damaged your restaurant building! Structure deemed unsafe.",
        "🐜 Cockroach infestation discovered in your restaurant! Health code violations."
    ],
    "private_company": [
        "⚖️ Your private company faced a major lawsuit. Legal fees skyrocketed!",
        "👔 A key executive resigned from your company taking clients with them!",
        "📉 Your private company lost a major client contract. Stocks plummeting!",
        "🔥 A fire in your company server room destroyed critical data! Recovery costly.",
        "🌋 An earthquake damaged your company headquarters! Operations disrupted.",
        "🐜 Digital infestation! Your company's network hit by ransomware attack."
    ],
    "real_estate": [
        "🛠️ Your real estate property needs emergency repairs. Plumbing disaster!",
        "💰 A tenant damaged your property and disappeared without paying!",
        "📋 Property taxes increased unexpectedly on your real estate. Budget ruined!",
        "🔥 A fire damaged multiple units in your real estate property! Insurance issues.",
        "🌋 An earthquake severely damaged your real estate investment! Building condemned.",
        "🐜 Termite infestation discovered throughout your real estate property! Extensive damage."
    ]
}

# Set up tasks
investment_tasks = {}

# Button class for emergency response to risk events
class EmergencyResponseView(ui.View):
    def __init__(self, user_id, investment_type, event_type):
        super().__init__(timeout=86400)  # 24 hour timeout
        self.user_id = user_id
        self.investment_type = investment_type
        self.event_type = event_type
        
    @ui.button(label="Quick Response ($$$)", style=discord.ButtonStyle.danger, emoji="🚨", row=0)
    async def quick_respond_button(self, interaction: discord.Interaction, button: ui.Button):
        # Only allow the investment owner to use this button
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your business emergency!", ephemeral=True)
            return
            
        # Calculate emergency response cost - higher for quick response
        investment = INVESTMENTS[self.investment_type]
        response_cost = investment["hourly_return"] * 8  # 8x hourly income for quick emergency response
        
        await self.handle_response(interaction, response_cost, 50, "Quick")
    
    @ui.button(label="Standard Response ($$)", style=discord.ButtonStyle.primary, emoji="🔧", row=0)
    async def standard_respond_button(self, interaction: discord.Interaction, button: ui.Button):
        # Only allow the investment owner to use this button
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your business emergency!", ephemeral=True)
            return
            
        # Calculate emergency response cost - standard
        investment = INVESTMENTS[self.investment_type]
        response_cost = investment["hourly_return"] * 5  # 5x hourly income for standard response
        
        await self.handle_response(interaction, response_cost, 35, "Standard")
    
    @ui.button(label="Basic Response ($)", style=discord.ButtonStyle.secondary, emoji="🧰", row=1)
    async def basic_respond_button(self, interaction: discord.Interaction, button: ui.Button):
        # Only allow the investment owner to use this button
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your business emergency!", ephemeral=True)
            return
            
        # Calculate emergency response cost - cheaper but less effective
        investment = INVESTMENTS[self.investment_type]
        response_cost = investment["hourly_return"] * 3  # 3x hourly income for basic response
        
        await self.handle_response(interaction, response_cost, 20, "Basic")
    
    @ui.button(label="Ignore Emergency", style=discord.ButtonStyle.gray, emoji="⏭️", row=1)
    async def ignore_button(self, interaction: discord.Interaction, button: ui.Button):
        # Only allow the investment owner to use this button
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your business emergency!", ephemeral=True)
            return
        
        # Confirm the user wants to ignore the emergency
        embed = discord.Embed(
            title="⚠️ Confirm Ignoring Emergency",
            description="Are you sure you want to ignore this business emergency? Your business will remain closed until you reopen it with the buy command.",
            color=discord.Color.red()
        )
        
        # Create confirmation buttons
        class ConfirmView(discord.ui.View):
            def __init__(self, parent_view):
                super().__init__(timeout=60)
                self.parent_view = parent_view
            
            @discord.ui.button(label="Yes, Ignore Emergency", style=discord.ButtonStyle.red)
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.parent_view.user_id:
                    await interaction.response.send_message("This isn't your business!", ephemeral=True)
                    return
                
                # Update the original message
                for child in self.parent_view.children:
                    child.disabled = True
                await interaction.message.edit(view=self.parent_view)
                
                # Confirm the ignore action
                result_embed = discord.Embed(
                    title="💔 Emergency Ignored",
                    description=f"You've chosen to ignore the emergency at your {INVESTMENTS[self.parent_view.investment_type]['name']}. The business remains closed.",
                    color=discord.Color.dark_gray()
                )
                result_embed.add_field(
                    name="🔄 Reopen",
                    value=f"To reopen your business, use `/investment buy {self.parent_view.investment_type}`",
                    inline=False
                )
                
                await interaction.response.edit_message(embed=result_embed, view=None)
            
            @discord.ui.button(label="No, Go Back", style=discord.ButtonStyle.green)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.parent_view.user_id:
                    await interaction.response.send_message("This isn't your business!", ephemeral=True)
                    return
                
                # Just close this confirmation view
                await interaction.response.edit_message(embed=interaction.message.embeds[0], view=self.parent_view)
        
        await interaction.response.send_message(embed=embed, view=ConfirmView(self), ephemeral=True)
        
    async def handle_response(self, interaction, response_cost, maintenance_level, response_type):
        # Check if user has enough coins
        async with aiosqlite.connect("leveling.db") as db:
            # First check current maintenance level
            cursor = await db.execute('''
                SELECT maintenance
                FROM investments
                WHERE user_id = ? AND investment_type = ? AND active = 1
            ''', (self.user_id, self.investment_type))
            
            inv_result = await cursor.fetchone()
            if not inv_result:
                await interaction.response.send_message(
                    "This business no longer exists or has been deactivated.",
                    ephemeral=True
                )
                return
            
            current_maintenance = inv_result[0]
            
            # Only allow emergency responses when maintenance is 0-50%
            # This ensures repairs happen only manually when needed
            if current_maintenance > 50:
                await interaction.response.send_message(
                    f"Emergency responses are only needed when maintenance is below 50%. Your business is currently at {current_maintenance:.1f}% maintenance.",
                    ephemeral=True
                )
                return
            
            # Now check if user has enough coins
            cursor = await db.execute('SELECT coins FROM users WHERE user_id = ?', (self.user_id,))
            result = await cursor.fetchone()
            
            if not result or result[0] < response_cost:
                await interaction.response.send_message(
                    f"You don't have enough coins for a {response_type.lower()} emergency response! Cost: {response_cost} coins.",
                    ephemeral=True
                )
                return
            
            # IMPORTANT: Emergency responses don't automatically fix the business
            # They just make it active again so the user can manually repair it
            # with the /investment maintain command
            
            # Deduct the cost
            await db.execute(
                'UPDATE users SET coins = coins - ? WHERE user_id = ?',
                (response_cost, self.user_id)
            )
            
            # Set the business as active, but DON'T increase maintenance
            # This ensures the user must manually repair with /investment maintain
            await db.execute('''
                UPDATE investments
                SET active = 1
                WHERE user_id = ? AND investment_type = ?
            ''', (self.user_id, self.investment_type))
            
            # Log the emergency response
            await db.execute('''
                INSERT INTO investment_logs 
                (user_id, investment_type, event_type, description, coins_affected, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (self.user_id, self.investment_type, "emergency_response", 
                 f"{response_type} emergency response to {self.event_type} - Business reactivated but needs maintenance", 
                 -response_cost, discord.utils.utcnow().timestamp()))
            
            await db.commit()
            
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        
        # Send a success message
        embed = discord.Embed(
            title=f"🚒 {response_type} Emergency Response Successful!",
            description=f"You've addressed the emergency at your {INVESTMENTS[self.investment_type]['name']}!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="💰 Response Cost",
            value=f"{response_cost} coins"
        )
        embed.add_field(
            name="🔧 Current Status",
            value=f"Business reactivated (current maintenance: {current_maintenance:.1f}%)"
        )
        embed.add_field(
            name="⚠️ IMPORTANT", 
            value=f"Your business still needs repairs! Use `/investment maintain {self.investment_type}` to restore it.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

async def setup_investment_tables():
    """Create necessary database tables for investments if they don't exist."""
    async with aiosqlite.connect("leveling.db") as db:
        # Create investments table to track user investments
        await db.execute('''
            CREATE TABLE IF NOT EXISTS investments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                investment_type TEXT NOT NULL,
                purchase_time REAL NOT NULL,
                maintenance INTEGER NOT NULL DEFAULT 100,
                collected_coins INTEGER NOT NULL DEFAULT 0,
                last_update_time REAL NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(user_id, investment_type)
            )
        ''')
        
        # Create investment_logs table to track major events
        await db.execute('''
            CREATE TABLE IF NOT EXISTS investment_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                investment_type TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                coins_affected INTEGER,
                timestamp REAL NOT NULL
            )
        ''')
        
        await db.commit()

async def update_investments():
    """Update all active investments with hourly income and maintenance drain."""
    now = datetime.now().timestamp()
    one_hour_ago = (datetime.now() - timedelta(hours=1)).timestamp()
    
    # Get all active investments
    async with aiosqlite.connect("leveling.db") as db:
        cursor = await db.execute('''
            SELECT id, user_id, investment_type, maintenance, collected_coins, last_update_time
            FROM investments
            WHERE active = 1 AND last_update_time < ?
        ''', (one_hour_ago,))
        
        investments = await cursor.fetchall()
        for inv_id, user_id, inv_type, maintenance, collected_coins, last_update_time in investments:
            if inv_type not in INVESTMENTS:
                continue
                
            investment = INVESTMENTS[inv_type]
            hours_passed = (now - last_update_time) / 3600  # Convert seconds to hours
            
            if hours_passed < 1:
                continue  # Skip if less than an hour has passed
                
            # Calculate how many full hours have passed
            full_hours_passed = int(hours_passed)
            
            # Calculate new maintenance level
            drain_per_hour = investment["maintenance_drain"]
            new_maintenance = max(0, maintenance - (drain_per_hour * full_hours_passed))
            
            # Calculate coins earned (only if maintenance is at least 25%)
            new_coins = collected_coins
            if maintenance >= 25:
                hourly_return = investment["hourly_return"]
                coins_earned = hourly_return * full_hours_passed
                max_holding = investment["max_holding"]
                new_coins = min(max_holding, collected_coins + coins_earned)
            
            # Send maintenance reminder if maintenance is between 0% and 50%
            if 0 < new_maintenance <= 50 and (maintenance > 50 or maintenance > new_maintenance):
                # Only send reminder if maintenance just dropped below 50% or if it continues to decline
                try:
                    # Get instance of bot from the global namespace 
                    from main import bot
                    
                    # Calculate hours until shutdown
                    hours_until_critical = new_maintenance / drain_per_hour
                    hours_until_zero = new_maintenance / drain_per_hour
                    
                    # Create embedded message with alert
                    if new_maintenance <= 25:
                        # Critical alert - maintenance below 25%
                        embed = discord.Embed(
                            title="🔴 CRITICAL Maintenance Alert!",
                            description=f"Your {INVESTMENTS[inv_type]['name']} needs urgent maintenance!",
                            color=discord.Color.red()
                        )
                        embed.add_field(
                            name="⚠️ Current Maintenance",
                            value=f"**{new_maintenance:.1f}%** (Critical level)",
                            inline=True
                        )
                    else:
                        # Warning alert - maintenance between 25% and 50%
                        embed = discord.Embed(
                            title="🟠 Maintenance Warning",
                            description=f"Your {INVESTMENTS[inv_type]['name']} needs maintenance soon.",
                            color=discord.Color.orange()
                        )
                        embed.add_field(
                            name="⚠️ Current Maintenance",
                            value=f"**{new_maintenance:.1f}%**",
                            inline=True
                        )
                    
                    embed.add_field(
                        name="⏰ Time Until Shutdown",
                        value=f"~{hours_until_zero:.1f} hours",
                        inline=True
                    )
                    
                    # Add maintenance instructions
                    cost_to_repair = int(investment["hourly_return"] * 0.5)  # 50% of hourly income for repair (matching maintain action cost)
                    embed.add_field(
                        name="🔧 Repair Instructions",
                        value=f"Use `/investment maintain {inv_type}` to restore maintenance. Cost: **{cost_to_repair}** coins.",
                        inline=False
                    )
                    
                    # Get the user and send DM
                    user = await bot.fetch_user(user_id)
                    await user.send(embed=embed)
                except Exception as e:
                    print(f"Failed to send maintenance reminder DM to user {user_id}: {e}")
            
            # Check for risk events if maintenance is low
            risk_event = None
            risk_type = None
            
            # Different risk thresholds for different event types
            if 0 < new_maintenance < 10:
                # Very high risk of catastrophic events (like earthquakes)
                earthquake_chance = 0.10  # 10% chance of earthquake when < 10% maintenance
                if random.random() < earthquake_chance:
                    # Find an earthquake event specifically
                    earthquake_events = [event for event in RISK_EVENTS[inv_type] if "earthquake" in event.lower()]
                    if earthquake_events:
                        risk_event = random.choice(earthquake_events)
                        risk_type = "earthquake"
            
            # Regular risk events if no earthquake and maintenance is low
            if risk_event is None and 0 < new_maintenance < 25:
                # Higher chance of general risk event when maintenance is very low
                risk_chance = (25 - new_maintenance) / 25  # 0-24% maintenance → 0-96% chance
                if random.random() < risk_chance:
                    # Filter out earthquake events for regular risk events
                    regular_events = [event for event in RISK_EVENTS[inv_type] if "earthquake" not in event.lower()]
                    # Trigger a risk event
                    risk_event = random.choice(regular_events if regular_events else RISK_EVENTS[inv_type])
                    risk_type = "regular"
                    
            # Handle the risk event if one occurred
            if risk_event:
                # Log the risk event
                await db.execute('''
                    INSERT INTO investment_logs 
                    (user_id, investment_type, event_type, description, coins_affected, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, inv_type, f"{risk_type}_risk_event", risk_event, -new_coins, now))
                
                # Different effects based on event type
                if risk_type == "earthquake":
                    # Earthquakes are more severe - complete shutdown
                    new_maintenance = 0
                    new_coins = 0
                    
                    # Try to send earthquake emergency DM
                    try:
                        # Get instance of bot from the global namespace 
                        from main import bot
                        
                        # Create embedded message with earthquake alert
                        embed = discord.Embed(
                            title="🌋 CATASTROPHIC: Earthquake Disaster!",
                            description=f"**{risk_event}**",
                            color=discord.Color.dark_red()
                        )
                        
                        embed.add_field(
                            name="🏢 Affected Business",
                            value=f"{INVESTMENTS[inv_type]['name']}",
                            inline=True
                        )
                        
                        embed.add_field(
                            name="💰 Losses",
                            value=f"All accumulated coins lost",
                            inline=True
                        )
                        
                        embed.add_field(
                            name="⚠️ Business Status",
                            value="COMPLETELY DESTROYED - Needs rebuilding",
                            inline=False
                        )
                        
                        embed.add_field(
                            name="🔧 Recovery Options",
                            value=f"Your business must be rebuilt from scratch.\nUse `/investment buy {inv_type}` to rebuild.",
                            inline=False
                        )
                        
                        # Add a striking image or icon to emphasize severity
                        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/2824/2824298.png")
                        
                        # Get the user and send DM
                        user = await bot.fetch_user(user_id)
                        await user.send(
                            content=f"<@{user_id}> **🌋 EARTHQUAKE DISASTER ALERT!**", 
                            embed=embed
                        )
                    except Exception as e:
                        print(f"Failed to send earthquake disaster DM to user {user_id}: {e}")
                else:
                    # Regular events reduce maintenance and coins but don't completely zero them
                    new_maintenance = max(0, new_maintenance - 15)  # Lose 15% maintenance
                    new_coins = max(0, int(new_coins * 0.5))  # Lose 50% of accumulated coins
                    
                    # Try to send DM with emergency response button
                    try:
                        # Get instance of bot from the global namespace 
                        from main import bot
                        
                        # Create embedded message with alert
                        embed = discord.Embed(
                            title="🚨 URGENT: Business Emergency!",
                            description=f"**{risk_event}**",
                            color=discord.Color.red()
                        )
                        
                        embed.add_field(
                            name="🏢 Affected Business",
                            value=f"{INVESTMENTS[inv_type]['name']}",
                            inline=True
                        )
                        
                        embed.add_field(
                            name="💰 Losses",
                            value=f"{int(collected_coins * 0.5)} coins lost",
                            inline=True
                        )
                        
                        embed.add_field(
                            name="⚠️ Damage Level",
                            value=f"Business damaged to {new_maintenance:.1f}% condition",
                            inline=True
                        )
                        
                        embed.add_field(
                            name="⏰ Time Sensitive",
                            value="Choose your emergency response option below!",
                            inline=False
                        )
                        
                        # Add description of different response options
                        embed.add_field(
                            name="Response Options",
                            value="• **Quick Response ($$$)**: Fastest but most expensive\n"
                                 "• **Standard Response ($$)**: Balanced approach\n"
                                 "• **Basic Response ($)**: Minimal fix, affordable\n"
                                 "• **Ignore**: Business remains damaged",
                            inline=False
                        )
                        
                        # Create emergency response view
                        view = EmergencyResponseView(user_id, inv_type, risk_event)
                        
                        # Get the user and send DM
                        user = await bot.fetch_user(user_id)
                        await user.send(content=f"<@{user_id}> **EMERGENCY ALERT!**", embed=embed, view=view)
                    except Exception as e:
                        print(f"Failed to send emergency DM to user {user_id}: {e}")
            
            # Update the investment
            await db.execute('''
                UPDATE investments
                SET maintenance = ?, collected_coins = ?, last_update_time = ?
                WHERE id = ?
            ''', (new_maintenance, new_coins, now, inv_id))
            
            # If maintenance reached 0, deactivate the investment
            if new_maintenance <= 0:
                await db.execute('''
                    UPDATE investments
                    SET active = 0
                    WHERE id = ?
                ''', (inv_id,))
                
                # Log the shutdown
                await db.execute('''
                    INSERT INTO investment_logs 
                    (user_id, investment_type, event_type, description, coins_affected, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, inv_type, "shutdown", 
                     f"Your {investment['name']} has shut down due to lack of maintenance.", 
                     0, now))
                
                # Send DM notification about shutdown
                try:
                    # Get instance of bot from the global namespace 
                    from main import bot
                    
                    # Create embedded message with shutdown alert
                    embed = discord.Embed(
                        title="🚫 Business Shutdown Alert!",
                        description=f"Your {INVESTMENTS[inv_type]['name']} has shut down due to lack of maintenance!",
                        color=discord.Color.dark_red()
                    )
                    
                    embed.add_field(
                        name="💼 Business",
                        value=f"{INVESTMENTS[inv_type]['emoji']} {INVESTMENTS[inv_type]['name']}",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="🔧 Maintenance",
                        value="0% (Critical Failure)",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="🔄 Recovery Instructions",
                        value=f"Use `/investment buy {inv_type}` to reopen your business for **{INVESTMENTS[inv_type]['cost']}** coins.",
                        inline=False
                    )
                    
                    # Get the user and send DM
                    user = await bot.fetch_user(user_id)
                    await user.send(embed=embed)
                except Exception as e:
                    print(f"Failed to send shutdown DM to user {user_id}: {e}")
        
        await db.commit()

class InvestmentCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_investments_task.start()
    
    def cog_unload(self):
        self.update_investments_task.cancel()
    
    @tasks.loop(minutes=30)
    async def update_investments_task(self):
        """Periodically update all investments."""
        await update_investments()
    
    @update_investments_task.before_loop
    async def before_update_investments(self):
        """Wait until the bot is ready before starting the task."""
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="investment", description="Manage your business investments")
    @app_commands.describe(
        action="Choose what you want to do with investments",
        business_type="Type of business to interact with"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Buy", value="buy"),
        app_commands.Choice(name="Collect", value="collect"),
        app_commands.Choice(name="Maintain", value="maintain"),
        app_commands.Choice(name="Status", value="status"),
        app_commands.Choice(name="Info", value="info"),
        app_commands.Choice(name="Logs", value="logs"),
    ])
    @app_commands.choices(business_type=[
        app_commands.Choice(name=data["name"], value=key) 
        for key, data in INVESTMENTS.items()
    ])
    async def investment(self, interaction: discord.Interaction, 
                       action: str, 
                       business_type: str = None):
        """Command to manage business investments."""
        user_id = interaction.user.id
        
        # Set up database tables if they don't exist yet
        await setup_investment_tables()
        
        # Force update investments for this user before proceeding
        await update_investments()
        
        if action == "info":
            # Show general information about investments
            embed = discord.Embed(
                title="💼 Investment System",
                description="Invest your coins in businesses to earn passive income!",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="📊 Earnings",
                value="Earnings are paid out every hour, not daily.",
                inline=False
            )
            
            # Add investment table header
            embed.add_field(
                name="Investment",
                value="\n".join([data["name"] for key, data in INVESTMENTS.items()]),
                inline=True
            )
            embed.add_field(
                name="Hourly Return",
                value="\n".join([f"{data['hourly_return']} coins/hr" for key, data in INVESTMENTS.items()]),
                inline=True
            )
            embed.add_field(
                name="Max Holding",
                value="\n".join([f"{data['max_holding']} coins" for key, data in INVESTMENTS.items()]),
                inline=True
            )
            
            # Add warning about maintenance
            embed.add_field(
                name="⚠️ Maintenance",
                value="Returns are paused if:\n• Maintenance < 25%\n• Risk event occurs (e.g., fire, strike, infestation)",
                inline=False
            )
            
            # Add second page for maintenance info
            maintenance_embed = discord.Embed(
                title="🔧 Maintenance & Income System",
                description="Each investment loses durability every hour instead of daily.",
                color=discord.Color.blurple()
            )
            
            # Add maintenance table header
            maintenance_embed.add_field(
                name="Investment",
                value="\n".join([data["name"] for key, data in INVESTMENTS.items()]),
                inline=True
            )
            maintenance_embed.add_field(
                name="Maintenance Drain",
                value="\n".join([f"-{data['maintenance_drain']}% / hour" for key, data in INVESTMENTS.items()]),
                inline=True
            )
            maintenance_embed.add_field(
                name="Risk When Low",
                value="\n".join([data["risk_level"] for key, data in INVESTMENTS.items()]),
                inline=True
            )
            
            maintenance_embed.add_field(
                name="⚠️ Warning",
                value="If you ignore your investment for too long, it may hit 0% and shut down or suffer a disaster.",
                inline=False
            )
            
            # Add cost information page
            cost_embed = discord.Embed(
                title="💰 Investment Costs",
                description="Purchase prices for each business type:",
                color=discord.Color.dark_gold()
            )
            
            # Add cost table
            cost_embed.add_field(
                name="Investment",
                value="\n".join([data["name"] for key, data in INVESTMENTS.items()]),
                inline=True
            )
            cost_embed.add_field(
                name="Purchase Cost",
                value="\n".join([f"{data['cost']} coins" for key, data in INVESTMENTS.items()]),
                inline=True
            )
            
            await interaction.response.send_message(embeds=[embed, maintenance_embed, cost_embed])
            return
            
        elif action == "status":
            # Show the user's current investments and their status
            async with aiosqlite.connect("leveling.db") as db:
                cursor = await db.execute('''
                    SELECT investment_type, maintenance, collected_coins, purchase_time, active
                    FROM investments
                    WHERE user_id = ?
                ''', (user_id,))
                
                investments = await cursor.fetchall()
            
            if not investments:
                await interaction.response.send_message(
                    "You don't have any investments yet! Use `/investment buy` to purchase your first business.",
                    ephemeral=True
                )
                return
                
            embed = discord.Embed(
                title="🏢 Your Business Empire",
                description=f"Overview of all your investments:",
                color=discord.Color.blue()
            )
            
            total_hourly_income = 0
            for inv_type, maintenance, collected_coins, purchase_time, active in investments:
                if inv_type not in INVESTMENTS:
                    continue
                    
                inv_data = INVESTMENTS[inv_type]
                status = "✅ Active" if active and maintenance >= 25 else "⚠️ Paused" if active else "❌ Shutdown"
                
                # Format the maintenance status with color indicators
                if maintenance >= 75:
                    maint_status = f"🟢 {maintenance:.1f}%"
                elif maintenance >= 50:
                    maint_status = f"🟡 {maintenance:.1f}%"
                elif maintenance >= 25:
                    maint_status = f"🟠 {maintenance:.1f}%"
                else:
                    maint_status = f"🔴 {maintenance:.1f}%"
                
                # Calculate income per hour (only if maintenance is sufficient)
                hourly_income = inv_data["hourly_return"] if maintenance >= 25 and active else 0
                total_hourly_income += hourly_income
                
                # Calculate time until max coins
                remaining_capacity = inv_data["max_holding"] - collected_coins
                hours_to_max = "∞" if hourly_income == 0 else f"{remaining_capacity / hourly_income:.1f}h"
                
                # Calculate time until maintenance drops below 25%
                if maintenance >= 25 and active:
                    hours_until_critical = (maintenance - 25) / inv_data["maintenance_drain"]
                    maint_time = f"Critical in: {hours_until_critical:.1f}h"
                else:
                    maint_time = "Needs maintenance now!"
                
                embed.add_field(
                    name=f"{inv_data['name']} - {status}",
                    value=f"Maintenance: {maint_status} ({maint_time})\n"
                          f"Collected: {collected_coins}/{inv_data['max_holding']} coins\n"
                          f"Income: {hourly_income} coins/hour\n"
                          f"Full capacity in: {hours_to_max}",
                    inline=False
                )
            
            embed.set_footer(text=f"Total hourly income: {total_hourly_income} coins/hour")
            await interaction.response.send_message(embed=embed)
            return
            
        # For all other actions, we need a business type
        if not business_type:
            await interaction.response.send_message(
                "Please specify a business type for this action!",
                ephemeral=True
            )
            return
            
        if business_type not in INVESTMENTS:
            await interaction.response.send_message(
                "Invalid business type selected!",
                ephemeral=True
            )
            return
            
        # Get investment data
        investment = INVESTMENTS[business_type]
        
        # Handle different actions
        if action == "buy":
            # Check if user already has this investment
            async with aiosqlite.connect("leveling.db") as db:
                cursor = await db.execute('''
                    SELECT id, active FROM investments
                    WHERE user_id = ? AND investment_type = ?
                ''', (user_id, business_type))
                
                existing = await cursor.fetchone()
                
                if existing and existing[1] == 1:
                    await interaction.response.send_message(
                        f"You already own a {investment['name']}! You can only own one of each business type.",
                        ephemeral=True
                    )
                    return
                    
                # If they had one but it's inactive, they can repurchase it
                if existing and existing[1] == 0:
                    # Check if user has enough coins
                    cursor = await db.execute('SELECT coins FROM users WHERE user_id = ?', (user_id,))
                    result = await cursor.fetchone()
                    
                    if not result:
                        await interaction.response.send_message(
                            "You don't have an account yet! Earn some coins first by chatting.",
                            ephemeral=True
                        )
                        return
                        
                    coins = result[0]
                    cost = investment["cost"] // 2  # 50% discount for repurchase
                    
                    if coins < cost:
                        await interaction.response.send_message(
                            f"You don't have enough coins to reopen this business! You need {cost} coins, but only have {coins}.",
                            ephemeral=True
                        )
                        return
                        
                    # Purchase the investment
                    now = datetime.now().timestamp()
                    
                    # Deduct the cost
                    await db.execute(
                        'UPDATE users SET coins = coins - ? WHERE user_id = ?',
                        (cost, user_id)
                    )
                    
                    # Reactivate the investment
                    await db.execute('''
                        UPDATE investments
                        SET active = 1, maintenance = 100, collected_coins = 0, purchase_time = ?, last_update_time = ?
                        WHERE id = ?
                    ''', (now, now, existing[0]))
                    
                    await db.commit()
                    
                    embed = discord.Embed(
                        title="🏬 Business Reopened!",
                        description=f"You've reopened your {investment['name']} for {cost} coins!",
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(
                        name="Hourly Income",
                        value=f"{investment['hourly_return']} coins/hour",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Storage Capacity",
                        value=f"{investment['max_holding']} coins",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="Maintenance",
                        value=f"100% (Loses {investment['maintenance_drain']}% per hour)",
                        inline=True
                    )
                    
                    await interaction.response.send_message(embed=embed)
                    return
                
                # Otherwise, purchase a new investment
                
                # Check if user has enough coins
                cursor = await db.execute('SELECT coins FROM users WHERE user_id = ?', (user_id,))
                result = await cursor.fetchone()
                
                if not result:
                    await interaction.response.send_message(
                        "You don't have an account yet! Earn some coins first by chatting.",
                        ephemeral=True
                    )
                    return
                    
                coins = result[0]
                cost = investment["cost"]
                
                if coins < cost:
                    await interaction.response.send_message(
                        f"You don't have enough coins to buy this business! You need {cost} coins, but only have {coins}.",
                        ephemeral=True
                    )
                    return
                    
                # Purchase the investment
                now = datetime.now().timestamp()
                
                # Deduct the cost
                await db.execute(
                    'UPDATE users SET coins = coins - ? WHERE user_id = ?',
                    (cost, user_id)
                )
                
                # Create the investment
                await db.execute('''
                    INSERT INTO investments
                    (user_id, investment_type, purchase_time, maintenance, collected_coins, last_update_time, active)
                    VALUES (?, ?, ?, 100, 0, ?, 1)
                ''', (user_id, business_type, now, now))
                
                await db.commit()
                
                embed = discord.Embed(
                    title=f"🎉 {investment['emoji']} Business Purchased!",
                    description=f"You've purchased a {investment['name']} for **{cost}** coins!",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="💰 Hourly Income",
                    value=f"**{investment['hourly_return']}** coins/hour",
                    inline=True
                )
                
                embed.add_field(
                    name="🏦 Storage Capacity",
                    value=f"**{investment['max_holding']}** coins",
                    inline=True
                )
                
                embed.add_field(
                    name="🔧 Maintenance",
                    value=f"**100%** (Loses **{investment['maintenance_drain']}%** per hour)",
                    inline=True
                )
                
                embed.add_field(
                    name="📝 Description",
                    value=f"{investment['description']}",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed)
                
        elif action == "collect":
            # Collect coins from the investment
            async with aiosqlite.connect("leveling.db") as db:
                cursor = await db.execute('''
                    SELECT id, collected_coins, maintenance, active
                    FROM investments
                    WHERE user_id = ? AND investment_type = ?
                ''', (user_id, business_type))
                
                result = await cursor.fetchone()
                
                if not result:
                    await interaction.response.send_message(
                        f"You don't own a {investment['name']}! Purchase one first with `/investment buy`.",
                        ephemeral=True
                    )
                    return
                    
                inv_id, collected_coins, maintenance, active = result
                
                if not active:
                    await interaction.response.send_message(
                        f"Your {investment['name']} has shut down! Reopen it with `/investment buy`.",
                        ephemeral=True
                    )
                    return
                
                if collected_coins <= 0:
                    await interaction.response.send_message(
                        f"Your {investment['name']} hasn't generated any coins yet!",
                        ephemeral=True
                    )
                    return
                
                # The user gets all coins (no automatic maintenance repair)
                coins_to_user = collected_coins
                
                # Add the coins to user balance
                await db.execute(
                    'UPDATE users SET coins = coins + ? WHERE user_id = ?',
                    (coins_to_user, user_id)
                )
                
                # Reset the collected coins in the investment but don't change maintenance
                await db.execute('''
                    UPDATE investments
                    SET collected_coins = 0
                    WHERE id = ?
                ''', (inv_id,))
                
                await db.commit()
                
                embed = discord.Embed(
                    title=f"💰 {investment['emoji']} Income Collected!",
                    description=f"You've collected **{collected_coins}** coins from your {investment['name']}!",
                    color=discord.Color.gold()
                )
                
                # Display current maintenance level
                embed.add_field(
                    name="🔄 Current Maintenance Level",
                    value=f"**{maintenance:.1f}%**",
                    inline=False
                )
                
                # Show maintenance status with appropriate emoji based on level
                if maintenance < 25:
                    embed.add_field(
                        name="🚨 Critical Warning",
                        value=f"Your business is in poor condition! Currently at **{maintenance:.1f}%**\nUse `/investment maintain` to restore it!",
                        inline=False
                    )
                elif maintenance < 50:
                    embed.add_field(
                        name="⚠️ Warning",
                        value=f"Your business needs maintenance. Currently at **{maintenance:.1f}%**\nUse `/investment maintain` to restore it!",
                        inline=False
                    )
                    
                await interaction.response.send_message(embed=embed)
                
        elif action == "maintain":
            # Perform maintenance on the investment
            async with aiosqlite.connect("leveling.db") as db:
                cursor = await db.execute('''
                    SELECT id, maintenance, active
                    FROM investments
                    WHERE user_id = ? AND investment_type = ?
                ''', (user_id, business_type))
                
                result = await cursor.fetchone()
                
                if not result:
                    await interaction.response.send_message(
                        f"You don't own a {investment['name']}! Purchase one first with `/investment buy`.",
                        ephemeral=True
                    )
                    return
                    
                inv_id, current_maintenance, active = result
                
                if not active:
                    await interaction.response.send_message(
                        f"Your {investment['name']} has shut down! Reopen it with `/investment buy`.",
                        ephemeral=True
                    )
                    return
                
                if current_maintenance > 50:
                    await interaction.response.send_message(
                        f"Repairs are only needed when maintenance is below 50%. Your {investment['name']} is currently at {current_maintenance:.1f}% maintenance.",
                        ephemeral=True
                    )
                    return
                
                # When maintenance is between 0-50%, always restore directly to 100%
                target_maintenance = 100
                maintenance_needed = target_maintenance - current_maintenance
                maintenance_cost = int((maintenance_needed / 100) * investment["max_holding"])
                
                # Check if user has enough coins
                cursor = await db.execute('SELECT coins FROM users WHERE user_id = ?', (user_id,))
                user_coins = (await cursor.fetchone())[0]
                
                # Create embed with maintenance information
                embed = discord.Embed(
                    title=f"🔧 {investment['emoji']} Maintenance Repair",
                    description=f"Repair your {investment['name']} to 100% condition:",
                    color=discord.Color.blue()
                )
                
                can_afford = user_coins >= maintenance_cost
                embed.add_field(
                    name=f"{'✅' if can_afford else '❌'} Restore to 100%",
                    value=f"Cost: **{maintenance_cost}** coins\nImproves by: **+{maintenance_needed:.1f}%**",
                    inline=True
                )
                
                if not can_afford:
                    embed.add_field(
                        name="❌ Insufficient Funds",
                        value=f"You need **{maintenance_cost}** coins but only have **{user_coins}** coins.",
                        inline=False
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                
                # Create confirmation view
                class ConfirmRepairView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=60)
                        
                    @discord.ui.button(label="Confirm Repair", style=discord.ButtonStyle.green)
                    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        # Deduct the cost
                        await db.execute(
                            'UPDATE users SET coins = coins - ? WHERE user_id = ?',
                            (maintenance_cost, user_id)
                        )
                        
                        # Update the maintenance to 100%
                        await db.execute('''
                            UPDATE investments
                            SET maintenance = 100
                            WHERE id = ?
                        ''', (inv_id,))
                        
                        await db.commit()
                        
                        # Create response embed
                        result_embed = discord.Embed(
                            title=f"🔧 {investment['emoji']} Maintenance Complete!",
                            description=f"You've fully repaired your {investment['name']} to **100%** condition!",
                            color=discord.Color.green()
                        )
                        
                        result_embed.add_field(
                            name="💰 Cost",
                            value=f"**{maintenance_cost}** coins",
                            inline=True
                        )
                        
                        result_embed.add_field(
                            name="📈 Improvement",
                            value=f"**{current_maintenance:.1f}%** → **100%**",
                            inline=True
                        )
                        
                        # Disable all buttons
                        for child in self.children:
                            child.disabled = True
                            
                        await interaction.response.edit_message(embed=result_embed, view=self)
                    
                    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
                    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        await interaction.response.send_message("Repair cancelled.", ephemeral=True)
                        # Disable all buttons
                        for child in self.children:
                            child.disabled = True
                        await interaction.message.edit(view=self)
                
                # Add an appropriate emoji based on the previous condition
                # Since repairs are only allowed when maintenance is below 50%,
                # we only need these two condition messages
                if current_maintenance < 25:
                    status_emoji = "🚨 → ✅"
                    message = "Critical condition fixed!"
                else:  # Must be between 25-50%
                    status_emoji = "⚠️ → ✅"
                    message = "Issues resolved!"
                
                embed.add_field(
                    name=status_emoji,
                    value=message,
                    inline=True
                )
                
                embed.set_footer(text=f"⏰ Maintenance drains at a rate of {investment['maintenance_drain']}% per hour")
                
                # Send the confirmation view
                await interaction.response.send_message(embed=embed, view=ConfirmRepairView())
        
        else:
            await interaction.response.send_message(
                "Invalid action! Try 'buy', 'collect', 'maintain', 'status', or 'info'.",
                ephemeral=True
            )

async def setup(bot):
    """Add the cog to the bot."""
    await setup_investment_tables()
    await bot.add_cog(InvestmentCommands(bot))