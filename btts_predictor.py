"""
BTTS Daily Predictor - GitHub Actions Version
==============================================
Automated daily BTTS predictions sent to Telegram
Runs 3 times daily: 6 AM, 8 AM, 7 PM WAT
"""

import requests
import json
import os
from datetime import datetime, timedelta
import time

# =====================================================
# GET SECRETS FROM ENVIRONMENT VARIABLES
# =====================================================

FOOTBALL_API_KEY = os.environ.get('FOOTBALL_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": FOOTBALL_API_KEY}

# =====================================================
# TARGET LEAGUES (50+)
# =====================================================

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
    # Netherlands
    88: "Eredivisie", 89: "Eerste Divisie",
    # Portugal
    94: "Primeira Liga", 95: "Liga Portugal 2",
    # Other Europe
    144: "Belgium Pro League", 179: "Scottish Premiership", 180: "Scottish Championship",
    203: "Turkey Super Lig", 204: "Turkey 1. Lig", 197: "Greece Super League",
    218: "Austria Bundesliga", 207: "Switzerland Super League", 119: "Denmark Superliga",
    103: "Norway Eliteserien", 113: "Sweden Allsvenskan", 106: "Poland Ekstraklasa",
    345: "Czech First League", 235: "Russia Premier League", 333: "Ukraine Premier League",
    283: "Romania Liga 1", 210: "Croatia 1. HNL", 286: "Serbia Super Liga",
    # South America
    71: "Brazil Serie A", 72: "Brazil Serie B", 128: "Argentina Primera",
    239: "Colombia Primera A", 265: "Chile Primera", 274: "Uruguay Primera",
    # North America
    253: "MLS", 262: "Liga MX",
    # Asia
    98: "Japan J1", 99: "Japan J2", 292: "South Korea K1", 293: "South Korea K2",
    17: "China Super League", 307: "Saudi Pro League", 305: "UAE Pro League",
    188: "Australia A-League", 323: "India Super League",
    # Africa
    233: "Egypt Premier", 288: "South Africa Premier", 200: "Morocco Botola",
}

# =====================================================
# TELEGRAM FUNCTIONS
# =====================================================

def send_telegram_message(message):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print("✅ Message sent to Telegram!")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# =====================================================
# FOOTBALL API FUNCTIONS
# =====================================================

def make_api_request(endpoint, params=None):
    """Make API request"""
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ API Error: {e}")
        return None

def is_match_upcoming(fixture_datetime_str):
    """Check if match hasn't started yet"""
    try:
        # Parse fixture time
        fixture_time = datetime.fromisoformat(fixture_datetime_str.replace('Z', '+00:00'))
        current_time = datetime.utcnow().replace(tzinfo=fixture_time.tzinfo)
        
        # Match is upcoming if it's in the future
        return fixture_time > current_time
    except:
        return True

def get_upcoming_fixtures():
    """Get fixtures for today and tomorrow"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"🔍 Fetching fixtures for {today} and {tomorrow}...")
    
    all_fixtures = []
    
    # Get today's fixtures
    data_today = make_api_request("fixtures", {"date": today})
    if data_today and "response" in data_today:
        all_fixtures.extend(data_today["response"])
    
    # Get tomorrow's fixtures
    data_tomorrow = make_api_request("fixtures", {"date": tomorrow})
    if data_tomorrow and "response" in data_tomorrow:
        all_fixtures.extend(data_tomorrow["response"])
    
    # Filter by target leagues and upcoming only
    upcoming = [
        f for f in all_fixtures 
        if f["league"]["id"] in TARGET_LEAGUES 
        and is_match_upcoming(f["fixture"]["date"])
    ]
    
    print(f"✅ Found {len(upcoming)} upcoming fixtures")
    return upcoming

def get_team_stats(team_id, league_id, season=2024):
    """Get team statistics"""
    params = {
        "team": team_id,
        "league": league_id,
        "season": season
    }
    
    data = make_api_request("teams/statistics", params)
    
    if not data or "response" not in data:
        return None
    
    return data["response"]

def calculate_btts_score(fixture):
    """Calculate BTTS probability score (0-100)"""
    home_team = fixture["teams"]["home"]
    away_team = fixture["teams"]["away"]
    league_id = fixture["league"]["id"]
    
    details = {
        "home_team": home_team["name"],
        "away_team": away_team["name"],
        "league": fixture["league"]["name"],
        "time": fixture["fixture"]["date"],
        "fixture_id": fixture["fixture"]["id"],
        "criteria_met": []
    }
    
    # Get stats
    home_stats = get_team_stats(home_team["id"], league_id)
    away_stats = get_team_stats(away_team["id"], league_id)
    
    if not home_stats or not away_stats:
        return 0, details
    
    time.sleep(0.5)  # Rate limiting
    
    score = 0
    
    # Scoring criteria
    try:
        home_goals = float(home_stats["goals"]["for"]["average"]["home"] or 0)
        details["home_goals_avg"] = round(home_goals, 2)
        if home_goals >= 1.5:
            score += 20
        elif home_goals >= 1.0:
            score += 10
    except:
        details["home_goals_avg"] = "N/A"
    
    try:
        away_goals = float(away_stats["goals"]["for"]["average"]["away"] or 0)
        details["away_goals_avg"] = round(away_goals, 2)
        if away_goals >= 1.0:
            score += 20
        elif away_goals >= 0.7:
            score += 10
    except:
        details["away_goals_avg"] = "N/A"
    
    try:
        home_conceded = float(home_stats["goals"]["against"]["average"]["home"] or 0)
        details["home_conceded_avg"] = round(home_conceded, 2)
        if home_conceded >= 1.0:
            score += 20
        elif home_conceded >= 0.7:
            score += 10
    except:
        details["home_conceded_avg"] = "N/A"
    
    try:
        away_conceded = float(away_stats["goals"]["against"]["average"]["away"] or 0)
        details["away_conceded_avg"] = round(away_conceded, 2)
        if away_conceded >= 1.0:
            score += 20
        elif away_conceded >= 0.7:
            score += 10
    except:
        details["away_conceded_avg"] = "N/A"
    
    try:
        home_form = home_stats.get("form", "")
        away_form = away_stats.get("form", "")
        
        if home_form and away_form:
            home_wins = home_form.count("W")
            away_wins = away_form.count("W")
            
            if home_wins >= 2 and away_wins >= 1:
                score += 20
            elif home_wins >= 1 or away_wins >= 1:
                score += 10
    except:
        pass
    
    details["score"] = score
    return score, details

def format_time(iso_time):
    """Format ISO time to readable format (WAT)"""
    try:
        dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
        # Convert to WAT (UTC+1)
        wat_time = dt + timedelta(hours=1)
        return wat_time.strftime("%I:%M %p WAT")
    except:
        return "TBD"

# =====================================================
# MAIN ANALYSIS FUNCTION
# =====================================================

def analyze_and_send():
    """Main function - analyze matches and send to Telegram"""
    
    print("=" * 60)
    print("🏆 BTTS PREDICTOR - STARTING ANALYSIS")
    print("=" * 60)
    
    # Get upcoming fixtures
    fixtures = get_upcoming_fixtures()
    
    if not fixtures:
        msg = "❌ No upcoming fixtures found in target leagues."
        send_telegram_message(msg)
        return
    
    print(f"\n📊 Analyzing {len(fixtures)} upcoming matches...\n")
    
    analyzed = []
    
    for i, fixture in enumerate(fixtures, 1):
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        
        print(f"[{i}/{len(fixtures)}] {home} vs {away}")
        
        score, details = calculate_btts_score(fixture)
        print(f"    Score: {score}/100")
        
        if score >= 35:
            analyzed.append(details)
            print("    ✅ Qualified!")
        
        # Pause every 5 matches
        if i % 5 == 0 and i < len(fixtures):
            print("\n⏸️  Pausing...")
            time.sleep(3)
    
    # Sort by score
    analyzed.sort(key=lambda x: x["score"], reverse=True)
    
    if not analyzed or len(analyzed) < 2:
        msg = "❌ Not enough qualified BTTS matches found. Try again later!"
        send_telegram_message(msg)
        return
    
    # Get top 2
    top_2 = analyzed[:2]
    
    # Format Telegram message
    current_date = datetime.utcnow().strftime("%A, %B %d, %Y")
    current_time = datetime.utcnow().strftime("%I:%M %p UTC")
    
    message = f"""🏆 <b>BTTS DAILY PREDICTIONS</b> 🏆

📅 {current_date}
🕒 Generated at {current_time}

━━━━━━━━━━━━━━━━━━━━━━

🎯 <b>PICK #1</b>
⚽️ <b>{top_2[0]['home_team']} vs {top_2[0]['away_team']}</b>
🏆 League: {top_2[0]['league']}
⏰ Kickoff: {format_time(top_2[0]['time'])}
📊 Confidence: {top_2[0]['score']}/100
💰 Bet: <b>BTTS-YES</b>
📈 Expected Odds: 1.40-1.80

📉 Stats:
  • Home goals avg: {top_2[0].get('home_goals_avg', 'N/A')}
  • Away goals avg: {top_2[0].get('away_goals_avg', 'N/A')}
  • Home concedes: {top_2[0].get('home_conceded_avg', 'N/A')}
  • Away concedes: {top_2[0].get('away_conceded_avg', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━

🎯 <b>PICK #2</b>
⚽️ <b>{top_2[1]['home_team']} vs {top_2[1]['away_team']}</b>
🏆 League: {top_2[1]['league']}
⏰ Kickoff: {format_time(top_2[1]['time'])}
📊 Confidence: {top_2[1]['score']}/100
💰 Bet: <b>BTTS-YES</b>
📈 Expected Odds: 1.40-1.80

📉 Stats:
  • Home goals avg: {top_2[1].get('home_goals_avg', 'N/A')}
  • Away goals avg: {top_2[1].get('away_goals_avg', 'N/A')}
  • Home concedes: {top_2[1].get('home_conceded_avg', 'N/A')}
  • Away concedes: {top_2[1].get('away_conceded_avg', 'N/A')}

━━━━━━━━━━━━━━━━━━━━━━

💡 <b>BETTING ADVICE:</b>
✅ Combine in a double for better odds
✅ Expected combined odds: 1.96-3.24
✅ Always verify latest odds
✅ Bet responsibly!

🍀 <b>Good luck!</b> 🍀
"""
    
    # Send to Telegram
    success = send_telegram_message(message)
    
    if success:
        print("\n✅ Predictions sent to Telegram successfully!")
    else:
        print("\n❌ Failed to send to Telegram")

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    print("🚀 Starting BTTS Predictor...")
    print(f"📅 Run time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    analyze_and_send()
    print("\n✅ Script completed!")
