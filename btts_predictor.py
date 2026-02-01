"""
BTTS Daily Predictor - 6 AM Version
====================================
Optimized single daily run at 6 AM
Analyzes 50 matches globally, sends TOP 2 BTTS picks
Uses exactly 100 API calls efficiently

Schedule: 6:00 AM WAT daily
Coverage: Matches kicking off 12 PM - 12 AM
"""

import requests
import json
import os
from datetime import datetime, timedelta
import time
import random

# =====================================================
# CONFIGURATION
# =====================================================

FOOTBALL_API_KEY = os.environ.get('FOOTBALL_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": FOOTBALL_API_KEY}

# Target 50+ leagues for maximum coverage
TARGET_LEAGUES = {
    # England
    39: "Premier League", 40: "Championship", 41: "League One", 42: "League Two",
    # Spain
    140: "La Liga", 141: "La Liga 2",
    # Italy
    135: "Serie A", 136: "Serie B",
    # Germany
    78: "Bundesliga", 79: "Bundesliga 2", 80: "3. Liga",
    # France
    61: "Ligue 1", 62: "Ligue 2",
    # Netherlands - BTTS Goldmine
    88: "Eredivisie", 89: "Eerste Divisie",
    # Portugal
    94: "Primeira Liga", 95: "Liga Portugal 2",
    # Belgium - High scoring
    144: "Pro League",
    # Scotland
    179: "Premiership", 180: "Championship",
    # Turkey
    203: "Super Lig", 204: "1. Lig",
    # Greece
    197: "Super League",
    # Austria
    218: "Bundesliga",
    # Switzerland
    207: "Super League",
    # Denmark
    119: "Superliga",
    # Norway
    103: "Eliteserien",
    # Sweden
    113: "Allsvenskan",
    # Poland
    106: "Ekstraklasa",
    # Czech Republic
    345: "First League",
    # Russia
    235: "Premier League",
    # Ukraine
    333: "Premier League",
    # Romania
    283: "Liga 1",
    # Croatia
    210: "1. HNL",
    # Serbia
    286: "Super Liga",
    # South America
    71: "Brazil Serie A", 72: "Brazil Serie B",
    128: "Argentina Primera",
    239: "Colombia Primera A",
    265: "Chile Primera",
    274: "Uruguay Primera",
    250: "Paraguay Division",
    # North America
    253: "MLS", 262: "Liga MX",
    # Africa
    233: "Egypt Premier",
    288: "South Africa Premier",
    200: "Morocco Botola",
    186: "Algeria Ligue 1",
    202: "Tunisia Ligue 1",
}

# =====================================================
# API FUNCTIONS
# =====================================================

def make_api_request(endpoint, params=None):
    """Make API request with error handling"""
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Check for API errors
        if 'errors' in data and data['errors']:
            print(f"⚠️ API Error: {data['errors']}")
            return None
            
        return data
    except requests.exceptions.Timeout:
        print(f"❌ Timeout error for {endpoint}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

def send_telegram_message(message):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ Message sent to Telegram!")
            return True
        else:
            print(f"❌ Telegram error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Telegram send error: {e}")
        return False

# =====================================================
# MAIN LOGIC
# =====================================================

def get_today_fixtures():
    """Get fixtures for today - focusing on daytime matches"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    print(f"🔍 Fetching fixtures for {today}...")
    
    data = make_api_request("fixtures", {"date": today})
    
    if not data or "response" not in data:
        print("❌ Failed to get fixtures")
        return []
    
    all_fixtures = data["response"]
    print(f"✅ Found {len(all_fixtures)} total fixtures globally")
    
    # Filter 1: Only target leagues
    filtered = [f for f in all_fixtures if f["league"]["id"] in TARGET_LEAGUES]
    print(f"✅ {len(filtered)} fixtures in target leagues")
    
    # Filter 2: Only not started matches
    filtered = [f for f in filtered if f["fixture"]["status"]["short"] == "NS"]
    print(f"✅ {len(filtered)} upcoming matches")
    
    # Filter 3: Focus on daytime matches (12 PM onwards in local time)
    # Parse kickoff time and filter
    daytime_matches = []
    for f in filtered:
        try:
            kickoff_time = datetime.fromisoformat(f["fixture"]["date"].replace('Z', '+00:00'))
            # Convert to WAT (UTC+1)
            wat_time = kickoff_time + timedelta(hours=1)
            hour = wat_time.hour
            
            # Keep matches kicking off between 12 PM and 11:59 PM WAT
            if 12 <= hour <= 23:
                daytime_matches.append(f)
        except:
            # If we can't parse time, include it anyway
            daytime_matches.append(f)
    
    print(f"✅ {len(daytime_matches)} daytime matches (12 PM - 12 AM kickoffs)")
    
    # If we have more than 50, randomly sample to get diversity
    if len(daytime_matches) > 50:
        daytime_matches = random.sample(daytime_matches, 50)
        print(f"✅ Randomly sampled 50 matches for analysis")
    
    return daytime_matches

def get_team_stats(team_id, league_id, season=2025):
    """Get team statistics for the season"""
    params = {
        "team": team_id,
        "league": league_id,
        "season": season
    }
    
    data = make_api_request("teams/statistics", params)
    
    if not data or "response" not in data:
        return None
    
    return data["response"]

def calculate_btts_score(home_stats, away_stats):
    """
    Calculate BTTS probability score (0-100)
    
    Scoring breakdown:
    - Home team scoring: 25 points
    - Away team scoring: 25 points
    - Home team conceding: 25 points
    - Away team conceding: 25 points
    """
    score = 0
    details = {
        "home_goals_avg": "N/A",
        "away_goals_avg": "N/A",
        "home_conceded_avg": "N/A",
        "away_conceded_avg": "N/A"
    }
    
    if not home_stats or not away_stats:
        return 0, details
    
    try:
        # HOME TEAM SCORING (25 points)
        home_goals = float(home_stats.get("goals", {}).get("for", {}).get("average", {}).get("home", 0) or 0)
        details["home_goals_avg"] = round(home_goals, 2)
        
        if home_goals >= 1.8:
            score += 25
        elif home_goals >= 1.5:
            score += 20
        elif home_goals >= 1.2:
            score += 15
        elif home_goals >= 1.0:
            score += 10
    except:
        pass
    
    try:
        # AWAY TEAM SCORING (25 points)
        away_goals = float(away_stats.get("goals", {}).get("for", {}).get("average", {}).get("away", 0) or 0)
        details["away_goals_avg"] = round(away_goals, 2)
        
        if away_goals >= 1.5:
            score += 25
        elif away_goals >= 1.2:
            score += 20
        elif away_goals >= 1.0:
            score += 15
        elif away_goals >= 0.8:
            score += 10
    except:
        pass
    
    try:
        # HOME TEAM CONCEDING (25 points)
        home_conceded = float(home_stats.get("goals", {}).get("against", {}).get("average", {}).get("home", 0) or 0)
        details["home_conceded_avg"] = round(home_conceded, 2)
        
        if home_conceded >= 1.5:
            score += 25
        elif home_conceded >= 1.2:
            score += 20
        elif home_conceded >= 1.0:
            score += 15
        elif home_conceded >= 0.8:
            score += 10
    except:
        pass
    
    try:
        # AWAY TEAM CONCEDING (25 points)
        away_conceded = float(away_stats.get("goals", {}).get("against", {}).get("average", {}).get("away", 0) or 0)
        details["away_conceded_avg"] = round(away_conceded, 2)
        
        if away_conceded >= 1.5:
            score += 25
        elif away_conceded >= 1.2:
            score += 20
        elif away_conceded >= 1.0:
            score += 15
        elif away_conceded >= 0.8:
            score += 10
    except:
        pass
    
    return score, details

def analyze_matches(fixtures):
    """Analyze fixtures and score them for BTTS probability"""
    analyzed = []
    total = len(fixtures)
    
    print(f"\n📊 Starting deep analysis of {total} matches...")
    print("=" * 60)
    
    for i, fixture in enumerate(fixtures, 1):
        home_team = fixture["teams"]["home"]
        away_team = fixture["teams"]["away"]
        league_id = fixture["league"]["id"]
        
        print(f"\n[{i}/{total}] {home_team['name']} vs {away_team['name']}")
        print(f"    League: {fixture['league']['name']}")
        
        # Get team stats
        home_stats = get_team_stats(home_team["id"], league_id)
        time.sleep(0.3)  # Rate limiting
        
        away_stats = get_team_stats(away_team["id"], league_id)
        time.sleep(0.3)  # Rate limiting
        
        # Calculate score
        score, details = calculate_btts_score(home_stats, away_stats)
        
        print(f"    Score: {score}/100")
        
        if score >= 50:  # Only keep high-confidence matches
            analyzed.append({
                "fixture": fixture,
                "score": score,
                "home_team": home_team["name"],
                "away_team": away_team["name"],
                "league": fixture["league"]["name"],
                "kickoff": fixture["fixture"]["date"],
                **details
            })
            print(f"    ✅ Qualified!")
        else:
            print(f"    ❌ Below threshold")
    
    print("\n" + "=" * 60)
    print(f"✅ Analysis complete! {len(analyzed)} matches qualified")
    
    return analyzed

def select_best_picks(analyzed_matches):
    """Select the best 2 picks with smart diversity"""
    if len(analyzed_matches) == 0:
        return []
    
    # Sort by score
    analyzed_matches.sort(key=lambda x: x["score"], reverse=True)
    
    picks = []
    
    for match in analyzed_matches:
        # Rule 1: Must have good score
        if match["score"] < 50:
            continue
        
        # Rule 2: League diversity (prefer different leagues)
        if len(picks) > 0:
            if match["league"] == picks[0]["league"]:
                # Same league - only pick if score is significantly better
                if match["score"] - picks[0]["score"] < 10:
                    continue
        
        # Rule 3: Time diversity (prefer different kickoff times)
        if len(picks) > 0:
            try:
                time1 = datetime.fromisoformat(picks[0]["kickoff"].replace('Z', '+00:00'))
                time2 = datetime.fromisoformat(match["kickoff"].replace('Z', '+00:00'))
                diff_hours = abs((time2 - time1).total_seconds() / 3600)
                
                if diff_hours < 2:  # Less than 2 hours apart
                    continue
            except:
                pass
        
        picks.append(match)
        
        if len(picks) == 2:
            break
    
    # If couldn't find 2 with diversity, just take top 2
    if len(picks) < 2 and len(analyzed_matches) >= 2:
        picks = analyzed_matches[:2]
    elif len(picks) < 1 and len(analyzed_matches) >= 1:
        picks = [analyzed_matches[0]]
    
    return picks

def format_time(iso_time):
    """Format ISO time to readable WAT time"""
    try:
        dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
        wat = dt + timedelta(hours=1)
        return wat.strftime("%I:%M %p WAT")
    except:
        return "TBD"

def format_date():
    """Get current date formatted"""
    return datetime.utcnow().strftime("%A, %B %d, %Y")

# =====================================================
# MAIN EXECUTION
# =====================================================

def main():
    """Main execution function"""
    print("=" * 60)
    print("🏆 BTTS DAILY PREDICTOR - 6 AM RUN")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    # Step 1: Get today's fixtures
    fixtures = get_today_fixtures()
    
    if len(fixtures) == 0:
        msg = "❌ No upcoming daytime fixtures found in target leagues today."
        print(msg)
        send_telegram_message(msg)
        return
    
    # Step 2: Analyze matches (max 50)
    analyzed = analyze_matches(fixtures)
    
    if len(analyzed) == 0:
        msg = "❌ No matches met the minimum BTTS confidence threshold today.\n\nTry again tomorrow! 🍀"
        print(msg)
        send_telegram_message(msg)
        return
    
    # Step 3: Select best 2 picks
    picks = select_best_picks(analyzed)
    
    if len(picks) == 0:
        msg = "❌ Could not find suitable BTTS picks today.\n\nTry again tomorrow! 🍀"
        print(msg)
        send_telegram_message(msg)
        return
    
    # Step 4: Format and send message
    print("\n" + "=" * 60)
    print("📲 SENDING TO TELEGRAM")
    print("=" * 60)
    
    message = f"""🏆 <b>BTTS DAILY PREDICTIONS</b> 🏆

📅 {format_date()}
🕒 6:00 AM Analysis
🌍 Global Coverage

━━━━━━━━━━━━━━━━━━━━━━
"""
    
    for i, pick in enumerate(picks, 1):
        message += f"""
🎯 <b>PICK #{i}</b>
⚽️ <b>{pick['home_team']} vs {pick['away_team']}</b>
🏆 League: {pick['league']}
⏰ Kickoff: {format_time(pick['kickoff'])}
📊 Confidence: {pick['score']}/100
💰 Bet: <b>BTTS-YES</b>
📈 Expected Odds: 1.40-1.80

📉 Stats:
  • Home goals avg: {pick['home_goals_avg']}
  • Away goals avg: {pick['away_goals_avg']}
  • Home concedes: {pick['home_conceded_avg']}
  • Away concedes: {pick['away_conceded_avg']}

━━━━━━━━━━━━━━━━━━━━━━
"""
    
    message += """
💡 <b>BETTING ADVICE:</b>
✅ Combine in a double for better odds
✅ Expected combined odds: 1.96-3.24
✅ Always verify latest odds before betting
✅ Bet responsibly!

🍀 <b>Good luck!</b> 🍀
"""
    
    # Send to Telegram
    success = send_telegram_message(message)
    
    if success:
        print("\n✅ Picks sent successfully!")
        for i, pick in enumerate(picks, 1):
            print(f"{i}. {pick['home_team']} vs {pick['away_team']} ({pick['score']}/100)")
    else:
        print("\n❌ Failed to send to Telegram")
    
    print("\n" + "=" * 60)
    print("✅ Script completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
