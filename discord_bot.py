#!/usr/bin/env python3
"""
discord_bot.py - SB-ALGO Interactive Discord Bot
=================================================
Listens in #algo-chat and responds using Gemini AI Agent
"""
import os
import sys
import logging
import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
log = logging.getLogger(__name__)

# Environment variables
DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Allowed channels (bot only responds in these)
ALLOWED_CHANNELS = ['algo-chat', 'ask-algo', 'bot-test']

@bot.event
async def on_ready():
    log.info(f"🤖 SB-ALGO Bot is online as {bot.user}")
    log.info(f"Connected to {len(bot.guilds)} server(s)")
    
    # Set status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="NBA edges | !help"
        )
    )

@bot.event
async def on_message(message):
    # Ignore own messages
    if message.author == bot.user:
        return
    
    # Only respond in allowed channels or DMs
    if message.guild:
        channel_name = message.channel.name.lower()
        if not any(allowed in channel_name for allowed in ALLOWED_CHANNELS):
            # Check if bot was mentioned
            if bot.user not in message.mentions:
                return
    
    # Get the question
    content = message.content
    
    # Remove bot mention if present
    content = content.replace(f'<@{bot.user.id}>', '').strip()
    
    # Ignore empty messages or just commands
    if not content or content.startswith('!'):
        await bot.process_commands(message)
        return
    
    # Show typing indicator
    async with message.channel.typing():
        try:
            # Import and call the algo agent
            from algo_agent import query_algo_agent
            
            response = query_algo_agent(content)
            
            # Split response if too long (Discord limit is 2000 chars)
            if len(response) > 1900:
                chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
                for chunk in chunks:
                    await message.reply(chunk)
            else:
                await message.reply(response)
                
        except Exception as e:
            log.error(f"Error processing message: {e}")
            await message.reply(f"⚠️ Error processing request: {str(e)[:100]}")
    
    await bot.process_commands(message)

# Commands
@bot.command(name='picks')
async def get_picks(ctx):
    """Get today's top picks"""
    async with ctx.typing():
        try:
            from algo_agent import query_algo_agent
            response = query_algo_agent("What are your top picks today?")
            await ctx.reply(response)
        except Exception as e:
            await ctx.reply(f"⚠️ Error: {str(e)[:100]}")

@bot.command(name='props')
async def get_props(ctx):
    """Get today's top props"""
    async with ctx.typing():
        try:
            from algo_agent import query_algo_agent
            response = query_algo_agent("What are your best prop bets today?")
            await ctx.reply(response)
        except Exception as e:
            await ctx.reply(f"⚠️ Error: {str(e)[:100]}")

@bot.command(name='status')
async def get_status(ctx):
    """Check system status"""
    async with ctx.typing():
        try:
            from algo_agent import query_algo_agent
            response = query_algo_agent("How is the system running? Check all pipelines.")
            await ctx.reply(response)
        except Exception as e:
            await ctx.reply(f"⚠️ Error: {str(e)[:100]}")

@bot.command(name='injuries')
async def get_injuries(ctx, team: str = None):
    """Check injuries (optionally for a specific team)"""
    async with ctx.typing():
        try:
            from algo_agent import query_algo_agent
            if team:
                response = query_algo_agent(f"What are the injuries for {team}?")
            else:
                response = query_algo_agent("What are the current NBA injuries?")
            await ctx.reply(response)
        except Exception as e:
            await ctx.reply(f"⚠️ Error: {str(e)[:100]}")

@bot.command(name='game')
async def get_game(ctx, *, team: str):
    """Get analysis for a specific team's game"""
    async with ctx.typing():
        try:
            from algo_agent import query_algo_agent
            response = query_algo_agent(f"What do you have on the {team} game today?")
            await ctx.reply(response)
        except Exception as e:
            await ctx.reply(f"⚠️ Error: {str(e)[:100]}")

@bot.command(name='commands')
async def show_commands(ctx):
    """Show available commands"""
    help_text = """
**🤖 SB-ALGO Bot Commands**

**Chat directly:** Just type your question in #algo-chat

**Commands:**
`!picks` - Today's top game picks
`!props` - Today's top prop bets  
`!status` - System health check
`!injuries [team]` - Injury report (optional team)
`!game <team>` - Analysis for specific team

**Examples:**
- "What's your best play today?"
- "Any injuries on the Lakers?"
- "Explain the Cavs game"
- `!game Bulls`
- `!injuries MIA`
"""
    await ctx.reply(help_text)

def main():
    if not DISCORD_BOT_TOKEN:
        log.error("Missing DISCORD_BOT_TOKEN")
        sys.exit(1)
    
    if not DATABASE_URL:
        log.error("Missing DATABASE_URL")
        sys.exit(1)
    
    if not GOOGLE_API_KEY:
        log.error("Missing GOOGLE_API_KEY")
        sys.exit(1)
    
    log.info("Starting SB-ALGO Discord Bot...")
    bot.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    main()
