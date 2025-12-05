"""
SB-ALGO AI Communication Layer
Claude API integration for translating algo outputs into natural language
"""

import os
from anthropic import Anthropic
import streamlit as st

class AlgoAI:
    """Claude API wrapper for SB-ALGO communication"""
    
    def __init__(self):
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
    
    def analyze_game(self, game_data):
        """
        Generate natural language analysis for a specific game
        
        Args:
            game_data (dict): Game information including:
                - home_team, away_team
                - spread, total, moneyline
                - algo_pick, confidence, ev
                - team_stats, injury_impact, trends
        
        Returns:
            str: Natural language game analysis
        """
        prompt = f"""You are the voice of SB-ALGO, a professional NBA betting algorithm. Analyze this game and explain the betting opportunity in 2-3 concise paragraphs.

Game: {game_data.get('away_team', 'Team A')} @ {game_data.get('home_team', 'Team B')}
Algo Pick: {game_data.get('algo_pick', 'TBD')}
Confidence: {game_data.get('confidence', 0)}%
Expected Value: {game_data.get('ev', 0)}%

Key Factors:
{game_data.get('key_factors', 'Analyzing team stats, matchup history, and current form.')}

Instructions:
1. Lead with the pick and why it's a strong play
2. Reference specific stats or trends that support the edge
3. Mention any injury impacts or situational advantages
4. Keep it direct and actionable - no fluff

Write as if you're a sharp bettor explaining your reasoning to another pro."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    
    def explain_pick(self, pick_data):
        """
        Explain why a specific pick has value
        
        Args:
            pick_data (dict): Pick details including type, line, confidence, ev
        
        Returns:
            str: Concise explanation of the pick
        """
        prompt = f"""You are SB-ALGO's voice. Explain this betting pick in 1-2 sentences.

Pick: {pick_data.get('pick', 'TBD')}
Type: {pick_data.get('type', 'Spread')}
Confidence: {pick_data.get('confidence', 0)}%
EV: {pick_data.get('ev', 0)}%

Be direct and specific about why this has edge."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    
    def analyze_player_prop(self, prop_data):
        """
        Generate analysis for player prop bets
        
        Args:
            prop_data (dict): Player prop details
        
        Returns:
            str: Natural language prop analysis
        """
        prompt = f"""You are SB-ALGO. Analyze this player prop and explain the edge in 1-2 paragraphs.

Player: {prop_data.get('player', 'Player')}
Prop: {prop_data.get('prop_type', 'Points')} {prop_data.get('line', 'TBD')}
Pick: {prop_data.get('pick', 'Over/Under')}
Hit Rate: {prop_data.get('hit_rate', 0)}%
Confidence: {prop_data.get('confidence', 0)}%

Recent Form: {prop_data.get('recent_form', 'Analyzing recent games')}
Matchup: {prop_data.get('matchup_notes', 'Checking opponent defense')}

Explain why this prop has value based on trends and matchup."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    
    def daily_summary(self, daily_data):
        """
        Generate daily market overview and top picks summary
        
        Args:
            daily_data (dict): Today's complete betting landscape
        
        Returns:
            str: Daily summary and recommendations
        """
        prompt = f"""You are SB-ALGO. Provide today's betting market overview in 2-3 paragraphs.

Games Today: {daily_data.get('games_count', 0)}
Edges Found: {daily_data.get('edges_found', 0)}
System Confidence: {daily_data.get('system_confidence', 0)}%
Best Play: {daily_data.get('best_play', 'TBD')}

Key Injuries: {daily_data.get('injury_impact', 'None significant')}
Market Notes: {daily_data.get('market_notes', 'Standard NBA slate')}

Give JJ the breakdown: what's the best opportunity today and why."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
    
    def chat(self, user_message, context=None):
        """
        Direct chat interface with the algo
        
        Args:
            user_message (str): User's question
            context (dict): Optional context about current data/picks
        
        Returns:
            str: Claude's response as the algo's voice
        """
        system_prompt = """You are SB-ALGO, a professional NBA betting algorithm. You speak directly to JJ, your creator.

Your personality:
- Direct and no-nonsense
- Results-oriented 
- Speak in facts and probabilities
- Reference specific stats and edges
- Never hedge or give generic advice

You have access to:
- 72,492+ NBA games since 1946
- 1.6M+ player statistics
- Real-time injury data
- 11 sportsbook lines
- Advanced mathematical models (Kelly Criterion, EV calculations)

When answering questions, be specific and actionable."""

        messages = [{"role": "user", "content": user_message}]
        
        if context:
            context_str = f"\n\nCurrent Context:\n{context}"
            messages[0]["content"] += context_str
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            system=system_prompt,
            messages=messages
        )
        
        return response.content[0].text


# Streamlit cached instance
@st.cache_resource
def get_algo_ai():
    """Get cached AlgoAI instance"""
    try:
        return AlgoAI()
    except Exception as e:
        st.error(f"AI Error: {str(e)}")
        return None
