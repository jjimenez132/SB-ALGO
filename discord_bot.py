#!/usr/bin/env python3
"""
SB-ALGO Discord Bot - Hedge Fund Style
=======================================
Full-featured bot with bankroll management, bet tracking, and AI analysis.
"""

import os
import discord
from discord.ext import commands
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

# Channel configuration
BANKROLL_CHANNEL = 'bankroll-dashboard'  # ONLY channel for bankroll commands
CHAT_CHANNELS = ['algo-chat', 'ask-algo', 'bot-test']  # Channels for general AI chat

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def is_bankroll_channel(ctx):
    """Check if command is in bankroll channel"""
    return hasattr(ctx.channel, 'name') and ctx.channel.name == BANKROLL_CHANNEL

async def send_not_allowed(ctx):
    """Send message that command must be used in bankroll channel"""
    await ctx.message.delete()  # Delete the command
    try:
        await ctx.author.send(
            f"⚠️ Bankroll commands only work in **#{BANKROLL_CHANNEL}**\n"
            f"Please go there to manage your bankroll."
        )
    except:
        pass  # Can't DM user

async def send_welcome_embed(channel):
    """Send the welcome/instruction embed to bankroll channel"""
    embed = discord.Embed(
        title="💰 Bankroll Manager — Financial Control Suite",
        description=(
            "Welcome to your **hedge fund-style** bankroll management system.\n\n"
            "**Get started by typing:** `!setup`"
        ),
        color=0x667eea
    )
    
    embed.add_field(
        name="🚀 QUICK START",
        value=(
            "`!setup` — Configure your bankroll (required first)\n"
            "`!bankroll` — View your full dashboard\n"
            "`!stake` — See your bet sizes"
        ),
        inline=False
    )
    
    embed.add_field(
        name="💵 BANKROLL COMMANDS",
        value=(
            "`!bankroll` — Full dashboard view\n"
            "`!health` — Bankroll health analysis\n"
            "`!update <amount>` — Update current bankroll\n"
            "`!limits` — View/set exposure limits\n"
            "`!targets` — Set profit goal & stop loss"
        ),
        inline=True
    )
    
    embed.add_field(
        name="🎯 BET SIZING",
        value=(
            "`!stake` — View all unit sizes\n"
            "`!stake 1.5` — Calculate specific stake\n"
            "🟢 0.5u = Low confidence\n"
            "🟡 1.0u = Standard\n"
            "🔴 2.0u = High confidence"
        ),
        inline=True
    )
    
    embed.add_field(
        name="📝 BET TRACKING",
        value=(
            "`!bet <units> <odds> <pick>` — Log a bet\n"
            "`!grade <id> <win/loss>` — Grade result\n"
            "`!pending` — View open bets\n"
            "`!history` — Bet history & P/L"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Risk Management Notice",
        value=(
            "Good bankroll management is essential to long-term success. "
            "This tool helps you plan, track, and structure your approach responsibly. "
            "Never bet more than you can afford to lose."
        ),
        inline=False
    )
    
    embed.set_footer(text="SB-ALGO — Institutional-grade bankroll allocation for disciplined bettors")
    
    return embed

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
    """Welcome new members via DM and direct to bankroll channel"""
    try:
        embed = discord.Embed(
            title="🎯 Welcome to SB-ALGO",
            description=(
                f"Hey **{member.name}**! Welcome to the edge.\n\n"
                f"I'm your personal bankroll manager and betting assistant."
            ),
            color=0x667eea
        )
        
        embed.add_field(
            name="🚀 Get Started",
            value=(
                f"**Step 1:** Go to **#{BANKROLL_CHANNEL}**\n"
                f"**Step 2:** Type `!setup` to configure your bankroll\n"
                f"**Step 3:** Start receiving personalized bet sizing!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 What You Get",
            value=(
                "• **Personal unit sizing** based on YOUR bankroll\n"
                "• **Exposure tracking** to manage risk\n"
                "• **Performance analytics** (ROI, win rate, streaks)\n"
                "• **Bet logging** with P/L tracking\n"
                "• **AI-powered** game analysis"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 Quick Commands",
            value=(
                "`!setup` — Configure bankroll\n"
                "`!bankroll` — View dashboard\n"
                "`!picks` — Today's top picks\n"
                "`!help` — All commands"
            ),
            inline=False
        )
        
        embed.set_footer(text="Head to #bankroll-dashboard to begin!")
        
        await member.send(embed=embed)
        log.info(f"Sent welcome DM to {member.name}")
    except discord.Forbidden:
        log.info(f"Could not DM {member.name} (DMs disabled)")
    except Exception as e:
        log.error(f"Error sending welcome DM: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Process commands first
    await bot.process_commands(message)
    
    # Natural language AI chat in allowed channels
    channel_name = message.channel.name.lower() if hasattr(message.channel, 'name') else ''
    
    if any(ch in channel_name for ch in CHAT_CHANNELS):
        if message.content.startswith('!'):
            return
        
        if bot.user.mentioned_in(message) or '?' in message.content:
            async with message.channel.typing():
                try:
                    from algo_agent import query_algo_agent
                    response = query_algo_agent(message.content)
                    await message.reply(response)
                except Exception as e:
                    await message.reply(f"⚠️ Error: {str(e)}")

# ============================================================
# BANKROLL SETUP (only in #bankroll-dashboard)
# ============================================================

@bot.command(name='setup')
async def setup_bankroll(ctx):
    """Start bankroll setup wizard - ONLY in #bankroll-dashboard"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import get_user, create_user, is_onboarded, create_bankroll_settings, complete_onboarding
    
    discord_id = str(ctx.author.id)
    username = str(ctx.author.name)
    
    create_user(discord_id, username)
    
    if is_onboarded(discord_id):
        await ctx.send(f"✅ {ctx.author.mention} You're already set up! Use `!bankroll` to view your settings.")
        return
    
    # Welcome embed
    embed = discord.Embed(
        title="💰 Bankroll Setup Wizard",
        description=(
            f"Welcome {ctx.author.mention}! Let's configure your hedge fund-style bankroll.\n\n"
            f"**Step 1 of 4:** What's your starting bankroll?\n"
            f"_(Type a number, e.g., `5000` for $5,000)_"
        ),
        color=0x667eea
    )
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
            if starting_bankroll < 100:
                await ctx.send("❌ Minimum bankroll is $100. Please run `!setup` again.")
                return
        except:
            await ctx.send("❌ Invalid amount. Please run `!setup` again with a number like `5000`")
            return
        
        # Step 2: Strategy Profile
        embed = discord.Embed(
            title="💰 Bankroll Setup Wizard",
            description=(
                f"Starting bankroll: **${starting_bankroll:,.2f}** ✅\n\n"
                f"**Step 2 of 4:** Choose your strategy profile:\n"
            ),
            color=0x667eea
        )
        embed.add_field(name="1️⃣ Conservative", value="1-2% risk per bet\nSteady, low variance", inline=False)
        embed.add_field(name="2️⃣ Balanced", value="2-3% risk per bet\nRecommended for most", inline=False)
        embed.add_field(name="3️⃣ Aggressive", value="3-5% risk per bet\nHigher variance", inline=False)
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for('message', check=check, timeout=60)
        strategy_map = {'1': 'conservative', '2': 'balanced', '3': 'aggressive'}
        strategy = strategy_map.get(msg.content.strip(), 'balanced')
        
        # Set default risk based on strategy
        risk_defaults = {'conservative': 1.5, 'balanced': 2.5, 'aggressive': 4.0}
        default_risk = risk_defaults[strategy]
        
        # Step 3: Confirm or customize risk %
        embed = discord.Embed(
            title="💰 Bankroll Setup Wizard",
            description=(
                f"Strategy: **{strategy.title()}** ✅\n\n"
                f"**Step 3 of 4:** Max risk per bet?\n\n"
                f"Default for {strategy}: **{default_risk}%**\n"
                f"_(Type a number 1-10, or `ok` to use default)_"
            ),
            color=0x667eea
        )
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for('message', check=check, timeout=60)
        if msg.content.lower() in ['ok', 'yes', 'y', 'default']:
            max_risk_pct = default_risk
        else:
            try:
                max_risk_pct = float(msg.content.replace('%', ''))
                max_risk_pct = max(1, min(10, max_risk_pct))
            except:
                max_risk_pct = default_risk
        
        # Step 4: Session targets (optional)
        unit_size = starting_bankroll * (max_risk_pct / 100)
        
        embed = discord.Embed(
            title="💰 Bankroll Setup Wizard",
            description=(
                f"Risk per bet: **{max_risk_pct}%** = **${unit_size:,.2f}** per unit ✅\n\n"
                f"**Step 4 of 4:** Set daily targets (optional)\n\n"
                f"Type your **daily profit goal** in dollars, or `skip` to set later.\n"
                f"_(e.g., `500` for $500 daily goal)_"
            ),
            color=0x667eea
        )
        await ctx.send(embed=embed)
        
        msg = await bot.wait_for('message', check=check, timeout=60)
        if msg.content.lower() in ['skip', 'no', 'n', '0']:
            profit_goal = 0
            stop_loss = 0
        else:
            try:
                profit_goal = float(msg.content.replace('$', '').replace(',', ''))
                stop_loss = profit_goal  # Default stop loss = profit goal
            except:
                profit_goal = 0
                stop_loss = 0
        
        # Save everything
        create_bankroll_settings(discord_id, starting_bankroll, 'percentage', max_risk_pct, strategy)
        
        if profit_goal > 0:
            from bankroll_manager import set_session_targets
            set_session_targets(discord_id, profit_goal, stop_loss)
        
        complete_onboarding(discord_id)
        
        # Final summary
        embed = discord.Embed(
            title="✅ Bankroll Setup Complete!",
            description=f"Welcome to the edge, {ctx.author.mention}!",
            color=0x00FF00
        )
        embed.add_field(name="💵 Bankroll", value=f"${starting_bankroll:,.2f}", inline=True)
        embed.add_field(name="📈 Strategy", value=strategy.title(), inline=True)
        embed.add_field(name="⚠️ Risk/Bet", value=f"{max_risk_pct}%", inline=True)
        
        embed.add_field(name="\u200b", value="**🎯 Your Bet Sizes:**", inline=False)
        embed.add_field(name="🟢 Low (0.5u)", value=f"${unit_size * 0.5:,.2f}", inline=True)
        embed.add_field(name="🟡 Standard (1u)", value=f"${unit_size:,.2f}", inline=True)
        embed.add_field(name="🔴 High (2u)", value=f"${unit_size * 2:,.2f}", inline=True)
        
        if profit_goal > 0:
            embed.add_field(name="🎯 Daily Goal", value=f"${profit_goal:,.2f}", inline=True)
            embed.add_field(name="🛑 Stop Loss", value=f"${stop_loss:,.2f}", inline=True)
        
        embed.add_field(
            name="📚 Next Steps",
            value=(
                "`!bankroll` — View full dashboard\n"
                "`!stake` — See all bet sizes\n"
                "`!bet 1 -110 Lakers ML` — Log a bet\n"
                "`!help` — All commands"
            ),
            inline=False
        )
        
        embed.set_footer(text="Your bankroll is now being tracked. Good luck! 🍀")
        await ctx.send(embed=embed)
        
    except asyncio.TimeoutError:
        await ctx.send("⏰ Setup timed out. Run `!setup` to try again.")

# ============================================================
# BANKROLL COMMANDS (only in #bankroll-dashboard)
# ============================================================

@bot.command(name='bankroll', aliases=['br', 'bank', 'dashboard'])
async def show_bankroll(ctx):
    """Show your bankroll dashboard"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded, build_bankroll_embed
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ {ctx.author.mention} You need to set up first! Type `!setup` to begin.")
        return
    
    embed_data = build_bankroll_embed(discord_id)
    if embed_data:
        embed = discord.Embed.from_dict(embed_data)
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)

@bot.command(name='health')
async def show_health(ctx):
    """Show bankroll health"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded, build_health_embed
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ {ctx.author.mention} Use `!setup` first.")
        return
    
    embed_data = build_health_embed(discord_id)
    if embed_data:
        embed = discord.Embed.from_dict(embed_data)
        await ctx.send(embed=embed)

@bot.command(name='stake', aliases=['unit', 'size'])
async def show_stake(ctx, units: float = None):
    """Show/calculate bet sizes"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded, get_bet_sizes, check_exposure
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ {ctx.author.mention} Use `!setup` first.")
        return
    
    sizes = get_bet_sizes(discord_id)
    
    if units:
        stake = sizes['unit_size'] * units
        exposure = check_exposure(discord_id, stake)
        
        embed = discord.Embed(
            title=f"🎯 Stake: {units}u = ${stake:,.2f}",
            color=0x00FF00 if exposure['allowed'] else 0xFF0000
        )
        if not exposure['allowed']:
            embed.add_field(name="⚠️ Warning", value=exposure['reason'], inline=False)
    else:
        embed = discord.Embed(
            title="🎯 Your Bet Sizes",
            description=f"**1 Unit = ${sizes['unit_size']:,.2f}**",
            color=0x667eea
        )
        embed.add_field(name="🟢 Low Confidence", value=f"0.5u = **${sizes['low_confidence']['stake']:,.2f}**\n60-70% plays", inline=True)
        embed.add_field(name="🟡 Standard", value=f"1.0u = **${sizes['standard']['stake']:,.2f}**\n70-80% plays", inline=True)
        embed.add_field(name="🔴 High Confidence", value=f"2.0u = **${sizes['high_confidence']['stake']:,.2f}**\n80%+ plays", inline=True)
        embed.add_field(name="📊 Limits", value=f"Max single: ${sizes['max_bet']:,.2f}\nMax daily: ${sizes['max_daily']:,.2f}", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='update')
async def update_bankroll(ctx, amount: str = None):
    """Update current bankroll"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded, update_bankroll as update_br, get_bankroll_settings
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ Use `!setup` first.")
        return
    
    if not amount:
        settings = get_bankroll_settings(discord_id)
        await ctx.send(f"💵 Current bankroll: **${float(settings['current_bankroll']):,.2f}**\nTo update: `!update 12500`")
        return
    
    try:
        new_amount = float(amount.replace('$', '').replace(',', ''))
        update_br(discord_id, new_amount)
        
        # Show updated unit size
        new_settings = get_bankroll_settings(discord_id)
        unit_size = float(new_settings['unit_size'])
        
        embed = discord.Embed(title="✅ Bankroll Updated", color=0x00FF00)
        embed.add_field(name="New Bankroll", value=f"${new_amount:,.2f}", inline=True)
        embed.add_field(name="New Unit Size", value=f"${unit_size:,.2f}", inline=True)
        await ctx.send(embed=embed)
    except:
        await ctx.send("❌ Invalid amount. Use: `!update 12500`")

@bot.command(name='limits')
async def set_limits(ctx, daily: str = None, single: str = None):
    """View/set exposure limits"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded, set_exposure_limits, get_bankroll_settings
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ Use `!setup` first.")
        return
    
    settings = get_bankroll_settings(discord_id)
    current = float(settings['current_bankroll'])
    
    if not daily or not single:
        daily_pct = float(settings['max_daily_exposure_pct'])
        single_pct = float(settings['max_single_game_pct'])
        
        embed = discord.Embed(title="📊 Exposure Limits", color=0x667eea)
        embed.add_field(name="Max Daily Exposure", value=f"{daily_pct}% = ${current * daily_pct / 100:,.2f}", inline=False)
        embed.add_field(name="Max Single Bet", value=f"{single_pct}% = ${current * single_pct / 100:,.2f}", inline=False)
        embed.add_field(name="Change Limits", value="`!limits 10 5` (10% daily, 5% single)", inline=False)
        await ctx.send(embed=embed)
        return
    
    try:
        daily_pct = float(daily.replace('%', ''))
        single_pct = float(single.replace('%', ''))
        set_exposure_limits(discord_id, daily_pct, single_pct)
        await ctx.send(f"✅ Limits updated: Daily **{daily_pct}%** | Single **{single_pct}%**")
    except:
        await ctx.send("❌ Invalid. Use: `!limits 10 5`")

@bot.command(name='targets')
async def set_targets(ctx, profit: str = None, stop: str = None):
    """View/set daily targets"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded, set_session_targets, get_bankroll_settings
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ Use `!setup` first.")
        return
    
    settings = get_bankroll_settings(discord_id)
    
    if not profit or not stop:
        embed = discord.Embed(title="🎯 Session Targets", color=0x667eea)
        embed.add_field(name="Daily Profit Goal", value=f"${float(settings['daily_profit_goal']):,.2f}", inline=True)
        embed.add_field(name="Stop Loss Limit", value=f"${float(settings['stop_loss_limit']):,.2f}", inline=True)
        embed.add_field(name="Change Targets", value="`!targets 500 300` ($500 goal, $300 stop)", inline=False)
        await ctx.send(embed=embed)
        return
    
    try:
        profit_goal = float(profit.replace('$', '').replace(',', ''))
        stop_loss = float(stop.replace('$', '').replace(',', ''))
        set_session_targets(discord_id, profit_goal, stop_loss)
        await ctx.send(f"✅ Targets set: Goal **${profit_goal:,.2f}** | Stop **${stop_loss:,.2f}**")
    except:
        await ctx.send("❌ Invalid. Use: `!targets 500 300`")

# ============================================================
# BET TRACKING (only in #bankroll-dashboard)
# ============================================================

@bot.command(name='bet', aliases=['follow', 'tail'])
async def follow_bet(ctx, pick_id: str = None, multiplier: float = 1.0):
    """Follow an algo pick by ID"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded
    from pick_system import follow_pick, get_pick_by_id
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ {ctx.author.mention} Use `!setup` first.")
        return
    
    if not pick_id:
        embed = discord.Embed(
            title="📝 Follow a Pick",
            description="`!bet <pick_id>` or `!bet <pick_id> <multiplier>`",
            color=0x667eea
        )
        embed.add_field(name="Examples", value=(
            "`!bet P03` — Follow prop pick P03 at full size\n"
            "`!bet G07` — Follow game pick G07\n"
            "`!bet P03 0.5` — Follow at half size\n"
            "`!bet P03 2` — Follow at double size"
        ), inline=False)
        embed.set_footer(text="Pick IDs are shown in #top-props and #game-bets")
        await ctx.send(embed=embed)
        return
    
    # Follow the pick
    result = follow_pick(discord_id, pick_id.upper(), multiplier)
    
    if not result['success']:
        await ctx.send(f"❌ {result['error']}")
        return
    
    pick = result['pick']
    
    embed = discord.Embed(
        title=f"✅ Following [{pick['pick_id']}]",
        description=f"**{pick['name']}**",
        color=0x00FF00
    )
    embed.add_field(name="Units", value=f"{result['units']:.1f}u", inline=True)
    embed.add_field(name="Your Stake", value=f"${result['stake']:,.2f}", inline=True)
    embed.add_field(name="Status", value="⏳ Pending", inline=True)
    
    if multiplier != 1.0:
        embed.add_field(name="Size", value=f"{multiplier}x original", inline=True)
    
    embed.set_footer(text="You will be notified when this pick is graded")
    await ctx.send(embed=embed)

@bot.command(name='grade')
async def grade_bet(ctx, bet_id: int = None, result: str = None):
    """Grade a bet result"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded, grade_bet as grade_bet_db
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ Use `!setup` first.")
        return
    
    if not bet_id or not result:
        await ctx.send("📊 **Grade a bet:** `!grade <id> win/loss/push`\nExample: `!grade 1 win`")
        return
    
    result = result.lower()
    result_map = {'w': 'win', 'l': 'loss', 'p': 'push'}
    result = result_map.get(result, result)
    
    if result not in ['win', 'loss', 'push']:
        await ctx.send("❌ Result must be: win, loss, or push")
        return
    
    graded = grade_bet_db(discord_id, bet_id, result)
    
    if graded:
        emoji = "✅" if result == 'win' else "❌" if result == 'loss' else "➡️"
        color = 0x00FF00 if result == 'win' else 0xFF0000 if result == 'loss' else 0xFFFF00
        
        embed = discord.Embed(title=f"{emoji} Bet #{bet_id}: {result.upper()}", color=color)
        embed.add_field(name="P/L", value=f"**${graded['pnl']:+,.2f}**", inline=True)
        embed.add_field(name="New Bankroll", value=f"${graded['new_bankroll']:,.2f}", inline=True)
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Bet not found or already graded.")

@bot.command(name='pending')
async def show_pending(ctx):
    """Show pending bets"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded, get_pending_bets
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ Use `!setup` first.")
        return
    
    bets = get_pending_bets(discord_id)
    
    if not bets:
        await ctx.send("📋 No pending bets. Log one with `!bet`")
        return
    
    embed = discord.Embed(title="📋 Pending Bets", color=0x667eea)
    total_risk = 0
    for bet in bets[:10]:
        total_risk += float(bet['stake_usd'])
        embed.add_field(
            name=f"#{bet['id']} — {bet['units']}u @ {bet['odds']:+d}",
            value=f"{bet['description'][:40]} | ${float(bet['stake_usd']):,.2f}",
            inline=False
        )
    embed.set_footer(text=f"Total at risk: ${total_risk:,.2f} | Grade: !grade <id> win/loss")
    await ctx.send(embed=embed)

@bot.command(name='history', aliases=['bets', 'record'])
async def show_history(ctx):
    """Show bet history"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded, get_bet_history, get_performance_metrics
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ Use `!setup` first.")
        return
    
    bets = get_bet_history(discord_id, 10)
    metrics = get_performance_metrics(discord_id)
    
    embed = discord.Embed(
        title="📜 Bet History",
        description=f"**Record:** {metrics['wins']}W-{metrics['losses']}L-{metrics['pushes']}P ({metrics['win_rate']:.1f}%)",
        color=0x667eea
    )
    
    if bets:
        for bet in bets[:8]:
            emoji = "✅" if bet['result'] == 'win' else "❌" if bet['result'] == 'loss' else "➡️"
            pnl = float(bet['pnl_usd'])
            embed.add_field(
                name=f"{emoji} {bet['description'][:25]}...",
                value=f"{bet['units']}u | ${pnl:+,.2f}",
                inline=True
            )
    else:
        embed.add_field(name="No bets yet", value="Log your first bet with `!bet`", inline=False)
    
    embed.set_footer(text=f"Total P/L: ${metrics['total_profit']:+,.2f} | ROI: {metrics['roi_pct']:+.1f}%")
    await ctx.send(embed=embed)

# ============================================================
# GENERAL COMMANDS (work anywhere)
# ============================================================

@bot.command(name='picks')
async def show_picks(ctx):
    """Today's top game picks"""
    try:
        from algo_agent import query_algo_agent
        async with ctx.typing():
            response = query_algo_agent("What are today's top NBA game picks with edges? Be concise.")
        await ctx.send(response[:2000])
    except Exception as e:
        await ctx.send(f"⚠️ Error: {str(e)}")

@bot.command(name='props')
async def show_props(ctx):
    """Today's top props"""
    try:
        from algo_agent import query_algo_agent
        async with ctx.typing():
            response = query_algo_agent("What are today's top NBA player prop bets? Be concise.")
        await ctx.send(response[:2000])
    except Exception as e:
        await ctx.send(f"⚠️ Error: {str(e)}")

@bot.command(name='injuries')
async def show_injuries(ctx, *, team: str = None):
    """Injury report"""
    try:
        from algo_agent import query_algo_agent
        query = f"Injuries for {team}?" if team else "Major NBA injuries today?"
        async with ctx.typing():
            response = query_algo_agent(query)
        await ctx.send(response[:2000])
    except Exception as e:
        await ctx.send(f"⚠️ Error: {str(e)}")

@bot.command(name='game')
async def analyze_game(ctx, *, team: str = None):
    """Analyze a game"""
    if not team:
        await ctx.send("Usage: `!game Lakers`")
        return
    try:
        from algo_agent import query_algo_agent
        async with ctx.typing():
            response = query_algo_agent(f"Analyze {team}'s game today. Spread, total, edges.")
        await ctx.send(response[:2000])
    except Exception as e:
        await ctx.send(f"⚠️ Error: {str(e)}")

@bot.command(name='help', aliases=['commands', 'menu', '?'])
async def show_help(ctx):
    """Show all commands"""
    embed = discord.Embed(
        title="📚 SB-ALGO Commands",
        description="Hedge fund-style sports betting intelligence",
        color=0x667eea
    )
    
    embed.add_field(
        name=f"💰 BANKROLL (#{BANKROLL_CHANNEL} only)",
        value=(
            "`!setup` — Configure bankroll\n"
            "`!bankroll` — View dashboard\n"
            "`!stake` — Bet sizes\n"
            "`!health` — Health analysis\n"
            "`!update` — Update bankroll\n"
            "`!limits` — Exposure limits\n"
            "`!targets` — Profit/loss targets"
        ),
        inline=True
    )
    
    embed.add_field(
        name="📝 BET TRACKING",
        value=(
            "`!bet <u> <odds> <pick>`\n"
            "`!grade <id> <result>`\n"
            "`!pending` — Open bets\n"
            "`!history` — Past bets"
        ),
        inline=True
    )
    
    embed.add_field(
        name="🎯 PICKS (anywhere)",
        value=(
            "`!picks` — Top games\n"
            "`!props` — Top props\n"
            "`!injuries` — Report\n"
            "`!game <team>` — Analysis"
        ),
        inline=True
    )
    
    embed.set_footer(text="SB-ALGO — Built for disciplined bettors")
    await ctx.send(embed=embed)

@bot.command(name='status')
async def show_status(ctx):
    """Bot status"""
    embed = discord.Embed(title="🤖 SB-ALGO Status", color=0x00FF00)
    embed.add_field(name="Bot", value="✅ Online", inline=True)
    embed.add_field(name="Servers", value=str(len(bot.guilds)), inline=True)
    
    try:
        from bankroll_manager import get_engine
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        embed.add_field(name="Database", value="✅ Connected", inline=True)
    except:
        embed.add_field(name="Database", value="❌ Error", inline=True)
    
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

# ============================================================
# TODAY'S SESSION (in bankroll channel)
# ============================================================

@bot.command(name='today', aliases=['session', 'day'])
async def show_today(ctx):
    """Show today's session stats"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded
    from discord_results import build_today_embed
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ {ctx.author.mention} Use `!setup` first.")
        return
    
    embed_data = build_today_embed(discord_id)
    if embed_data:
        embed = discord.Embed.from_dict(embed_data)
        await ctx.send(embed=embed)
    else:
        await ctx.send("⚠️ Could not load today's stats.")

# ============================================================
# ADMIN: GRADE ALGO PICK (for grading results channel)
# ============================================================

@bot.command(name='gradepick', aliases=['gp'])
@commands.has_permissions(administrator=True)
async def grade_algo_pick(ctx, pick_id: int = None, result: str = None):
    """Admin: Grade an algo pick (updates #results)"""
    if not pick_id or not result:
        await ctx.send("Usage: `!gradepick <pick_id> win/loss/void`")
        return
    
    result = result.lower()
    if result not in ['win', 'loss', 'void', 'w', 'l', 'v']:
        await ctx.send("❌ Result must be: win, loss, or void")
        return
    
    result_map = {'w': 'win', 'l': 'loss', 'v': 'void'}
    result = result_map.get(result, result)
    
    from discord_results import update_pick_result
    success = update_pick_result(pick_id=pick_id, result=result)
    
    if success:
        emoji = "✅" if result == 'win' else "❌" if result == 'loss' else "🟨"
        await ctx.send(f"{emoji} Pick #{pick_id} graded as **{result.upper()}**")
    else:
        await ctx.send("❌ Pick not found or error grading.")

@grade_algo_pick.error
async def grade_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Admin only command.")

# ============================================================
# MY PICKS (show user's active followed picks)
# ============================================================

@bot.command(name='mypicks', aliases=['following', 'active'])
async def show_my_picks(ctx):
    """Show your active followed picks"""
    if not is_bankroll_channel(ctx):
        await send_not_allowed(ctx)
        return
    
    from bankroll_manager import is_onboarded
    from pick_system import get_user_active_picks
    
    discord_id = str(ctx.author.id)
    
    if not is_onboarded(discord_id):
        await ctx.send(f"❌ {ctx.author.mention} Use `!setup` first.")
        return
    
    picks = get_user_active_picks(discord_id)
    
    if not picks:
        await ctx.send("📋 No active picks. Follow one with `!bet <pick_id>`")
        return
    
    embed = discord.Embed(title="🎯 Your Active Picks", color=0x667eea)
    
    total_risk = 0
    for pick in picks[:10]:
        total_risk += pick['stake']
        embed.add_field(
            name=f"[{pick['pick_id']}] {pick['name'][:30]}",
            value=f"{pick['units']}u | ${pick['stake']:,.2f}",
            inline=False
        )
    
    embed.set_footer(text=f"Total at risk: ${total_risk:,.2f} | Auto-grades when results come in")
    await ctx.send(embed=embed)

# ============================================================
# ADMIN: GRADE PICK (grades pick + all followers)
# ============================================================

@bot.command(name='gp', aliases=['gradepick'])
@commands.has_permissions(administrator=True)
async def admin_grade_pick(ctx, pick_id: str = None, result: str = None):
    """Admin: Grade an algo pick and all followers"""
    if not pick_id or not result:
        await ctx.send("Usage: `!gp <pick_id> win/loss/void`\nExample: `!gp P03 win`")
        return
    
    result = result.lower()
    result_map = {'w': 'win', 'l': 'loss', 'v': 'void', 'p': 'void'}
    result = result_map.get(result, result)
    
    if result not in ['win', 'loss', 'void']:
        await ctx.send("❌ Result must be: win, loss, or void")
        return
    
    from pick_system import grade_pick
    
    graded = grade_pick(pick_id.upper(), result)
    
    if not graded['success']:
        await ctx.send(f"❌ {graded['error']}")
        return
    
    emoji = "✅" if result == 'win' else "❌" if result == 'loss' else "🟨"
    color = 0x00FF00 if result == 'win' else 0xFF0000 if result == 'loss' else 0xFFFF00
    
    embed = discord.Embed(
        title=f"{emoji} Pick [{pick_id.upper()}] Graded: {result.upper()}",
        color=color
    )
    embed.add_field(name="Result Units", value=f"{graded['result_units']:+.1f}u", inline=True)
    embed.add_field(name="Followers Updated", value=str(len(graded['followers_graded'])), inline=True)
    
    await ctx.send(embed=embed)
    
    # DM each follower
    for follower in graded['followers_graded']:
        try:
            user = await bot.fetch_user(int(follower['discord_id']))
            dm_embed = discord.Embed(
                title=f"{emoji} Pick [{pick_id.upper()}] Result: {result.upper()}",
                color=color
            )
            dm_embed.add_field(name="Your P/L", value=f"${follower['pnl']:+,.2f}", inline=True)
            if follower['new_bankroll']:
                dm_embed.add_field(name="New Bankroll", value=f"${follower['new_bankroll']:,.2f}", inline=True)
            await user.send(embed=dm_embed)
        except:
            pass  # Can't DM user

@admin_grade_pick.error
async def admin_grade_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Admin only command.")
