"""
SB-ALGO AI - Wrapper for Gemini Agent
LAZY LOADING - Only imports algo_agent when functions are actually called
"""

AGENT_AVAILABLE = True  # Will be updated on first use

def get_algo_ai():
    """Get AI agent - lazy load"""
    try:
        from algo_agent import get_algo_ai as _get_algo_ai
        return _get_algo_ai()
    except Exception as e:
        print(f"AI agent not available: {e}")
        return None

def query_algo_agent(query: str):
    """Query the AI agent - lazy load"""
    try:
        from algo_agent import query_algo_agent as _query_algo_agent
        return _query_algo_agent(query)
    except Exception as e:
        return f"AI agent error: {e}"

__all__ = ['get_algo_ai', 'query_algo_agent', 'AGENT_AVAILABLE']
