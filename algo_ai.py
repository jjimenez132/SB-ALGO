"""
SB-ALGO AI Communication Layer
Groq API integration for translating algo outputs into natural language
"""

import os
from groq import Groq
import streamlit as st

class AlgoAI:
    """Groq API wrapper for SB-ALGO communication"""
    
    def __init__(self):
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY not found")
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"
    
    def analyze_game(self, game_data):
        """Generate natural language analysis for a game"""
        prompt = f"""You are SB-ALGO, a professional NBA betting algorithm. Analyze this game in 2-3 SHORT paragraphs.

Game: {game_data.get('away_team')} @ {game_data.get('home_team')}
Pick: {game_data.get('algo_pick')}
Confidence: {game_data.get('confidence')}%
Edge: {game_data.get('ev')}%

Key Factors: {game_data.get('key_factors', '')}

Be direct. Lead with the pick. Reference specific stats. No fluff."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400
        )
        return response.choices[0].message.content
    
    def analyze_player_prop(self, prop_data):
        """Generate analysis for player prop bets"""
        prompt = f"""You are SB-ALGO. Analyze this prop in 1-2 SHORT paragraphs.

Player: {prop_data.get('player')}
Prop: {prop_data.get('prop_type')} {prop_data.get('line')}
Pick: {prop_data.get('pick')}
Hit Rate L10: {prop_data.get('hit_rate')}%

Recent: {prop_data.get('recent_form', '')}
Matchup: {prop_data.get('matchup_notes', '')}

Be direct. Why does this have value?"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return response.choices[0].message.content
    
    def chat(self, user_message, context=None):
        """Direct chat with the algo"""
        system = """You are SB-ALGO, a professional NBA betting algorithm. You speak to JJ, your creator.
Be direct, use stats and probabilities. You have access to 72k+ NBA games and real-time data."""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message + (f"\n\nContext: {context}" if context else "")}
        ]
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=500
        )
        return response.choices[0].message.content


@st.cache_resource
def get_algo_ai():
    """Get cached AlgoAI instance"""
    try:
        return AlgoAI()
    except Exception as e:
        return None
