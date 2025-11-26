#!/usr/bin/env python3
"""
Create Web Dashboard for NBA Betting Algo
"""
import os

print("🚀 CREATING WEB DASHBOARD...")

# Create dashboard directory
os.makedirs("~/Desktop/SB-ALGO/dashboard", exist_ok=True)

# Create main HTML file
html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NBA Algo Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .status {
            display: flex;
            gap: 20px;
            margin-top: 20px;
        }
        .status-item {
            flex: 1;
            text-align: center;
            padding: 15px;
            background: #f7f7f7;
            border-radius: 10px;
        }
        .status-value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }
        .status-label {
            color: #666;
            margin-top: 5px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .card h2 {
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }
        .pick {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            border-left: 4px solid #4CAF50;
        }
        .pick-team {
            font-weight: bold;
            font-size: 1.2em;
            color: #333;
        }
        .pick-details {
            color: #666;
            margin-top: 5px;
        }
        .confidence {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
        }
        .high { background: #4CAF50; color: white; }
        .medium { background: #FFC107; color: white; }
        .low { background: #9E9E9E; color: white; }
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 30px;
            font-size: 1em;
            cursor: pointer;
            transition: all 0.3s;
        }
        .refresh-btn:hover {
            background: #764ba2;
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        }
        .live-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            background: #4CAF50;
            border-radius: 50%;
            margin-right: 5px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }
            100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏀 NBA Betting Algorithm</h1>
            <div class="status">
                <div class="status-item">
                    <div class="status-value" id="bankroll">$5,000</div>
                    <div class="status-label">Bankroll</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="roi">+12.5%</div>
                    <div class="status-label">ROI This Week</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="record">8-2</div>
                    <div class="status-label">Last 10 Picks</div>
                </div>
                <div class="status-item">
                    <div class="status-value" id="timestamp">
                        <span class="live-indicator"></span>
                        <span id="time">LIVE</span>
                    </div>
                    <div class="status-label">Status</div>
                </div>
            </div>
            <button class="refresh-btn" onclick="refreshData()">Refresh Picks</button>
        </div>

        <div class="grid">
            <div class="card">
                <h2>🎯 Today's Best Bets</h2>
                <div id="picks">
                    <!-- Picks will be loaded here -->
                </div>
            </div>

            <div class="card">
                <h2>📊 Live Odds</h2>
                <div id="odds">
                    <!-- Odds will be loaded here -->
                </div>
            </div>

            <div class="card">
                <h2>🚨 Injury Report</h2>
                <div id="injuries">
                    <!-- Injuries will be loaded here -->
                </div>
            </div>

            <div class="card">
                <h2>📈 Performance</h2>
                <canvas id="chart"></canvas>
            </div>
        </div>
    </div>

    <script>
        function refreshData() {
            fetch('/api/picks')
                .then(res => res.json())
                .then(data => {
                    updatePicks(data);
                });
        }

        function updatePicks(data) {
            const picksDiv = document.getElementById('picks');
            picksDiv.innerHTML = data.picks.map(pick => `
                <div class="pick">
                    <div class="pick-team">${pick.team} ${pick.spread}</div>
                    <div class="pick-details">
                        ${pick.opponent} • ${pick.time}
                        <span class="confidence ${pick.confidence}">${pick.confidence.toUpperCase()}</span>
                    </div>
                </div>
            `).join('');
        }

        // Auto refresh every 5 minutes
        setInterval(refreshData, 300000);
        
        // Initial load
        refreshData();
    </script>
</body>
</html>
'''

with open(os.path.expanduser("~/Desktop/SB-ALGO/dashboard/index.html"), "w") as f:
    f.write(html_content)

print("✅ Dashboard created!")
print("\n📱 To view your dashboard:")
print("   1. Open: ~/Desktop/SB-ALGO/dashboard/index.html")
print("   2. Or run: python3 -m http.server 8080")
print("   3. Visit: http://localhost:8080")
