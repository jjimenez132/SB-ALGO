import os
print(f"ANTHROPIC_API_KEY exists: {bool(os.getenv('ANTHROPIC_API_KEY'))}")
print(f"Key starts with: {os.getenv('ANTHROPIC_API_KEY', 'NOT_SET')[:20]}...")

try:
    from anthropic import Anthropic
    client = Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=50,
        messages=[{"role": "user", "content": "Say hello in 5 words"}]
    )
    print(f"API works! Response: {response.content[0].text}")
except Exception as e:
    print(f"Error: {e}")
