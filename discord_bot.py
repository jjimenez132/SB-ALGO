#!/usr/bin/env python3
"""
SB-ALGO Discord Bot - Hedge Fund Style
=======================================
Full-featured bot with bankroll management, bet tracking, and AI analysis.
"""

import os
import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger(__name__)

# Environment variables
DISCORD_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Allowed channels for bot responses
ALLOWED_CHANNELS = ['algo-chat', 'ask-algo', 'bot-test', 'bankroll', 'risk-desk']

# ============================================================
# BOT EVENTS
# ============================================================

@bot.event
async def on_ready():
    log.info(f"✅ SB-ALGO Bot is online as {bot.user}")
    log.info(f"Connected to {len(bot.guilds)} server(s)")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, 
        name="NBA edges | !help"
    ))

@bot.event
async def on_member_join(member):
    """Welcome new members and start onboarding"""
    try:
        embed = discord.Embed(
            title="🎯 Welcome to SB-ALGO",
            description=f"Hey {member.name}! Welcome to the edge.\n\n"
                       f"**Get started by setting up your bankroll:**\n"
                       f"Type `!setup` to configure your personal bankroll manager.",
            color=0x667eea
        )
        embed.add_field(name="📊 What you get:", value=(
            "• Personalized unit sizing\n"
            "• Exposure limit tracking\n"
            "• Performance analytics\n"
            "• Bet logging & P/L tracking"
        ), inline=False)
        embed.set_footer(text="SB-ALGO — Institutional-grade sports betting intelligence")
        await member.send(embed=embed)
    except:
        pass  # Can't DM user

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Process commands first
    await bot.process_commands(message)
    
    # Natural language in allowed channels
    channel_name = message.channel.name.lower() if hasattr(message.channel, 'name') else ''
    if any(allowed in channel_name for allowed in ALLOWED_CHANNELS):
        # Skip if it's a command
        if message.content.startswith('!'):
            return
        
        # Only respond to @mentions or direct questions
        if bot.user.mentioned_in(message) or '?' in message.content:
            async with message.channel.typing():
                try:
                    from algo_agent import query_algo_agent
                    response = query_algo_agent(message.content)
                    await message.reply(response)
                except Exception as e:
                    await message.reply(f"⚠️ Error: {str(e)}")

# ============================================================
# ONBOARDING COMMANDS
# ============================================================

@bot.command(name='setup')
async def setup_bankroll(ctx):
    """Start bankroll setup wizard"""
    from bankroll_manager import get_user, create_user, is_onboarded, create_bankroll_settings, complete_onboarding
    
    discord_id = str(ctx.author.id)
    username = str(ctx.author.name)
    
    # Create user if doesn't exist
    create_user(discord_id, username)
    
    if is_onboarded(discord_id):
        await ctx.send("✅ You're already set up! Use `!bankroll` to view your settings or `!update` to change them.")
        return
    
    embed = discord.Embed(
        title="💰 Bankroll Setup Wizard",
        description="Let's configure your hedge fund-style bankroll manager.\n\n"
                   "**Step 1 of 4:** What's your starting bankroll?",
        color=0x667eea
    )
    embed.add_field(name="Example", value="Type a number like `5000` for $5,000", inline=False)
    embed.set_footer(text="Type 'cancel' at any time to exit")
    await ctx.send(embed=embed)
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel
    
    try:
        # Step 1: Starting Bankroll
        msg = await bot.wait_for('message', check=check, timeout=120)
        if msg.content.lower() == 'cancel':
            await ctx.send("❌ Setup cancelled.")
            return
        
        try:
            starting_bankroll = float(msg.content.replace('$', '').replace(',', ''))
        except:
            await ctx.send("❌ Invalid amount. Please run `!setup` again.")
            return
        
        # Step 2: Risk Method
        embed = discord.Embed(
            title="💰 Bankroll Setup Wizard",
            description=f"Great! Starting bankroll: **${starting_bankroll:,.2f}**\n\n"
                       f"**Step 2 of 4:** Choose your risk method:",
            color=0x667eea
        )
        embed.add_field(name="1️⃣ Percentage", value="Risk % of bankroll per bet (recommended)", inline=False)
        embed.add_field(name="2️⃣ Fixed", value="Fixed dollar amount per bet", inline=False)
        embed.add_field(name="3️⃣ Units", value="Fixed unit system", inline=False)
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for('message', check=check, timeout=60)
        risk_method_map = {'1': 'percentage', '2': 'fixed', '3': 'units', 
                          'percentage': 'percentage', 'fixed': 'fixed', 'units': 'units'}
        risk_method = risk_method_map.get(msg.content.lower().strip(), 'percentage')
        
        # Step 3: Max Risk %
        embed = discord.Embed(
            title="💰 Bankroll Setup Wizard",
            description=f"Risk method: **{risk_method.title()}**\n\n"
                       f"**Step 3 of 4:** What's your max risk per bet?\n"
                       f"(Enter a number between 1-10)",
            color=0x667eea
        )
        embed.add_field(name="🟢 Conservative", value="1-2%", inline=True)
        embed.add_field(name="🟡 Balanced", value="2-3%", inline=True)
        embed.add_field(name="🔴 Aggressive", value="3-5%", inline=True)
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for('message', check=check, timeout=60)
        try:
            max_risk_pct = float(msg.content.replace('%', ''))
            max_risk_pct = max(1, min(10, max_risk_pct))  # Clamp 1-10
        except:
            max_risk_pct = 2.0
        
        # Step 4: Strategy Profile
        embed = discord.Embed(
            title="💰 Bankroll Setup Wizard",
            description=f"Max risk: **{max_risk_pct}%** per bet\n\n"
                       f"**Step 4 of 4:** Choose your strategy profile:",
            color=0x667eea
        )
        embed.add_field(name="🟢 1. Conservative", value="Lower variance, steady growth", inline=False)
        embed.add_field(name="🟡 2. Balanced", value="Moderate risk/reward (recommended)", inline=False)
        embed.add_field(name="🔴 3. Aggressive", value="Higher variance, faster growth potential", inline=False)
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for('message', check=check, timeout=60)
        strategy_map = {'1': 'conservative', '2': 'balanced', '3': 'aggressive',
                       'conservative': 'conservative', 'balanced': 'balanced', 'aggressive': 'aggressive'}
        strategy = strategy_map.get(msg.content.lower().strip(), 'balanced')
        
        # Save settings
        create_bankroll_settings(discord_id, starting_bankroll, risk_method, max_risk_pct, strategy)
        complete_onboarding(discord_id)
        
        # Calculate unit size
        unit_size = starting_bankroll * (max_risk_pct / 100)
        
        # Final summary
        embed = discord.Embed(
            title="✅ Bankroll Setup Complete!",
            description="Your hedge fund-style bankroll is ready.",
            color=0x00FF00
        )
        embed.add_field(name="💵 Starting Bankroll", value=f"${starting_bankroll:,.2f}", inline=True)
        embed.add_field(name="📊 Risk Method", value=risk_method.title(), inline=True)
        embed.add_field(name="⚠️ Max Risk", value=f"{max_risk_pct}%", inline=True)
        embed.add_field(name="📈 Strategy", value=strategy.title(), inline=True)
        embed.add_field(name="🎯 Unit Size", value=f"${unit_size:,.2f}", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="🟢 Low (0.5u)", value=f"${unit_size * 0.5:,.2f}", inline=True)
        embed.add_field(name="🟡 Standard (1u)", value=f"${unit_size:,.2f}", inline=True)
        embed.add_field(name="🔴 High (2u)", value=f"${unit_size * 2:,.2f}", inline=True)
        embed.set_footer(text="Use !bankroll to view | !stake to calculate bets | !help for all commands")
        await ctx.send(embed=embed)
        
    except asyncio.TimeoutError:
        await ctx.send("⏰ Setup timed out. Run `!setup` to try again.")

# ============================================================
# BANKROLL COMMANDS
# ============================================================

@bot.command(name='bankroll', aliases=['br', 'bank'])
async def show_bankroll(ctx):
    """Show your bankroll overview"""
    from bankroll_manager import is_onboarded, build_bankroll_embed
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send("❌ You haven't set up your bankroll yet. Use `!setup` to get started.")
        return
    
    embed_data = build_bankroll_embed(discord_id)
    if embed_data:
        embed = discord.Embed.from_dict(embed_data)
        await ctx.send(embed=embed)
    else:
        await ctx.send("⚠️ Could not load bankroll data.")

@bot.command(name='health')
async def show_health(ctx):
    """Show bankroll health analysis"""
    from bankroll_manager import is_onboarded, build_health_embed
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send("❌ Use `!setup` first.")
        return
    
    embed_data = build_health_embed(discord_id)
    if embed_data:
        embed = discord.Embed.from_dict(embed_data)
        await ctx.send(embed=embed)

@bot.command(name='stake', aliases=['unit', 'size'])
async def show_stake(ctx, units: float = 1.0):
    """Calculate your stake for given units"""
    from bankroll_manager import is_onboarded, get_bet_sizes, check_exposure
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send("❌ Use `!setup` first.")
        return
    
    sizes = get_bet_sizes(discord_id)
    stake = sizes['unit_size'] * units
    
    # Check exposure
    exposure = check_exposure(discord_id, stake)
    
    embed = discord.Embed(
        title=f"🎯 Stake Calculator — {units}u",
        color=0x00FF00 if exposure['allowed'] else 0xFF0000
    )
    embed.add_field(name="💵 Your Stake", value=f"**${stake:,.2f}**", inline=False)
    embed.add_field(name="🟢 0.5u", value=f"${sizes['low_confidence']['stake']:,.2f}", inline=True)
    embed.add_field(name="🟡 1.0u", value=f"${sizes['standard']['stake']:,.2f}", inline=True)
    embed.add_field(name="🔴 2.0u", value=f"${sizes['high_confidence']['stake']:,.2f}", inline=True)
    
    if not exposure['allowed']:
        embed.add_field(name="⚠️ Warning", value=exposure['reason'], inline=False)
    
    embed.set_footer(text=f"Max single bet: ${sizes['max_bet']:,.2f} | Max daily: ${sizes['max_daily']:,.2f}")
    await ctx.send(embed=embed)

@bot.command(name='update')
async def update_bankroll(ctx, amount: str = None):
    """Update your current bankroll"""
    from bankroll_manager import is_onboarded, update_bankroll as update_br, get_bankroll_settings
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send("❌ Use `!setup` first.")
        return
    
    if not amount:
        settings = get_bankroll_settings(discord_id)
        await ctx.send(f"💵 Current bankroll: **${float(settings['current_bankroll']):,.2f}**\n"
                      f"To update, use: `!update 12500`")
        return
    
    try:
        new_amount = float(amount.replace('$', '').replace(',', ''))
        update_br(discord_id, new_amount)
        await ctx.send(f"✅ Bankroll updated to **${new_amount:,.2f}**")
    except:
        await ctx.send("❌ Invalid amount. Use: `!update 12500`")

@bot.command(name='limits')
async def set_limits(ctx, daily: str = None, single: str = None):
    """Set exposure limits"""
    from bankroll_manager import is_onboarded, set_exposure_limits, get_bankroll_settings
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send("❌ Use `!setup` first.")
        return
    
    settings = get_bankroll_settings(discord_id)
    
    if not daily or not single:
        await ctx.send(f"📊 **Current Exposure Limits:**\n"
                      f"• Max Daily: {float(settings['max_daily_exposure_pct'])}%\n"
                      f"• Max Single Bet: {float(settings['max_single_game_pct'])}%\n\n"
                      f"To change: `!limits 10 5` (10% daily, 5% single)")
        return
    
    try:
        daily_pct = float(daily.replace('%', ''))
        single_pct = float(single.replace('%', ''))
        set_exposure_limits(discord_id, daily_pct, single_pct)
        await ctx.send(f"✅ Limits updated: Daily {daily_pct}% | Single {single_pct}%")
    except:
        await ctx.send("❌ Invalid. Use: `!limits 10 5`")

@bot.command(name='targets')
async def set_targets(ctx, profit: str = None, stop: str = None):
    """Set daily profit goal and stop loss"""
    from bankroll_manager import is_onboarded, set_session_targets, get_bankroll_settings
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send("❌ Use `!setup` first.")
        return
    
    settings = get_bankroll_settings(discord_id)
    
    if not profit or not stop:
        await ctx.send(f"🎯 **Session Targets:**\n"
                      f"• Daily Profit Goal: ${float(settings['daily_profit_goal']):,.2f}\n"
                      f"• Stop Loss Limit: ${float(settings['stop_loss_limit']):,.2f}\n\n"
                      f"To change: `!targets 500 300` ($500 goal, $300 stop)")
        return
    
    try:
        profit_goal = float(profit.replace('$', '').replace(',', ''))
        stop_loss = float(stop.replace('$', '').replace(',', ''))
        set_session_targets(discord_id, profit_goal, stop_loss)
        await ctx.send(f"✅ Targets set: Goal ${profit_goal:,.2f} | Stop ${stop_loss:,.2f}")
    except:
        await ctx.send("❌ Invalid. Use: `!targets 500 300`")

# ============================================================
# BET TRACKING COMMANDS
# ============================================================

@bot.command(name='bet', aliases=['log'])
async def log_bet(ctx, units: float = None, odds: int = None, *, description: str = None):
    """Log a bet: !bet 1.5 -110 Lakers ML"""
    from bankroll_manager import is_onboarded, log_bet as log_bet_db, calculate_stake
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send("❌ Use `!setup` first.")
        return
    
    if not units or not odds or not description:
        await ctx.send("📝 **Log a bet:**\n"
                      "`!bet <units> <odds> <description>`\n\n"
                      "**Examples:**\n"
                      "`!bet 1 -110 Lakers -3.5`\n"
                      "`!bet 2 +150 Celtics ML`\n"
                      "`!bet 0.5 -115 LeBron o25.5 pts`")
        return
    
    stake = calculate_stake(discord_id, units)
    bet_id = log_bet_db(discord_id, 'manual', description, description, units, odds)
    
    embed = discord.Embed(
        title="📝 Bet Logged",
        description=f"**{description}**",
        color=0x667eea
    )
    embed.add_field(name="Units", value=f"{units}u", inline=True)
    embed.add_field(name="Stake", value=f"${stake:,.2f}", inline=True)
    embed.add_field(name="Odds", value=f"{odds:+d}", inline=True)
    embed.set_footer(text=f"Bet ID: {bet_id} | Grade with: !grade {bet_id} win/loss")
    await ctx.send(embed=embed)

@bot.command(name='grade')
async def grade_bet(ctx, bet_id: int = None, result: str = None):
    """Grade a bet: !grade 123 win"""
    from bankroll_manager import is_onboarded, grade_bet as grade_bet_db
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send("❌ Use `!setup` first.")
        return
    
    if not bet_id or not result:
        await ctx.send("📊 **Grade a bet:**\n`!grade <bet_id> <result>`\n\n"
                      "Results: `win`, `loss`, `push`\n"
                      "Example: `!grade 123 win`")
        return
    
    result = result.lower()
    if result not in ['win', 'loss', 'push', 'w', 'l', 'p']:
        await ctx.send("❌ Result must be: win, loss, or push")
        return
    
    result_map = {'w': 'win', 'l': 'loss', 'p': 'push'}
    result = result_map.get(result, result)
    
    graded = grade_bet_db(discord_id, bet_id, result)
    
    if graded:
        emoji = "✅" if result == 'win' else "❌" if result == 'loss' else "➡️"
        color = 0x00FF00 if result == 'win' else 0xFF0000 if result == 'loss' else 0xFFFF00
        
        embed = discord.Embed(
            title=f"{emoji} Bet Graded: {result.upper()}",
            color=color
        )
        embed.add_field(name="P/L", value=f"${graded['pnl']:+,.2f}", inline=True)
        embed.add_field(name="New Bankroll", value=f"${graded['new_bankroll']:,.2f}", inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Bet not found or already graded.")

@bot.command(name='pending')
async def show_pending(ctx):
    """Show pending bets"""
    from bankroll_manager import is_onboarded, get_pending_bets
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send("❌ Use `!setup` first.")
        return
    
    bets = get_pending_bets(discord_id)
    
    if not bets:
        await ctx.send("📋 No pending bets.")
        return
    
    embed = discord.Embed(title="📋 Pending Bets", color=0x667eea)
    for bet in bets[:10]:
        embed.add_field(
            name=f"#{bet['id']} — {bet['units']}u @ {bet['odds']:+d}",
            value=f"{bet['description'][:50]} | ${bet['stake_usd']:,.2f}",
            inline=False
        )
    embed.set_footer(text="Grade with: !grade <id> win/loss/push")
    await ctx.send(embed=embed)

@bot.command(name='history', aliases=['bets'])
async def show_history(ctx):
    """Show bet history"""
    from bankroll_manager import is_onboarded, get_bet_history
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send("❌ Use `!setup` first.")
        return
    
    bets = get_bet_history(discord_id, 10)
    
    if not bets:
        await ctx.send("📋 No bet history yet.")
        return
    
    embed = discord.Embed(title="📜 Recent Bet History", color=0x667eea)
    for bet in bets:
        emoji = "✅" if bet['result'] == 'win' else "❌" if bet['result'] == 'loss' else "➡️"
        embed.add_field(
            name=f"{emoji} {bet['description'][:30]}",
            value=f"{bet['units']}u | ${bet['pnl_usd']:+,.2f}",
            inline=True
        )
    await ctx.send(embed=embed)

# ============================================================
# PICKS COMMANDS (existing)
# ============================================================

@bot.command(name='picks')
async def show_picks(ctx):
    """Show today's top game picks"""
    try:
        from algo_agent import query_algo_agent
        response = query_algo_agent("What are today's top NBA game picks with the best edges?")
        await ctx.send(response)
    except Exception as e:
        await ctx.send(f"⚠️ Error getting picks: {str(e)}")

@bot.command(name='props')
async def show_props(ctx):
    """Show today's top prop bets"""
    try:
        from algo_agent import query_algo_agent
        response = query_algo_agent("What are today's top NBA player prop bets?")
        await ctx.send(response)
    except Exception as e:
        await ctx.send(f"⚠️ Error getting props: {str(e)}")

@bot.command(name='injuries')
async def show_injuries(ctx, team: str = None):
    """Show injury report"""
    try:
        from algo_agent import query_algo_agent
        query = f"What are the current injuries for {team}?" if team else "What are the major NBA injuries affecting today's games?"
        response = query_algo_agent(query)
        await ctx.send(response)
    except Exception as e:
        await ctx.send(f"⚠️ Error: {str(e)}")

@bot.command(name='game')
async def analyze_game(ctx, *, team: str = None):
    """Analyze a specific game"""
    if not team:
        await ctx.send("Usage: `!game Lakers` or `!game LAL vs BOS`")
        return
    try:
        from algo_agent import query_algo_agent
        response = query_algo_agent(f"Analyze {team}'s game today. Include spread, total, and any edges.")
        await ctx.send(response)
    except Exception as e:
        await ctx.send(f"⚠️ Error: {str(e)}")

# ============================================================
# HELP COMMAND
# ============================================================

@bot.command(name='help', aliases=['commands', 'menu'])
async def show_help(ctx):
    """Show all commands"""
    embed = discord.Embed(
        title="📚 SB-ALGO Commands",
        description="Hedge fund-style sports betting intelligence",
        color=0x667eea
    )
    
    embed.add_field(name="💰 BANKROLL", value=(
        "`!setup` — Initial bankroll setup\n"
        "`!bankroll` — View your dashboard\n"
        "`!health` — Bankroll health analysis\n"
        "`!stake <units>` — Calculate stake\n"
        "`!update <amount>` — Update bankroll\n"
        "`!limits <daily%> <single%>` — Set limits\n"
        "`!targets <goal> <stop>` — Set targets"
    ), inline=False)
    
    embed.add_field(name="📝 BET TRACKING", value=(
        "`!bet <units> <odds> <pick>` — Log bet\n"
        "`!grade <id> <result>` — Grade bet\n"
        "`!pending` — View pending bets\n"
        "`!history` — Bet history"
    ), inline=False)
    
    embed.add_field(name="🎯 PICKS & ANALYSIS", value=(
        "`!picks` — Today's top game picks\n"
        "`!props` — Today's top props\n"
        "`!injuries [team]` — Injury report\n"
        "`!game <team>` — Game analysis"
    ), inline=False)
    
    embed.set_footer(text="SB-ALGO — Built for disciplined bettors")
    await ctx.send(embed=embed)

# ============================================================
# STATUS COMMAND
# ============================================================

@bot.command(name='status')
async def show_status(ctx):
    """Show bot status"""
    from bankroll_manager import get_engine
    
    # Check database
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        db_status = "✅ Connected"
    except:
        db_status = "❌ Disconnected"
    
    # Check AI
    try:
        from algo_agent import AGENT_AVAILABLE
        ai_status = "✅ Online" if AGENT_AVAILABLE else "⚠️ Initializing"
    except:
        ai_status = "❌ Offline"
    
    embed = discord.Embed(title="🤖 SB-ALGO Status", color=0x667eea)
    embed.add_field(name="Bot", value="✅ Online", inline=True)
    embed.add_field(name="Database", value=db_status, inline=True)
    embed.add_field(name="AI Agent", value=ai_status, inline=True)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    await ctx.send(embed=embed)

# ============================================================
# MAIN
# ============================================================

def main():
    if not DISCORD_TOKEN:
        log.error("Missing DISCORD_BOT_TOKEN")
        return
    
    log.info("Starting SB-ALGO Bot...")
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
