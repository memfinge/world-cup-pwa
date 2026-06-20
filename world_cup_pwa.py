# world_cup_pwa.py

import os
import uuid
import json
import urllib.parse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, date
from typing import List, Optional, Dict, Any

import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
import requests
from bs4 import BeautifulSoup
from strenum import StrEnum
from supabase import Client, create_client, PostgrestAPIResponse, ClientOptions
import google.generativeai as genai

# --- 1. INITIAL CONFIGURATION & SETUP ---

# Load environment variables from .env file
load_dotenv()

# Set Streamlit page configuration for a mobile-first experience
st.set_page_config(
    page_title="WC Data Pipeline",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Inject Custom Glassmorphic Dark-Mode Stylesheet at script startup to keep it persistent
st.markdown("""
<style>
/* Base Theme & Gradient Background */
.stApp {
    background: linear-gradient(135deg, #0b0f19, #1b172b, #090a0f) !important;
    color: #e2e8f0 !important;
}

/* Glassmorphism Containers for expanders and cards */
div[data-testid="stExpander"], div[data-testid="element-container"] > div[style*="border"] {
    background: rgba(30, 41, 59, 0.45) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 12px !important;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25) !important;
    transition: all 0.3s ease !important;
    margin-bottom: 12px !important;
}

/* Interactive Card Hover Transition */
div[data-testid="stExpander"]:hover, div[data-testid="element-container"] > div[style*="border"]:hover {
    border-color: rgba(99, 102, 241, 0.35) !important;
    box-shadow: 0 12px 40px 0 rgba(99, 102, 241, 0.12) !important;
    transform: translateY(-2px) !important;
}

/* Typography Custom Fonts and Gradients */
h1, h2, h3 {
    color: #ffffff !important;
    font-family: 'Outfit', 'Inter', sans-serif !important;
    font-weight: 700 !important;
}

h1 {
    background: linear-gradient(to right, #818cf8, #c084fc, #e879f9) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    padding-bottom: 0.2em !important;
    font-size: 2.25rem !important;
}

/* Premium Buttons Styling */
button {
    background: linear-gradient(90deg, #4f46e5, #7c3aed) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.5rem 1.0rem !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px 0 rgba(99, 102, 241, 0.3) !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

button:hover {
    background: linear-gradient(90deg, #4338ca, #6d28d9) !important;
    box-shadow: 0 6px 18px 0 rgba(99, 102, 241, 0.5) !important;
    transform: translateY(-1px) !important;
}

/* Form Controls & Inputs Styling */
input, select, textarea {
    background-color: rgba(15, 23, 42, 0.5) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    color: #f1f5f9 !important;
    border-radius: 8px !important;
}

/* Metric Display Values */
div[data-testid="stMetricValue"] {
    font-weight: 800 !important;
    color: #38bdf8 !important;
}

/* AI Confidence Meter */
.confidence-meter-wrap {
    margin: 0.5rem 0 1rem 0;
}
.confidence-meter-label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
    font-size: 0.8rem;
    color: #94a3b8;
    font-family: 'Outfit', 'Inter', sans-serif;
}
.confidence-meter-label span.score-val {
    font-size: 1.1rem;
    font-weight: 800;
    color: #e2e8f0;
}
.confidence-track {
    width: 100%;
    height: 10px;
    background: rgba(255,255,255,0.07);
    border-radius: 99px;
    overflow: hidden;
    box-shadow: inset 0 1px 4px rgba(0,0,0,0.4);
}
.confidence-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Dashboard stat cards */
.stat-card {
    background: rgba(30, 41, 59, 0.55);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 1rem 1.25rem;
    text-align: center;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.stat-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 30px rgba(99,102,241,0.15);
}
.stat-card .stat-value {
    font-size: 1.8rem;
    font-weight: 800;
    color: #e2e8f0;
    font-family: 'Outfit', 'Inter', sans-serif;
}
.stat-card .stat-label {
    font-size: 0.72rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 2px;
}
.stat-card .stat-delta-pos { color: #4ade80; font-size: 0.85rem; font-weight: 600; }
.stat-card .stat-delta-neg { color: #f87171; font-size: 0.85rem; font-weight: 600; }
.stat-card .stat-delta-neu { color: #94a3b8; font-size: 0.85rem; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- 2. ENUMS AND DATA MODELS (with Pydantic for validation) ---

class LineupStatus(StrEnum):
    """Enum for match lineup status, mirroring the DB constraint."""
    PROJECTED = "Projected"
    CONFIRMED = "Confirmed"

class LedgerStatus(StrEnum):
    """Enum for ledger entry status, mirroring the DB constraint."""
    PENDING = "Pending"
    WON = "Won"
    LOST = "Lost"
    VOID = "Void"

class Match(BaseModel):
    """Pydantic model for the 'matches' table."""
    match_id: str
    kickoff_time: datetime
    home_team: str
    away_team: str
    lineup_status: LineupStatus
    home_lineup: List[str] = Field(default_factory=list)
    away_lineup: List[str] = Field(default_factory=list)
    updated_at: Optional[datetime] = None

class Odds(BaseModel):
    """Pydantic model for the 'odds' table."""
    id: Optional[int] = None
    match_id: str
    market_type: str
    selection: str
    dk_odds: int
    updated_at: Optional[datetime] = None

class LedgerEntry(BaseModel):
    """Pydantic model for the 'ledger' table."""
    slip_id: str
    match_id: str
    market_type: str
    selection: str
    base_odds: int
    unit_risk: float = Field(..., ge=0.01, le=10.0) # Example: 0.01 to 10.00 units
    status: LedgerStatus
    net_return: Optional[float] = None
    created_at: Optional[datetime] = None

    @field_validator('unit_risk')
    def unit_risk_precision(cls, v):
        return round(v, 2)

# --- 3. SUPABASE DATABASE CONNECTION ---

@st.cache_resource
def get_supabase_client() -> Client:
    """
    Creates and returns a Supabase client instance.
    Uses Streamlit's caching to maintain a single connection.
    """
    try:
        supabase_url = os.environ["SUPABASE_URL"]
        supabase_key = os.environ["SUPABASE_KEY"]
        # Explicitly setting the schema can sometimes help with stubborn caching issues.
        options = ClientOptions(schema="public")
        return create_client(supabase_url, supabase_key, options=options)
    except KeyError:
        st.error("Supabase credentials not found. Please set SUPABASE_URL and SUPABASE_KEY in your .env file.")
        st.stop()

supabase = get_supabase_client()

# --- 4. CORE APPLICATION LOGIC & PIPELINE ---

def generate_content_with_fallback(api_key: str, prompt: str, json_mode: bool = True) -> str:
    """
    Tries to generate content using a prioritized list of model candidates.
    If a model returns a 429/Quota Exceeded error, it automatically falls back
    to the next model in the list.
    """
    genai.configure(api_key=api_key)
    
    # Prioritize 1.5 flash/pro models which usually have higher/stable quotas,
    # then 1.5-flash-8b, then others. Put preview/experimental models last.
    preferred_models = [
        'gemini-1.5-flash',
        'gemini-1.5-flash-8b',
        'gemini-1.5-pro',
        'gemini-1.5-flash-latest',
        'gemini-1.5-pro-latest',
        'gemini-2.0-flash-exp',
        'gemini-2.5-flash',
        'gemini-3.5-flash',
        'gemini-3.5-pro',
        'gemini-flash-latest',
        'gemini-pro-latest'
    ]
    
    # Dynamically fetch other supported models from list_models
    api_models = []
    try:
        api_models = [m.name.replace("models/", "") for m in genai.list_models() 
                      if 'generateContent' in m.supported_generation_methods]
    except Exception as e:
        print(f"[DEBUG] Failed to list models: {e}")
        
    # Build list of all models to try, avoiding duplicates while preserving order
    all_models_to_try = []
    for model_name in preferred_models:
        if model_name not in all_models_to_try:
            all_models_to_try.append(model_name)
            
    for model_name in api_models:
        if model_name not in all_models_to_try:
            all_models_to_try.append(model_name)
            
    if not all_models_to_try:
        all_models_to_try = ['gemini-1.5-flash']
        
    last_error = None
    gen_config = {"response_mime_type": "application/json", "temperature": 0.0} if json_mode else {"temperature": 0.0}

    
    for model_name in all_models_to_try:
        try:
            print(f"[DEBUG] Attempting content generation with model: {model_name}")
            model = genai.GenerativeModel(model_name=model_name, generation_config=gen_config)
            response = model.generate_content(prompt)
            if response and response.text:
                print(f"[DEBUG] Success using model: {model_name}")
                return response.text.strip()
        except Exception as err:
            last_error = err
            err_str = str(err)
            print(f"[DEBUG] Model {model_name} failed: {err_str[:200]}")
            if "429" in err_str or "quota" in err_str.lower() or "limit" in err_str.lower():
                print("[DEBUG] Rate limit/quota error detected. Sleeping 2 seconds before fallback...")
                time.sleep(2.0)
            continue
                
    if last_error:
        raise last_error
    else:
        raise Exception("All generation models failed with no specific error.")


def calculate_kelly_fraction(base_odds: int, true_odds: int) -> float:
    """
    Calculates the suggested bankroll stake using a Half-Kelly Criterion.
    Returns the percentage as a float (e.g. 5.2 for 5.2%).
    Returns 0.0 if there is no edge (base odds are worse than true odds).
    """
    # 1. Convert to decimal odds
    if base_odds > 0:
        base_dec = (base_odds / 100.0) + 1.0
    elif base_odds < 0:
        base_dec = (100.0 / abs(base_odds)) + 1.0
    else:
        return 0.0
        
    if true_odds > 0:
        true_dec = (true_odds / 100.0) + 1.0
    elif true_odds < 0:
        true_dec = (100.0 / abs(true_odds)) + 1.0
    else:
        return 0.0

    # 2. Implied true probability p and net odds b
    p = 1.0 / true_dec
    b = base_dec - 1.0
    q = 1.0 - p
    
    if b <= 0:
        return 0.0
        
    # 3. Kelly Stake
    f_star = (p * b - q) / b
    
    # Apply Half-Kelly and format as percentage
    half_kelly = max(0.0, f_star * 0.5) * 100.0
    return round(half_kelly, 1)


def generate_projected_lineups(home_team: str, away_team: str, api_key: str) -> Optional[Dict[str, List[str]]]:
    """
    Calls Gemini to generate a realistic starting XI (11 players) for both the Home and Away teams.
    Returns a dict with 'home_lineup' and 'away_lineup' keys, or None on failure.
    """
    prompt = f"""
Identify the realistic projected starting 11 players (tactical lineups) for the World Cup 2026 match: {home_team} vs {away_team}.
For each team, list exactly 11 players who are expected to start, including their primary goalkeeper (GK), defenders, midfielders, and forwards. Use standard common names (e.g. "Musiala", "Son Heung-min").

Format your output strictly as a JSON object matching this schema:
{{
  "home_lineup": ["Player 1", "Player 2", ..., "Player 11"],
  "away_lineup": ["Player 1", "Player 2", ..., "Player 11"]
}}
"""
    try:
        content = generate_content_with_fallback(api_key, prompt, json_mode=True)
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            data = json.loads(content)
            
        home_l = data.get("home_lineup", [])
        away_l = data.get("away_lineup", [])
        
        return {
            "home_lineup": [str(p).strip() for p in home_l if p][:11],
            "away_lineup": [str(p).strip() for p in away_l if p][:11]
        }
    except Exception as e:
        print(f"[DEBUG] Error generating lineups: {e}")
        return None


def parse_time_local_as_utc(date_str: str, time_str: str) -> datetime:
    """
    Parses date and time from Wikipedia, returning a timezone-aware UTC datetime.
    Keeps the local numbers as the hour/minute representation to avoid timezone shifting
    on the Streamlit dashboard date filter.
    """
    import re
    # Replace non-breaking spaces
    time_str = time_str.replace('\xa0', ' ').strip()
    # Normalize unicode minus signs to standard hyphen-minus
    time_str = time_str.replace('\u2212', '-').replace('\u2013', '-')
    
    # Remove UTC offset part from time_str
    time_clean = re.sub(r'UTC[+-]\d+', '', time_str).strip()
    # Replace dots in a.m./p.m.
    time_clean = time_clean.replace('.', '').strip()
    
    dt_str = f"{date_str} {time_clean}"
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p")
    except Exception:
        # Fallback if no time matches
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except Exception:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            
    return dt.replace(tzinfo=timezone.utc)


@st.cache_data(ttl=1800)
def get_wikipedia_matches() -> List[Dict[str, Any]]:
    """
    Scrapes the 2026 World Cup page from Wikipedia, parsing all 104 matches.
    Returns a list of dictionaries with match data.
    """
    import re
    url = "https://en.wikipedia.org/wiki/2026_FIFA_World_Cup"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        boxes = soup.find_all(class_=re.compile(r"footballbox|vevent"))
        
        parsed = []
        for box in boxes:
            bday_span = box.find(class_="bday")
            if not bday_span:
                continue
            date_str = bday_span.get_text().strip()
            
            ftime_div = box.find(class_="ftime")
            time_raw = ftime_div.get_text().strip() if ftime_div else ""
            
            fhome_th = box.find(class_="fhome")
            home_team = ""
            if fhome_th:
                home_link = fhome_th.find("a")
                home_team = home_link.get_text().strip() if home_link else fhome_th.get_text().strip()
                
            faway_th = box.find(class_="faway")
            away_team = ""
            if faway_th:
                away_link = faway_th.find("a")
                away_team = away_link.get_text().strip() if away_link else faway_th.get_text().strip()
                
            fscore_th = box.find(class_="fscore")
            score = ""
            if fscore_th:
                score = fscore_th.get_text().strip()
                score = score.replace('\u2013', '-').replace('\u2212', '-').replace('\xa0', ' ').strip()
                
            kickoff_utc = parse_time_local_as_utc(date_str, time_raw)

            # Parse venue/city if available in the football box
            venue_city = ""
            fground = box.find(class_="fground") or box.find(class_="venue")
            if fground:
                venue_city = fground.get_text().strip().replace('\n', ' ').strip()

            parsed.append({
                "date": date_str,
                "home_team": home_team,
                "away_team": away_team,
                "kickoff_time": kickoff_utc,
                "score": score,
                "venue_city": venue_city
            })
        return parsed
    except Exception as e:
        print(f"[DEBUG] Error scraping Wikipedia matches: {e}")
        return []


# --- WC 2026 Venue → GPS coordinates for weather lookups ---
WC_2026_VENUES: Dict[str, tuple] = {
    "at&t stadium": ("Arlington, TX, USA", 32.747, -97.094),
    "sofi stadium": ("Inglewood, CA, USA", 33.953, -118.339),
    "metlife stadium": ("East Rutherford, NJ, USA", 40.813, -74.074),
    "hard rock stadium": ("Miami Gardens, FL, USA", 25.958, -80.239),
    "levi's stadium": ("Santa Clara, CA, USA", 37.403, -121.970),
    "arrowhead stadium": ("Kansas City, MO, USA", 39.049, -94.484),
    "lincoln financial field": ("Philadelphia, PA, USA", 39.901, -75.168),
    "gillette stadium": ("Foxborough, MA, USA", 42.091, -71.264),
    "lumen field": ("Seattle, WA, USA", 47.595, -122.332),
    "bc place": ("Vancouver, BC, Canada", 49.277, -123.112),
    "bmo field": ("Toronto, ON, Canada", 43.633, -79.419),
    "estadio azteca": ("Mexico City, Mexico", 19.303, -99.151),
    "estadio akron": ("Guadalajara, Mexico", 20.688, -103.467),
    "estadio bbva": ("Monterrey, Mexico", 25.669, -100.247),
    # City fallbacks
    "arlington": ("Arlington, TX, USA", 32.747, -97.094),
    "inglewood": ("Inglewood, CA, USA", 33.953, -118.339),
    "los angeles": ("Los Angeles, CA, USA", 34.052, -118.244),
    "new york": ("East Rutherford, NJ, USA", 40.813, -74.074),
    "miami": ("Miami Gardens, FL, USA", 25.958, -80.239),
    "santa clara": ("Santa Clara, CA, USA", 37.403, -121.970),
    "kansas city": ("Kansas City, MO, USA", 39.049, -94.484),
    "philadelphia": ("Philadelphia, PA, USA", 39.901, -75.168),
    "boston": ("Foxborough, MA, USA", 42.091, -71.264),
    "seattle": ("Seattle, WA, USA", 47.595, -122.332),
    "vancouver": ("Vancouver, BC, Canada", 49.277, -123.112),
    "toronto": ("Toronto, ON, Canada", 43.633, -79.419),
    "mexico city": ("Mexico City, Mexico", 19.303, -99.151),
    "guadalajara": ("Guadalajara, Mexico", 20.688, -103.467),
    "monterrey": ("Monterrey, Mexico", 25.669, -100.247),
}


def get_weather_context(venue_city: str, match_date: str) -> str:
    """
    Fetches match-day weather forecast from OpenMeteo (free, no API key required).
    Looks up venue GPS from WC_2026_VENUES dict and returns a formatted context string.
    """
    if not venue_city:
        return ""
    try:
        venue_lower = venue_city.lower()
        match_info = None
        # Exact then partial match against venue dict
        for key, val in WC_2026_VENUES.items():
            if key in venue_lower or venue_lower in key:
                match_info = val
                break
        if not match_info:
            return f"Weather: Venue '{venue_city}' not mapped to coordinates."

        city_label, lat, lon = match_info
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,weathercode",
            "timezone": "auto",
            "start_date": match_date,
            "end_date": match_date
        }
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code != 200:
            return ""

        data = resp.json()
        daily = data.get("daily", {})
        temp_max_c = daily.get("temperature_2m_max", [None])[0]
        temp_min_c = daily.get("temperature_2m_min", [None])[0]
        precip = daily.get("precipitation_sum", [None])[0] or 0
        wind = daily.get("windspeed_10m_max", [None])[0] or 0
        wcode = daily.get("weathercode", [0])[0] or 0

        wcode_map = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Icy fog",
            51: "Light drizzle", 53: "Moderate drizzle", 55: "Heavy drizzle",
            61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
            71: "Light snow", 73: "Moderate snow", 75: "Heavy snow",
            80: "Rain showers", 81: "Heavy showers", 82: "Violent showers",
            95: "Thunderstorm", 96: "Thunderstorm w/ hail", 99: "Severe thunderstorm",
        }
        condition = wcode_map.get(wcode, "Unknown")

        # Convert C to F
        def c_to_f(c):
            return round((c * 9 / 5) + 32, 1) if c is not None else "N/A"

        impacts = []
        if wind > 30:
            impacts.append(f"HIGH WIND ({wind:.0f}km/h) — expect fewer corners and suppressed total goals")
        elif wind > 20:
            impacts.append(f"Moderate wind ({wind:.0f}km/h) — may slightly affect aerial play")
        if precip > 3:
            impacts.append(f"RAIN EXPECTED ({precip:.1f}mm) — historically reduces total goals by ~0.3 and corners by ~1")
        elif precip > 0.5:
            impacts.append(f"Light precipitation ({precip:.1f}mm) — minor playing surface impact")
        temp_max_f = c_to_f(temp_max_c)
        if isinstance(temp_max_f, float) and temp_max_f > 90:
            impacts.append(f"HIGH HEAT ({temp_max_f}°F) — may impact player stamina in second half")

        impact_str = "; ".join(impacts) if impacts else "Standard conditions — no major weather factor"

        return (
            f"Venue: {venue_city} ({city_label})\n"
            f"Conditions: {condition}\n"
            f"Temp: {c_to_f(temp_min_c)}°F – {temp_max_f}°F\n"
            f"Precipitation: {precip:.1f}mm | Wind: {wind:.0f}km/h\n"
            f"Betting Impact: {impact_str}"
        )
    except Exception as e:
        print(f"[DEBUG] OpenMeteo weather fetch failed: {e}")
        return ""


def get_form_and_h2h_context(home_team: str, away_team: str) -> str:
    """
    Runs targeted searches for team recent form, H2H history, xG/stats, and referee data.
    All queries run in parallel via ThreadPoolExecutor for speed.
    """
    queries = [
        (f"{home_team} last 5 matches results goals 2026", "HOME TEAM RECENT FORM (Last 5)"),
        (f"{away_team} last 5 matches results goals 2026", "AWAY TEAM RECENT FORM (Last 5)"),
        (f"{home_team} vs {away_team} head to head history all time record", "HEAD-TO-HEAD HISTORY"),
        (f"{home_team} {away_team} expected goals xG shots statistics World Cup 2026", "xG & UNDERLYING STATS"),
        (f"referee appointed {home_team} vs {away_team} World Cup 2026 official", "REFEREE TENDENCIES"),
        (f"{home_team} tactical style formation system pressing World Cup 2026", "HOME TACTICAL STYLE"),
        (f"{away_team} tactical style formation system pressing World Cup 2026", "AWAY TACTICAL STYLE"),
    ]

    def _fetch_one(args):
        query, label = args
        snippets = ""
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.news(query, max_results=3))
                if not results:
                    results = list(ddgs.text(query, max_results=3))
                for r in results:
                    body = _trunc(r.get('body') or r.get('description') or r.get('snippet', ''))
                    snippets += f"  • {r.get('title', '')}: {body}\n"
        except Exception:
            pass

        if len(snippets.strip()) < 40:
            try:
                url = f"https://news.search.yahoo.com/search?p={urllib.parse.quote(query)}"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                resp = requests.get(url, headers=headers, timeout=8)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    for item in soup.find_all("div", class_="NewsArticle")[:3]:
                        title_tag = item.find("h4") or item.find("a")
                        snippet_tag = item.find("p") or item.find(class_="compText")
                        if title_tag:
                            snippets += f"  • {title_tag.get_text().strip()}: {_trunc(snippet_tag.get_text() if snippet_tag else '')}\n"
            except Exception:
                pass

        return label, snippets

    results_map = {}
    with ThreadPoolExecutor(max_workers=len(queries)) as executor:
        futures = {executor.submit(_fetch_one, q): q for q in queries}
        for future in as_completed(futures):
            try:
                label, snippets = future.result(timeout=15)
                results_map[label] = snippets
            except Exception:
                pass

    full_context = ""
    for _, label in queries:
        snippets = results_map.get(label, "")
        if snippets:
            full_context += f"\n[{label}]\n{snippets}"

    return full_context.strip()


def try_grounded_generation(prompt: str, api_key: str) -> Optional[str]:
    """
    Attempts to use Google Search Grounding for real-time web research during generation.
    Tries Gemini 2.0/2.5 models with grounding enabled, with a 25-second timeout.
    Returns None on any failure so the caller can fall back to manual DDG search.
    """
    genai.configure(api_key=api_key)
    grounding_models = ['gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-2.0-flash-exp']

    for model_name in grounding_models:
        try:
            # Build grounding tool — try new google_search API first, fall back to retrieval
            try:
                tool = genai.protos.Tool(google_search=genai.protos.GoogleSearch())
            except Exception:
                try:
                    tool = genai.protos.Tool(
                        google_search_retrieval=genai.protos.GoogleSearchRetrieval()
                    )
                except Exception:
                    continue

            model = genai.GenerativeModel(
                model_name=model_name,
                tools=[tool],
                generation_config={"temperature": 0.0}
            )
            response = model.generate_content(
                prompt,
                request_options={"timeout": 25}
            )
            if response and response.text:
                print(f"[DEBUG] Grounding succeeded with model: {model_name}")
                return response.text.strip()
        except Exception as e:
            err_str = str(e)
            print(f"[DEBUG] Grounding attempt failed ({model_name}): {err_str[:120]}")
            if "429" in err_str or "quota" in err_str.lower() or "limit" in err_str.lower():
                print("[DEBUG] Rate limit/quota error detected in grounding. Sleeping 2 seconds before fallback...")
                time.sleep(2.0)
            continue

    return None


def _trunc(text: str, max_chars: int = 400) -> str:
    """Truncate a string to max_chars, appending ellipsis if needed."""
    if not text:
        return ""
    text = text.strip()
    return text[:max_chars] + "..." if len(text) > max_chars else text


def clean_name(name: str) -> str:
    """Normalizes team names for fuzzy matching."""
    return (
        name.lower()
        .replace(" ", "")
        .replace("ç", "c")
        .replace("ã", "a")
        .replace("í", "i")
        .replace("é", "e")
        .replace("&", "and")
    )


def scrape_and_update_match_data(api_key: str, target_date, odds_api_key: str = ""):
    """
    Discovers actual upcoming World Cup matches by parsing the Wikipedia schedule,
    and generates realistic betting odds using Gemini.
    """
    if not api_key:
        st.error("Gemini API Key is missing. Please configure it in the sidebar.")
        return
        
    try:
        target_date_iso = target_date.strftime("%Y-%m-%d")
        target_date_str = target_date.strftime("%A, %B %d, %Y")
        
        # 1. Fetch matches from Wikipedia
        all_matches = get_wikipedia_matches()
        if not all_matches:
            st.error("Failed to parse match schedule from Wikipedia.")
            return
            
        # 2. Filter matches for target date
        day_matches = [m for m in all_matches if m["date"] == target_date_iso]
        
        if not day_matches:
            st.info(f"No matches scheduled for {target_date_str} on Wikipedia.")
            return

        # 3. Pull actual odds from The Odds API if apiKey is present
        api_odds_context = ""
        if odds_api_key:
            try:
                # Soccer FIFA World Cup sport key is 'soccer_fifa_world_cup'
                odds_url = f"https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/"
                params = {
                    "apiKey": odds_api_key,
                    "regions": "us",
                    "markets": "h2h",
                    "oddsFormat": "american"
                }
                resp = requests.get(odds_url, params=params, timeout=12)
                if resp.status_code == 200:
                    api_data = resp.json()
                    # Filter for target date matches
                    relevant_games = []
                    for game in api_data:
                        commence_time = game.get("commence_time", "")
                        if commence_time.startswith(target_date_iso):
                            relevant_games.append(game)
                    
                    if relevant_games:
                        consolidated_games = []
                        st.write(f"Found {len(relevant_games)} match(es) in The Odds API. Fetching detailed lines...")
                        def _fetch_event(game):
                            event_id = game.get("id")
                            home = game.get("home_team")
                            away = game.get("away_team")
                            event_url = f"https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/events/{event_id}/odds"
                            event_params = {
                                "apiKey": odds_api_key,
                                "regions": "us",
                                "markets": "h2h,spreads,totals,btts,alternate_totals",
                                "oddsFormat": "american"
                            }
                            priority = ["draftkings", "fanduel", "betmgm", "betrivers", "bovada", "mybookieag", "betonlineag", "betus", "lowvig"]
                            try:
                                event_resp = requests.get(event_url, params=event_params, timeout=12)
                                if event_resp.status_code == 200:
                                    event_data = event_resp.json()
                                    bookmakers = event_data.get("bookmakers", [])
                                    consolidated = {
                                        "home_team": home,
                                        "away_team": away,
                                        "commence_time": game.get("commence_time"),
                                        "event_id": event_id,
                                        "odds": {}
                                    }
                                    for bk in priority:
                                        bm = next((b for b in bookmakers if b["key"] == bk), None)
                                        if not bm: continue
                                        market = next((m for m in bm.get("markets", []) if m["key"] == "h2h"), None)
                                        if market:
                                            consolidated["odds"]["Moneyline"] = {"bookmaker": bk, "outcomes": market["outcomes"]}
                                            break
                                    for bk in priority:
                                        bm = next((b for b in bookmakers if b["key"] == bk), None)
                                        if not bm: continue
                                        market = next((m for m in bm.get("markets", []) if m["key"] == "btts"), None)
                                        if market:
                                            consolidated["odds"]["BTTS"] = {"bookmaker": bk, "outcomes": market["outcomes"]}
                                            break
                                    found_totals = False
                                    for bk in priority:
                                        bm = next((b for b in bookmakers if b["key"] == bk), None)
                                        if not bm: continue
                                        totals_markets = [m for m in bm.get("markets", []) if m["key"] in ("totals", "alternate_totals")]
                                        over_2_5 = under_2_5 = None
                                        for m in totals_markets:
                                            for out in m.get("outcomes", []):
                                                if out.get("point") == 2.5:
                                                    if out.get("name") == "Over": over_2_5 = out
                                                    elif out.get("name") == "Under": under_2_5 = out
                                        if over_2_5 and under_2_5:
                                            consolidated["odds"]["Total Goals (2.5)"] = {"bookmaker": bk, "outcomes": [over_2_5, under_2_5]}
                                            found_totals = True
                                            break
                                    if not found_totals:
                                        for bk in priority:
                                            bm = next((b for b in bookmakers if b["key"] == bk), None)
                                            if not bm: continue
                                            market = next((m for m in bm.get("markets", []) if m["key"] == "totals"), None)
                                            if market:
                                                consolidated["odds"]["Total Goals (Other)"] = {"bookmaker": bk, "outcomes": market["outcomes"]}
                                                break
                                    for bk in priority:
                                        bm = next((b for b in bookmakers if b["key"] == bk), None)
                                        if not bm: continue
                                        market = next((m for m in bm.get("markets", []) if m["key"] == "spreads"), None)
                                        if market:
                                            consolidated["odds"]["Spread"] = {"bookmaker": bk, "outcomes": market["outcomes"]}
                                            break
                                    return consolidated
                                else:
                                    raise Exception(f"Event HTTP {event_resp.status_code}")
                            except Exception as ev_err:
                                print(f"[DEBUG] Event detail fetch failed for {home} vs {away}: {ev_err}")
                                return {
                                    "home_team": home, "away_team": away,
                                    "commence_time": game.get("commence_time"), "event_id": event_id,
                                    "odds": {"Moneyline": {"bookmaker": "general_api", "outcomes": next(
                                        (m["outcomes"] for m in game.get("bookmakers", [{}])[0].get("markets", []) if m["key"] == "h2h"), []
                                    )}}
                                }

                        with ThreadPoolExecutor(max_workers=min(len(relevant_games), 5)) as ex:
                            consolidated_games = list(ex.map(_fetch_event, relevant_games))

                        api_odds_context = json.dumps(consolidated_games, indent=2)
                        st.toast(f"Successfully retrieved and consolidated real lines for {len(consolidated_games)} match(es) from The Odds API!")
                    else:
                        st.toast("No matching target date games found in Odds API response.")
                else:
                    st.warning(f"The Odds API returned status code {resp.status_code}: {resp.text}")
            except Exception as api_err:
                print(f"[DEBUG] The Odds API request failed: {api_err}")
                st.warning(f"Failed to fetch from The Odds API: {api_err}")


        # 4. Fetch Bovada FIFA World Cup player props and lines (free & keyless)
        bovada_context = {}
        try:
            bovada_url = "https://www.bovada.lv/services/sports/event/v2/events/A/description/soccer/fifa-world-cup"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            bovada_resp = requests.get(bovada_url, headers=headers, timeout=12)
            if bovada_resp.status_code == 200:
                bovada_data = bovada_resp.json()
                if bovada_data and len(bovada_data) > 0:
                    bovada_events = bovada_data[0].get("events", [])
                    print(f"[DEBUG] Fetched {len(bovada_events)} events from Bovada.")
                    for ev in bovada_events:
                        desc = ev.get("description", "")
                        if " vs " in desc:
                            parts = desc.split(" vs ")
                            home_clean = parts[0].strip().lower()
                            away_clean = parts[1].strip().lower()
                            key = f"{home_clean}-{away_clean}"
                            bovada_context[key] = ev
        except Exception as bov_err:
            print(f"[DEBUG] Bovada request failed: {bov_err}")

        # Discover daily DraftKings promos and odds boosts via web search
        dk_promo_snippets = ""
        promo_query = f"DraftKings sportsbook odds boosts promotions soccer {target_date_str}"
        try:
            from duckduckgo_search import DDGS
            with DDGS(timeout=3) as ddgs:
                results_promos = list(ddgs.news(promo_query, max_results=4))
                for r in results_promos:
                    dk_promo_snippets += f"Title: {r.get('title')}\nSnippet: {r.get('body')}\n\n"
        except Exception:
            pass
            
        if not dk_promo_snippets or len(dk_promo_snippets.strip()) < 50:
            try:
                url = f"https://news.search.yahoo.com/search?p={urllib.parse.quote(promo_query)}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                resp = requests.get(url, headers=headers, timeout=4)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    items = soup.find_all("div", class_="NewsArticle")
                    for item in items[:4]:
                        title_tag = item.find("h4") or item.find("a")
                        if not title_tag: continue
                        title = title_tag.get_text().strip()
                        snippet_tag = item.find("p") or item.find(class_="compText")
                        snippet = snippet_tag.get_text().strip() if snippet_tag else ""
                        dk_promo_snippets += f"Title: {title}\nSnippet: {snippet}\n\n"
            except Exception:
                pass

        # 5. Fetch odds news/betting prediction snippets from web search (RAG)
        def _process_single_match(m):
            match_snippets = ""
            dk_promo_local = ""
            sync_queries = [
                f"{m['home_team']} vs {m['away_team']} betting odds DraftKings",
                f"DraftKings player props shots on target {m['home_team']} vs {m['away_team']}",
                f"DraftKings promo boost {m['home_team']} vs {m['away_team']}",
            ]

            def _fetch_sync_query(q):
                snippets = ""
                try:
                    from duckduckgo_search import DDGS
                    with DDGS(timeout=3) as ddgs:
                        results = list(ddgs.news(q, max_results=3))
                        for r in results:
                            snippets += f"Title: {r.get('title')}\nSnippet: {_trunc(r.get('body', ''))}\n\n"
                except Exception:
                    pass
                return q, snippets

            # Inner thread pool for 3 queries of this match
            with ThreadPoolExecutor(max_workers=3) as ex:
                sync_futures = list(ex.map(_fetch_sync_query, sync_queries))

            for sq, sq_snippets in sync_futures:
                match_snippets += sq_snippets
                if "promo boost" in sq:
                    dk_promo_local += sq_snippets

            # Fallback to Yahoo if all DDG searches returned nothing
            if len(match_snippets.strip()) < 50:
                try:
                    query = sync_queries[0]
                    url = f"https://news.search.yahoo.com/search?p={urllib.parse.quote(query)}"
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    resp = requests.get(url, headers=headers, timeout=4)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        for item in soup.find_all("div", class_="NewsArticle")[:3]:
                            title_tag = item.find("h4") or item.find("a")
                            if not title_tag:
                                continue
                            snippet_tag = item.find("p") or item.find(class_="compText")
                            match_snippets += f"Title: {title_tag.get_text().strip()}\nSnippet: {_trunc(snippet_tag.get_text() if snippet_tag else '')}\n\n"
                except Exception:
                    pass
            
            # Parse Bovada data for this specific match
            bovada_match = None
            home_lower = m['home_team'].lower()
            away_lower = m['away_team'].lower()
            home_clean = clean_name(home_lower)
            away_clean = clean_name(away_lower)
            
            for key, ev in bovada_context.items():
                if "-" in key:
                    parts = key.split("-")
                    k_home = clean_name(parts[0])
                    k_away = clean_name(parts[1])
                    if (home_clean in k_home or k_home in home_clean) and (away_clean in k_away or k_away in away_clean):
                        bovada_match = ev
                        break
                        
            bovada_odds_summary = {}
            if bovada_match:
                display_groups = bovada_match.get("displayGroups", [])
                for dg in display_groups:
                    dg_desc = dg.get("description", "")
                    if dg_desc == "Goalscorer":
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            if m_desc == "Anytime Goal Scorer":
                                outcomes = []
                                for out in market.get("outcomes", []):
                                    outcomes.append({
                                        "player": out.get("description"),
                                        "price": out.get("price", {}).get("american")
                                    })
                                bovada_odds_summary["Anytime Goalscorer"] = outcomes
                    elif dg_desc == "Assists":
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            if m_desc == "To Assist a Goal":
                                outcomes = []
                                for out in market.get("outcomes", []):
                                    outcomes.append({
                                        "player": out.get("description"),
                                        "price": out.get("price", {}).get("american")
                                    })
                                bovada_odds_summary["To Assist a Goal"] = outcomes
                    elif dg_desc == "Corners":
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            if m_desc == "Total Corners":
                                outcomes = []
                                for out in market.get("outcomes", []):
                                    outcomes.append({
                                        "selection": out.get("description"),
                                        "price": out.get("price", {}).get("american")
                                    })
                                bovada_odds_summary["Corners"] = outcomes
                    elif dg_desc == "Game Props":
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            if m_desc == "Both Teams To Score":
                                outcomes = []
                                for out in market.get("outcomes", []):
                                    outcomes.append({
                                        "selection": out.get("description"),
                                        "price": out.get("price", {}).get("american")
                                    })
                                bovada_odds_summary["Both Teams to Score"] = outcomes

            return m, match_snippets, bovada_odds_summary, dk_promo_local

        # Execute news fetching and Bovada summaries in parallel across all matches
        with ThreadPoolExecutor(max_workers=min(len(day_matches), 4)) as outer_ex:
            futures = [outer_ex.submit(_process_single_match, m) for m in day_matches]
            results = [f.result() for f in futures]

        rag_search_context = ""
        bovada_all_matches_summary = {}
        for m, match_snippets, bovada_odds_summary, dk_promo_local in results:
            rag_search_context += f"=== Match: {m['home_team']} vs {m['away_team']} ===\n{match_snippets}\n"
            bovada_all_matches_summary[f"{m['home_team']} vs {m['away_team']}"] = bovada_odds_summary
            dk_promo_snippets += dk_promo_local

        bovada_odds_context = json.dumps(bovada_all_matches_summary, indent=2)
        dk_promos_context = dk_promo_snippets.strip()


        # Prepare data for Gemini to generate match IDs and odds
        target_matches_data = []
        for m in day_matches:
            target_matches_data.append({
                "home_team": m["home_team"],
                "away_team": m["away_team"],
                "kickoff_time": m["kickoff_time"].isoformat()
            })

        # 5. Call Gemini to generate match IDs and odds
        
        prompt = f"""
Based on the following actual World Cup 2026 matches scheduled for {target_date_str}:
{json.dumps(target_matches_data, indent=2)}

We have fetched official live market odds data from The Odds API (if available):
{api_odds_context if api_odds_context else "None available"}

We have also fetched live player props, assists, and corners from Bovada (if available):
{bovada_odds_context if bovada_odds_context else "None available"}

And we have scraped the following recent web search snippets (including player prop lines and sportsbook previews) for these matchups:
{rag_search_context if rag_search_context else "None available"}

We have also scraped the following general and match-specific DraftKings promotions and odds boosts snippets:
{dk_promos_context if dk_promos_context else "None available"}

Task:
Generate a unique match_id (e.g. "GER-CIV-2026") for each match, and provide realistic DraftKings betting odds (Moneyline, BTTS, Total Goals Over/Under, Spread, Corners Over/Under, Anytime Goalscorer, Player Shots Over/Under, Player Shots on Target Over/Under, and Promo/Boost) based on the team strengths, playing styles, and the real market lines provided above.

CRITICAL ODDS MAPPING REQUIREMENTS:
1. Ground your generated odds on the consolidated live market odds (from The Odds API, Bovada, and web search snippets):
   - For each match, if The Odds API data has consolidated odds for "Moneyline", "BTTS", "Total Goals (2.5)", or "Spread", you MUST output those exact points and price values in your output JSON fields. For example, if BTTS Yes is -165 in the API data, you MUST output -165. If Total Goals Over 2.5 is -164 in the API data, you MUST output Over 2.5 as -164.
   - If the Bovada data contains "Anytime Goalscorer" or "To Assist a Goal" odds, you MUST output those exact player selections and prices in your Anytime Goalscorer fields. If Bovada contains "Corners" (e.g. Over/Under 9.5 Corners), you MUST output that corner line and price.
   - If web search snippets mention specific player props or lines (e.g., Alexander Isak over 1.5 shots on target is +270), you MUST output those exact prices.
   - If general DraftKings promotions, odds boosts, or match-specific promos/boosts are found in the snippets (e.g., "Alexander Isak to score boosted to +300", or a general odds boost), you MUST output these under market_type: "Promo/Boost" with the corresponding selection description and boosted odds.
   - Only simulate or estimate odds if real market data for that specific market/selection is completely absent from all sources.



Format your output strictly as a JSON object matching this schema:
{{
  "matches": [
     {{
        "match_id": "string (unique ID like GER-CIV-2026)",
        "kickoff_time": "string (matching the kickoff_time provided)",
        "home_team": "string (matching the home_team provided)",
        "away_team": "string (matching the away_team provided)",
        "lineup_status": "Projected",
        "home_lineup": [],
        "away_lineup": []
     }}
  ],
  "odds": [
     {{
        "match_id": "string (matching the match_id above)",
        "market_type": "Moneyline",
        "selection": "string (Home Team name, Away Team name, or Draw)",
        "dk_odds": integer
     }},
     {{
        "match_id": "string (matching the match_id above)",
        "market_type": "BTTS",
        "selection": "Yes",
        "dk_odds": integer
     }},
     {{
        "match_id": "string (matching the match_id above)",
        "market_type": "BTTS",
        "selection": "No",
        "dk_odds": integer
     }},
     {{
        "match_id": "string (matching the match_id above)",
        "market_type": "Total Goals",
        "selection": "string (e.g., Over 2.5 or Over 3.5)",
        "dk_odds": integer
     }},
     {{
        "match_id": "string (matching the match_id above)",
        "market_type": "Total Goals",
        "selection": "string (e.g., Under 2.5 or Under 3.5)",
        "dk_odds": integer
     }},
     {{
        "match_id": "string (matching the match_id above)",
        "market_type": "Spread",
        "selection": "string (e.g., Germany -1.5 or Germany -0.5)",
        "dk_odds": integer
     }},
     {{
        "match_id": "string (matching the match_id above)",
        "market_type": "Spread",
        "selection": "string (e.g., Ivory Coast +1.5 or Ivory Coast +0.5)",
        "dk_odds": integer
     }},
     {{
        "match_id": "string (matching the match_id above)",
        "market_type": "Corners",
        "selection": "string (e.g., Over 9.5 Corners or Under 9.5 Corners)",
        "dk_odds": integer
     }},
     {{
        "match_id": "string (matching the match_id above)",
        "market_type": "Anytime Goalscorer",
        "selection": "string (e.g., Player Name to Score)",
        "dk_odds": integer
     }},
      {{
        "match_id": "string (matching the match_id above)",
        "market_type": "Player Shots",
        "selection": "string (e.g., Player Name Over 2.5 Shots or Player Name Under 2.5 Shots)",
        "dk_odds": integer
      }},
      {{
        "match_id": "string (matching the match_id above)",
        "market_type": "Player Shots on Target",
        "selection": "string (e.g., Player Name Over 1.5 Shots on Target or Player Name Under 1.5 Shots on Target)",
        "dk_odds": integer
      }},
      {{
        "match_id": "string (matching the match_id above)",
        "market_type": "Promo/Boost",
        "selection": "string (e.g., Alexander Isak to Score (Boosted +300, was +220))",
        "dk_odds": integer
      }}
   ]
}}

Guidelines:
1. Generate three Moneyline selections per match: the Home Team name, the Away Team name, and "Draw" exactly.
2. Generate two BTTS selections per match: "Yes" and "No".
3. Generate two Total Goals selections per match: "Over X.5" and "Under X.5" (where X.5 is a realistic line for the match, typically 1.5, 2.5, or 3.5 based on team offensive/defensive styles).
4. Generate two Spread selections per match: one for the Home Team (e.g., Home Team name -1.5 or -2.5) and one for the Away Team (e.g., Away Team name +1.5 or +2.5), using a realistic handicap line based on the strength difference between the teams (do not use +0.5 or -0.5 spreads, as those are equivalent to Double Chance or Moneyline).
5. Generate two Corners selections per match: "Over Y.5 Corners" and "Under Y.5 Corners" (where Y.5 is a realistic corner line, typically 8.5, 9.5, or 10.5 depending on tactical wing play and styles).
6. Generate four Anytime Goalscorer selections per match: 2 expected key players/star strikers per team (e.g., "Harry Kane to Score").
7. Generate four Player Shots selections per match: Over and Under lines for 1 key shooter per team (e.g., "Musiala Over 2.5 Shots" and "Musiala Under 2.5 Shots", and "Haller Over 1.5 Shots" and "Haller Under 1.5 Shots").
8. Generate four Player Shots on Target selections per match: Over and Under lines for 1 key shooter per team (e.g., "Musiala Over 1.5 Shots on Target" and "Musiala Under 1.5 Shots on Target", and "Haller Over 0.5 Shots on Target" and "Haller Under 0.5 Shots on Target").
9. If any DraftKings odds boosts, super boosts, or promotions are found in the search snippets for a match, generate a "Promo/Boost" market type entry with a descriptive selection string and the boosted odds value (e.g. 300 for +300).
10. Use realistic betting odds representation (American odds, e.g. +150, -110, etc.).
"""
        content = generate_content_with_fallback(api_key, prompt, json_mode=True)
        
        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as je:
            print(f"[DEBUG] JSONDecodeError in scrape_and_update_match_data: {je}. Attempting cleanup...")
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            try:
                data = json.loads(content)
            except Exception as e2:
                print(f"[DEBUG] Failed to parse JSON even after cleanup. Error: {e2}\nRaw content: {content}")
                st.error(f"Failed to parse AI-generated odds: {e2}")
                return
            
        discovered_matches = data.get("matches", [])
        discovered_odds = data.get("odds", [])
        
        # Adjust any Spread odds that have a +/-0.5 handicap to the Moneyline category
        import re
        for o in discovered_odds:
            if o.get("market_type") == "Spread":
                sel = o.get("selection", "")
                if re.search(r"[+-]0\.5$", sel.strip()):
                    o["market_type"] = "Moneyline"
                    print(f"[DEBUG] Re-mapped selection '{sel}' to Moneyline category")
        
        if not discovered_matches:
            print(f"[DEBUG] AI odds generation returned: {content}")
            st.info(f"Failed to generate match details for {target_date_str}.")
            return

        # Clear existing matches and odds for this target date to prevent duplicates/stale data
        # But first snapshot existing odds for line movement detection
        line_movement_data: Dict[str, int] = {}
        try:
            matches_to_del = supabase.table("matches").select("match_id").filter("kickoff_time", "gte", f"{target_date_iso}T00:00:00+00:00").filter("kickoff_time", "lte", f"{target_date_iso}T23:59:59+00:00").execute()
            ids_to_del = [m['match_id'] for m in matches_to_del.data]
            if ids_to_del:
                # Snapshot current odds BEFORE deleting (line movement baseline)
                existing_odds_resp = supabase.table("odds").select("match_id,market_type,selection,dk_odds").in_("match_id", ids_to_del).execute()
                for o in existing_odds_resp.data:
                    key = f"{o['match_id']}|{o['market_type']}|{o['selection']}"
                    line_movement_data[key] = o['dk_odds']
                print(f"[DEBUG] Snapshotted {len(line_movement_data)} existing odds for line movement detection.")
                supabase.table("odds").delete().in_("match_id", ids_to_del).execute()
                supabase.table("matches").delete().in_("match_id", ids_to_del).execute()
        except Exception as db_err:
            print(f"[DEBUG] Failed to clear matches/odds for {target_date_iso}: {db_err}")

        # Store line movement snapshot and venue map in session state for use by evaluation
        st.session_state['line_movement_data'] = line_movement_data

        # Build a venue map from the wikipedia matches for this date
        venue_map = {}
        for m in day_matches:
            key = f"{m['home_team']}|{m['away_team']}"
            venue_map[key] = m.get('venue_city', '')
        st.session_state['venue_map'] = venue_map

        # Insert discovered matches and odds into the Supabase database
        valid_matches = []
        for m in discovered_matches:
            try:
                ktime = datetime.fromisoformat(m["kickoff_time"].replace("Z", "+00:00"))
            except Exception:
                ktime = datetime.now(timezone.utc)
                
            match_obj = Match(
                match_id=m["match_id"],
                kickoff_time=ktime,
                home_team=m["home_team"],
                away_team=m["away_team"],
                lineup_status=m.get("lineup_status", LineupStatus.PROJECTED),
                home_lineup=m.get("home_lineup", []),
                away_lineup=m.get("away_lineup", [])
            )
            valid_matches.append(match_obj)

        if valid_matches:
            supabase.table("matches").upsert([m.model_dump(mode='json', exclude={'updated_at'}) for m in valid_matches]).execute()
            st.toast(f"Successfully sync'ed and updated {len(valid_matches)} matches.")

        if discovered_odds:
            supabase.table("odds").upsert(discovered_odds, on_conflict="match_id,market_type,selection").execute()
            st.toast(f"Successfully generated and updated {len(discovered_odds)} odds entries.")
            
    except Exception as e:
        print(f"[DEBUG] Error during match scraping: {e}")
        st.error(f"Error during match scraping: {e}")


def calculate_parlay_odds(odds_list: list[int]) -> int:
    """Calculates combined American odds for a list of individual American odds legs."""
    if not odds_list:
        return 100
    multipliers = []
    for odds in odds_list:
        if odds > 0:
            mult = (odds / 100.0) + 1.0
        else:
            mult = (100.0 / abs(odds)) + 1.0
        multipliers.append(mult)
        
    total_mult = 1.0
    for m in multipliers:
        total_mult *= m
        
    if total_mult >= 2.0:
        ans = (total_mult - 1.0) * 100
    else:
        ans = -100 / (total_mult - 1.0)
    return int(round(ans))


def evaluate_tactical_matchups_ai(match: Match, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Evaluates tactical matchups with comprehensive multi-source research:
    - Google Search Grounding (with DDG/Yahoo fallback)
    - Team recent form, H2H history, xG/stats, referee data
    - Venue weather from OpenMeteo
    - Line movement detection
    """
    if not api_key:
        return None

    try:
        # --- 1. Retrieve live market odds from database ---
        odds_resp = supabase.table("odds").select("*").eq("match_id", match.match_id).execute()
        odds_data = odds_resp.data
        if not odds_data:
            return None
        valid_options_str = "\n".join(
            [f"- Selection: '{o['selection']}' | Market Type: '{o['market_type']}'" for o in odds_data]
        )

        # --- 2. Line movement context (from sync snapshot) ---
        line_movement_data = st.session_state.get('line_movement_data', {})
        line_movement_str = ""
        if line_movement_data:
            movements = []
            for o in odds_data:
                key = f"{o['match_id']}|{o['market_type']}|{o['selection']}"
                old_odds = line_movement_data.get(key)
                if old_odds is not None and old_odds != o['dk_odds']:
                    delta = o['dk_odds'] - old_odds
                    direction = "▲ SHARPER" if delta < 0 else "▼ LONGER"
                    movements.append(
                        f"  {o['market_type']}: {o['selection']} moved {old_odds:+d} → {o['dk_odds']:+d} ({direction}, Δ{delta:+d})"
                    )
            if movements:
                line_movement_str = "\n".join(movements)
                print(f"[DEBUG] Detected {len(movements)} line movement(s) for {match.match_id}")

        # --- 3. Venue weather context ---
        match_date_str = match.kickoff_time.strftime("%Y-%m-%d")
        venue_map = st.session_state.get('venue_map', {})
        venue_city = venue_map.get(f"{match.home_team}|{match.away_team}", "")
        weather_str = get_weather_context(venue_city, match_date_str) if venue_city else ""
        print(f"[DEBUG] Weather context for {match.match_id}: {weather_str[:80] if weather_str else 'N/A'}")

        # --- 4. Form, H2H, xG, referee context ---
        print(f"[DEBUG] Fetching form/H2H/xG/referee context for {match.home_team} vs {match.away_team}...")
        extended_research = get_form_and_h2h_context(match.home_team, match.away_team)

        # --- 5. General match news (DDG/Yahoo) ---
        raw_research = ""
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                query = f"{match.home_team} vs {match.away_team} world cup 2026 team news injuries"
                results = list(ddgs.news(query, max_results=5))
                if not results:
                    results = list(ddgs.news(f"{match.home_team} vs {match.away_team} football", max_results=5))
                for r in results:
                    raw_research += f"  • {r.get('title')}: {r.get('body', '')}\n"
        except Exception as ddg_err:
            print(f"[DEBUG] DDG news failed: {ddg_err}")

        # Fallback to Yahoo News
        if len(raw_research.strip()) < 50:
            try:
                query = f"{match.home_team} vs {match.away_team} world cup 2026 team news"
                url = f"https://news.search.yahoo.com/search?p={urllib.parse.quote(query)}"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    for item in soup.find_all("div", class_="NewsArticle")[:5]:
                        title_tag = item.find("h4") or item.find("a")
                        snippet_tag = item.find("p") or item.find(class_="compText")
                        if title_tag:
                            raw_research += f"  • {title_tag.get_text().strip()}: {snippet_tag.get_text().strip() if snippet_tag else ''}\n"
            except Exception as yahoo_err:
                print(f"[DEBUG] Yahoo News fallback failed: {yahoo_err}")

        # --- 6. Build structured prompt ---
        prompt = f"""
You are an elite sports betting analyst, oddsmaker, and tactical football expert.
Your task: evaluate the World Cup 2026 match {match.home_team} vs {match.away_team} using ALL data sections below.
For EVERY recommendation, explicitly cite which section(s) of data most influenced it.
All bet types are on the table: Moneyline, BTTS, Total Goals, Spread, Corners, Anytime Goalscorer, Player Shots, Player Shots on Target, Promo/Boost, SGP.

══════════════════════════════════════════
[SECTION 1: LIVE ODDS & LINE MOVEMENT]
══════════════════════════════════════════
Current DraftKings Odds:
{json.dumps(odds_data, indent=2)}

Line Movement Since Last Sync (sharp money indicator):
{line_movement_str if line_movement_str else "No prior snapshot available (first sync or no change)."}
NOTE: Lines moving shorter (more negative) WITHOUT proportional public volume = sharp/professional money. This is a HIGH-VALUE signal.

══════════════════════════════════════════
[SECTION 2: CONFIRMED LINEUPS]
══════════════════════════════════════════
{match.home_team}: {", ".join(match.home_lineup) if match.home_lineup else 'Not yet confirmed'}
{match.away_team}: {", ".join(match.away_lineup) if match.away_lineup else 'Not yet confirmed'}

══════════════════════════════════════════
[SECTION 3: TEAM FORM, H2H HISTORY, xG & REFEREE]
══════════════════════════════════════════
{extended_research if extended_research else 'No extended research data retrieved.'}

══════════════════════════════════════════
[SECTION 4: MATCH NEWS & INJURY INTEL]
══════════════════════════════════════════
{raw_research if raw_research else 'No match news retrieved — use your knowledge base.'}

══════════════════════════════════════════
[SECTION 5: VENUE & WEATHER CONDITIONS]
══════════════════════════════════════════
{weather_str if weather_str else 'Venue/weather data not available for this match.'}
NOTE: Wind > 30km/h suppresses corners and total goals. Rain > 3mm reduces total goals ~0.3. Heat > 90°F impacts second-half intensity.

══════════════════════════════════════════
[VALID BETTING OPTIONS — USE EXACTLY]
══════════════════════════════════════════
{valid_options_str}

══════════════════════════════════════════
ANALYSIS TASKS:
══════════════════════════════════════════
1. Injuries & absences: Extract from Section 3/4 or your knowledge base for both teams.
2. Key tactical battle: Identify the single most decisive unit or player matchup.
3. Form analysis: Use Section 3 form data. Which team has momentum? Any goal-scoring droughts?
4. H2H patterns: Does historical record suggest a tendency (e.g., low-scoring, home team dominant)?
5. xG/stats analysis: If underlying data shows a team scores fewer goals than expected or concedes fewer, weight this toward Total Goals/BTTS markets.
6. Weather impact: If Section 5 shows adverse conditions (wind, rain), adjust corners/totals recommendations accordingly.
7. Line movement: If any line moved sharper (Section 1), presume sharp action — consider fading public or following the sharp side.
8. Referee tendency: If referee data suggests high card rates, note potential impact on bookings markets.
9. Tactical style clash (NEW): Using Sections 3, 4, and your own knowledge, explicitly analyze the style matchup:
   - What formation/system does each team use?
   - Is one team a high-press side facing a slow-buildup team? A possession side facing a low-block?
   - Which team's style exploits the other's known weakness?
   - Does this style clash favor high or low total goals? More or fewer corners? More or fewer cards?
   - Use this style analysis to refine ALL your Total Goals, BTTS, Corners, and Spread recommendations.
10. Fair value: For each recommended selection, estimate your calculated "true odds" using all above data.
11. Recommend ALL positive-EV selections. For Promo/Boost, compare boosted odds vs your true odds.
12. If 2+ value picks exist, evaluate whether combining them into an SGP makes betting sense:
    - Only construct an SGP if the legs have a strong positive correlation (e.g. Under 2.5 and Underdog Spread) such that the parlay offers a correlation edge (i.e. winning one leg significantly increases the probability of winning the other).
    - Do NOT construct an SGP if the picks are uncorrelated (e.g. an anytime goalscorer from team A and under corners), negatively correlated, or simply stack redundant risk on the same game script without a clear mathematical correlation advantage.
    - The rationale for the SGP MUST explain the correlation dynamics and why doubling down in a parlay makes betting sense for this specific matchup.
13. Conviction level: "High" (multiple confirming signals from different sections), "Medium" (1-2 signals), "Low" (single signal or borderline).
14. For each pick, populate `"research_summary"` with 2-3 bullet points citing the SPECIFIC data that drove the recommendation.

Return ONLY a valid JSON object matching this schema:
{{
  "injuries": {{
    "home_team_absences": [{{
      "player": "Name",
      "status": "Out|Questionable|Doubtful",
      "reason": "reason"
    }}],
    "away_team_absences": [{{
      "player": "Name",
      "status": "Out|Questionable|Doubtful",
      "reason": "reason"
    }}]
  }},
  "key_battle": "1-2 sentence tactical battle description",
  "recommendations": [
    {{
      "selection": "exact selection string from valid options",
      "market_type": "exact market_type from valid options OR 'SGP'",
      "true_odds": integer,
      "rationale": "2-3 sentence explanation citing specific data sections",
      "conviction": "High|Medium|Low",
      "research_summary": ["data-backed bullet 1", "data-backed bullet 2"],
      "legs": [{{
        "selection": "leg selection matching live odds exactly",
        "market_type": "leg market_type matching live odds exactly"
      }}],
      "base_odds": integer
    }}
  ]
}}
If no value exists anywhere, return `"recommendations": []`.
"""
        # --- 7. Try Google Search Grounding first; fall back to standard generation ---
        content = None
        grounding_used = False
        try:
            grounded_result = try_grounded_generation(prompt, api_key)
            if grounded_result:
                content = grounded_result
                grounding_used = True
        except Exception as grounding_err:
            print(f"[DEBUG] Grounding wrapper error: {grounding_err}")

        if not content:
            print(f"[DEBUG] Using standard generation (grounding unavailable or failed).")
            content = generate_content_with_fallback(api_key, prompt, json_mode=True)

        # Build enriched raw_research string for display in UI
        raw_research_display = ""
        if grounding_used:
            raw_research_display = "[Google Search Grounding Active — AI searched the web in real-time]\n\n"
        raw_research_display += f"[MATCH NEWS]\n{raw_research}\n\n[FORM / H2H / xG / REFEREE]\n{extended_research}\n\n[WEATHER]\n{weather_str}\n\n[LINE MOVEMENT]\n{line_movement_str or 'None detected'}"

        # Print the raw content to your terminal for easy debugging
        print(f"\n--- [DEBUG] Gemini Raw Response for {match.match_id} (grounding={grounding_used}) ---")
        print(content)
        print("----------------------------------------------------\n")
        
        # Parse the JSON response
        try:
            data = json.loads(content)
        except json.JSONDecodeError as je:
            print(f"[DEBUG] JSONDecodeError: {je}. Attempting cleanup...")
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            try:
                data = json.loads(content)
            except Exception as e2:
                print(f"[DEBUG] Failed to parse JSON even after cleanup: {e2}")
                return None
            
        recommendations = data.get("recommendations", [])
        valid_picks = []
        
        for rec in recommendations:
            sel = rec.get("selection")
            mtype = rec.get("market_type")
            if not sel or not mtype:
                print(f"[DEBUG] Selection or Market Type missing in recommendation keys.")
                continue
                
            if mtype.upper() == "SGP":
                legs = rec.get("legs", [])
                if not legs or len(legs) < 2:
                    print(f"[DEBUG] SGP must have at least 2 legs.")
                    continue
                    
                validated_legs = []
                leg_odds_list = []
                valid_sgp = True
                for leg in legs:
                    leg_sel = leg.get("selection")
                    leg_mtype = leg.get("market_type")
                    if not leg_sel or not leg_mtype:
                        valid_sgp = False
                        break
                        
                    leg_match_odds = next((o for o in odds_data if o['selection'].lower() == leg_sel.lower() and o['market_type'].lower() == leg_mtype.lower()), None)
                    if not leg_match_odds:
                        leg_match_odds = next((o for o in odds_data if (leg_sel.lower() in o['selection'].lower() or o['selection'].lower() in leg_sel.lower()) and o['market_type'].lower() == leg_mtype.lower()), None)
                        
                    if not leg_match_odds:
                        print(f"[DEBUG] SGP leg '{leg_sel}' | '{leg_mtype}' could not be matched to database options.")
                        valid_sgp = False
                        break
                        
                    validated_legs.append({
                        "match_id": match.match_id,
                        "selection": leg_match_odds["selection"],
                        "market_type": leg_match_odds["market_type"],
                        "base_odds": leg_match_odds["dk_odds"],
                        "home_team": match.home_team,
                        "away_team": match.away_team
                    })
                    leg_odds_list.append(leg_match_odds["dk_odds"])
                    
                if not valid_sgp:
                    continue
                    
                base_odds = rec.get("base_odds")
                if not base_odds:
                    base_odds = calculate_parlay_odds(leg_odds_list)
                    
                validated_rec = {
                    "match_id": match.match_id,
                    "selection": sel,
                    "market_type": "SGP",
                    "base_odds": int(base_odds),
                    "true_odds": rec.get("true_odds"),
                    "rationale": rec.get("rationale"),
                    "conviction": rec.get("conviction", "Medium"),
                    "research_summary": rec.get("research_summary", []),
                    "raw_research": raw_research_display,
                    "legs": validated_legs,
                    "is_taxed": False
                }
                if validated_rec["true_odds"] is not None:
                    validated_rec["is_taxed"] = validated_rec["base_odds"] < validated_rec["true_odds"]
                    
                print(f"[DEBUG] Successfully validated AI SGP pick: {validated_rec['selection']} at {validated_rec['base_odds']}")
                valid_picks.append(validated_rec)
                
            else:
                matching_odds = next((o for o in odds_data if o['selection'].lower() == sel.lower() and o['market_type'].lower() == mtype.lower()), None)
                
                if not matching_odds:
                    matching_odds = next((o for o in odds_data if (sel.lower() in o['selection'].lower() or o['selection'].lower() in sel.lower()) and o['market_type'].lower() == mtype.lower()), None)
                    
                if not matching_odds:
                    print(f"[DEBUG] Selection '{sel}' could not be matched to live odds.")
                    continue
                    
                validated_rec = {
                    "match_id": match.match_id,
                    "selection": matching_odds["selection"],
                    "market_type": matching_odds["market_type"],
                    "base_odds": matching_odds["dk_odds"],
                    "true_odds": rec.get("true_odds"),
                    "rationale": rec.get("rationale"),
                    "conviction": rec.get("conviction", "Medium"),
                    "research_summary": rec.get("research_summary", []),
                    "raw_research": raw_research_display,
                    "is_taxed": False
                }
                
                live_odds = matching_odds["dk_odds"]
                true_odds = validated_rec["true_odds"]
                if true_odds is not None:
                    validated_rec["is_taxed"] = live_odds < true_odds
                
                print(f"[DEBUG] Successfully validated AI pick: {validated_rec['selection']} at {validated_rec['base_odds']}")
                valid_picks.append(validated_rec)
                
        return {
            "recommendations": valid_picks,
            "injuries": data.get("injuries", {
                "home_team_absences": [],
                "away_team_absences": []
            }),
            "key_battle": data.get("key_battle", "")
        }
    except Exception as e:
        print(f"[DEBUG] Exception in evaluate_tactical_matchups_ai: {e}")
        st.error(f"Error during AI evaluation for match {match.match_id}: {e}")
        return None

def get_final_scores(api_key: str = "") -> Dict[str, str]:
    """
    Scrapes Wikipedia for final scores of completed matches and maps them to database match_ids.
    Returns a dictionary mapping match_id to a score string (e.g., "1-2").
    """
    try:
        # Fetch completed matches from Wikipedia
        wiki_matches = get_wikipedia_matches()
        if not wiki_matches:
            return {}
            
        completed_wiki_matches = []
        import re
        for m in wiki_matches:
            # Check if score matches a digit-hyphen-digit pattern
            if re.match(r'^\d+-\d+$', m["score"]):
                completed_wiki_matches.append(m)
                
        if not completed_wiki_matches:
            return {}
            
        # Fetch all matches from Supabase to map them
        matches_resp = supabase.table("matches").select("match_id", "home_team", "away_team").execute()
        db_matches = matches_resp.data
        
        final_scores = {}
        for m in completed_wiki_matches:
            home = m["home_team"].lower()
            away = m["away_team"].lower()
            # Find matching db match (fuzzy lookup in home/away teams)
            db_match = next((dbm for dbm in db_matches if home in dbm["home_team"].lower() and away in dbm["away_team"].lower()), None)
            if db_match:
                final_scores[db_match["match_id"]] = m["score"]
                
        return final_scores
    except Exception as e:
        print(f"[DEBUG] Error getting final scores: {e}")
        return {}

def determine_settlement_status(slip: LedgerEntry, match: Match, final_score_str: str) -> LedgerStatus:
    """
    Determines the outcome of a bet based on the final score.
    """
    try:
        if slip.market_type == "SGP":
            try:
                import json
                parlay_data = json.loads(slip.selection)
                legs = parlay_data.get("legs", [])
                
                leg_statuses = []
                for leg in legs:
                    leg_slip = LedgerEntry(
                        slip_id=f"leg-{leg.get('market_type')}",
                        match_id=slip.match_id,
                        market_type=leg.get("market_type", ""),
                        selection=leg.get("selection", ""),
                        base_odds=leg.get("base_odds", 100),
                        unit_risk=slip.unit_risk,
                        status=LedgerStatus.PENDING
                    )
                    status = determine_settlement_status(leg_slip, match, final_score_str)
                    if status == LedgerStatus.PENDING:
                        return LedgerStatus.PENDING
                    leg_statuses.append(status)
                    
                if LedgerStatus.LOST in leg_statuses:
                    return LedgerStatus.LOST
                if all(s == LedgerStatus.VOID for s in leg_statuses):
                    return LedgerStatus.VOID
                return LedgerStatus.WON
            except Exception as pe:
                print(f"[DEBUG] Error settling SGP: {pe}")
                return LedgerStatus.PENDING

        home_score_str, away_score_str = final_score_str.split('-')
        home_score = int(home_score_str)
        away_score = int(away_score_str)

        if slip.market_type == "Moneyline":
            # Check if selection is a spread-like line (e.g. "Sweden +0.5" or "Germany -0.5")
            import re
            match_spr = re.search(r"^(.*?)\s+([+-]\d+(?:\.\d+)?)$", slip.selection.strip())
            if match_spr:
                team_name = match_spr.group(1).strip()
                spread_val = float(match_spr.group(2))
                
                is_home = (team_name.lower() in match.home_team.lower()) or (match.home_team.lower() in team_name.lower())
                is_away = (team_name.lower() in match.away_team.lower()) or (match.away_team.lower() in team_name.lower())
                
                if is_home:
                    diff = (home_score + spread_val) - away_score
                    if diff > 0: return LedgerStatus.WON
                    elif diff < 0: return LedgerStatus.LOST
                    else: return LedgerStatus.VOID
                elif is_away:
                    diff = (away_score + spread_val) - home_score
                    if diff > 0: return LedgerStatus.WON
                    elif diff < 0: return LedgerStatus.LOST
                    else: return LedgerStatus.VOID
            else:
                # Standard Moneyline (Home Team, Away Team, or Draw)
                if home_score > away_score:
                    winner = match.home_team
                elif away_score > home_score:
                    winner = match.away_team
                else:
                    winner = "Draw"
                
                # Check for exact or fuzzy match
                is_win = (slip.selection.lower() == winner.lower()) or \
                         (winner.lower() != "draw" and (slip.selection.lower() in winner.lower() or winner.lower() in slip.selection.lower()))
                return LedgerStatus.WON if is_win else LedgerStatus.LOST

        elif slip.market_type == "BTTS": # Both Teams To Score
            is_btts = home_score > 0 and away_score > 0
            if slip.selection == "Yes":
                return LedgerStatus.WON if is_btts else LedgerStatus.LOST
            elif slip.selection == "No":
                return LedgerStatus.WON if not is_btts else LedgerStatus.LOST

        elif slip.market_type == "Spread":
            import re
            match_spr = re.search(r"^(.*?)\s+([+-]\d+(?:\.\d+)?)$", slip.selection.strip())
            if match_spr:
                team_name = match_spr.group(1).strip()
                spread_val = float(match_spr.group(2))
                
                is_home = (team_name.lower() in match.home_team.lower()) or (match.home_team.lower() in team_name.lower())
                is_away = (team_name.lower() in match.away_team.lower()) or (match.away_team.lower() in team_name.lower())
                
                if is_home:
                    diff = (home_score + spread_val) - away_score
                    if diff > 0: return LedgerStatus.WON
                    elif diff < 0: return LedgerStatus.LOST
                    else: return LedgerStatus.VOID
                elif is_away:
                    diff = (away_score + spread_val) - home_score
                    if diff > 0: return LedgerStatus.WON
                    elif diff < 0: return LedgerStatus.LOST
                    else: return LedgerStatus.VOID

        elif slip.market_type == "Total Goals":
            import re
            match_tg = re.search(r"^(Over|Under)\s+(\d+(?:\.\d+)?)$", slip.selection.strip(), re.IGNORECASE)
            if match_tg:
                direction = match_tg.group(1).lower()
                threshold = float(match_tg.group(2))
                total_goals = home_score + away_score
                
                if direction == "over":
                    if total_goals > threshold: return LedgerStatus.WON
                    elif total_goals < threshold: return LedgerStatus.LOST
                    else: return LedgerStatus.VOID
                elif direction == "under":
                    if total_goals < threshold: return LedgerStatus.WON
                    elif total_goals > threshold: return LedgerStatus.LOST
                    else: return LedgerStatus.VOID

    except (ValueError, IndexError):
        # If score is malformed, cannot determine status
        return LedgerStatus.PENDING

    return LedgerStatus.PENDING # Default to pending if no logic matches


def audit_pending_ledger(api_key: str) -> None:
    """
    Audits historical 'Pending' records against final scores and settles them.
    """
    st.write("`[Ledger]` Auditing pending slips...")
    try:
        final_scores = get_final_scores(api_key)
        if not final_scores:
            st.info("No final scores found to audit against.")
            return

        pending_slips_resp = supabase.table("ledger").select("*, matches(*)").eq("status", LedgerStatus.PENDING).execute()
        pending_slips = pending_slips_resp.data

        if not pending_slips:
            st.info("No pending ledger entries to audit.")
            return

        settled_count = 0
        for slip_data in pending_slips:
            slip = LedgerEntry.model_validate(slip_data)
            match_data = slip_data.get('matches')
            
            if not match_data or slip.match_id not in final_scores:
                continue # Skip if match data is missing or match is not yet final

            match = Match.model_validate(match_data)
            final_score = final_scores[slip.match_id]
            final_status = determine_settlement_status(slip, match, final_score)

            if final_status in [LedgerStatus.WON, LedgerStatus.LOST, LedgerStatus.VOID]:
                net_return = 0.0
                if final_status == LedgerStatus.WON:
                    if slip.market_type == "SGP":
                        try:
                            import json
                            parlay_data = json.loads(slip.selection)
                            legs = parlay_data.get("legs", [])
                            
                            total_multiplier = 1.0
                            for leg in legs:
                                leg_slip = LedgerEntry(
                                    slip_id=f"leg-{leg.get('market_type')}",
                                    match_id=slip.match_id,
                                    market_type=leg.get("market_type", ""),
                                    selection=leg.get("selection", ""),
                                    base_odds=leg.get("base_odds", 100),
                                    unit_risk=slip.unit_risk,
                                    status=LedgerStatus.PENDING
                                )
                                status = determine_settlement_status(leg_slip, match, final_score)
                                if status == LedgerStatus.WON:
                                    odds = leg.get("base_odds", 100)
                                    if odds > 0:
                                        mult = (odds / 100.0) + 1.0
                                    else:
                                        mult = (100.0 / abs(odds)) + 1.0
                                    total_multiplier *= mult
                                
                            net_return = slip.unit_risk * (total_multiplier - 1.0)
                        except Exception as calc_err:
                            print(f"[DEBUG] Error calculating SGP winnings: {calc_err}")
                            if slip.base_odds > 0: net_return = slip.unit_risk * (slip.base_odds / 100.0)
                            else: net_return = slip.unit_risk * (100.0 / abs(slip.base_odds))
                    else:
                        if slip.base_odds > 0: net_return = slip.unit_risk * (slip.base_odds / 100.0)
                        else: net_return = slip.unit_risk * (100.0 / abs(slip.base_odds))
                elif final_status == LedgerStatus.LOST:
                    net_return = -slip.unit_risk
                elif final_status == LedgerStatus.VOID:
                    net_return = 0.0

                supabase.table("ledger").update({
                    "status": final_status.value,
                    "net_return": round(net_return, 2)
                }).eq("slip_id", slip.slip_id).execute()
                settled_count += 1

        if settled_count > 0:
            st.success(f"Audited and settled {settled_count} pending slip(s).")
        else:
            st.info("Audit complete. No new results to settle.")

    except Exception as e:
        st.error(f"Error during ledger audit: {e}")


def execute_sync_pipeline():
    """
    Main on-demand execution chain.
    """
    with st.status("Executing sync pipeline...", expanded=True) as status:
        try:
            api_key = st.session_state.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
            
            # Step 0: Audit ledger first (as per rules)
            status.update(label="Auditing pending ledger entries...")
            audit_pending_ledger(api_key)

            # Step 1: Scrape active lineups and update the database
            status.update(label="Discovering matches and odds...")
            target_date = st.session_state.get("sync_date", date(2026, 6, 19))
            odds_api_key = st.session_state.get("odds_api_key") or os.environ.get("ODDS_API_KEY", "")
            scrape_and_update_match_data(api_key, target_date, odds_api_key)

            # Step 2: Fetch all matches from DB
            status.update(label="Fetching matches from database...")
            matches_response = supabase.table("matches").select("*").execute()
            all_matches = [Match.model_validate(m) for m in matches_response.data]
            all_matches.sort(key=lambda m: m.kickoff_time)

            st.session_state.all_matches = all_matches
            
            # Reset conviction picks so user can run fresh research on newly synced matches
            st.session_state.conviction_picks = {}

            status.update(label="Sync complete. Ready to render UI.", state="complete")
        except Exception as e:
            status.update(label=f"Pipeline failed: {e}", state="error")


# --- 5. USER INTERFACE (Mobile-First Streamlit Components) ---


def render_dashboard_tab():
    """Renders the bet tracking performance dashboard section."""
    try:
        # Fetch all settled + pending ledger entries
        ledger_resp = supabase.table("ledger").select("*").order("created_at", desc=False).execute()
        all_entries = ledger_resp.data
    except Exception as e:
        st.error(f"Could not load ledger data: {e}")
        return

    if not all_entries:
        st.info("📭 No bets tracked yet. Log your first pick from a conviction card below!")
        return

    # --- Compute aggregate stats ---
    total = len(all_entries)
    won    = sum(1 for e in all_entries if e["status"] == "Won")
    lost   = sum(1 for e in all_entries if e["status"] == "Lost")
    void   = sum(1 for e in all_entries if e["status"] == "Void")
    pending = sum(1 for e in all_entries if e["status"] == "Pending")
    settled = won + lost
    win_rate = (won / settled * 100) if settled > 0 else 0.0
    net_returns = [e["net_return"] for e in all_entries if e["net_return"] is not None]
    net_pl = sum(net_returns)

    # Current streak (scan from most recent settled)
    streak = 0
    streak_label = "—"
    settled_entries = [e for e in reversed(all_entries) if e["status"] in ("Won", "Lost")]
    if settled_entries:
        streak_status = settled_entries[0]["status"]
        for e in settled_entries:
            if e["status"] == streak_status:
                streak += 1
            else:
                break
        streak_label = f"{'🔥' if streak_status == 'Won' else '❄️'} {streak}{'W' if streak_status == 'Won' else 'L'}"

    # --- Stat Cards Row ---
    col1, col2, col3, col4 = st.columns(4)
    def _card(col, value, label, delta=None, delta_pos=True):
        delta_class = "stat-delta-pos" if delta_pos else "stat-delta-neg"
        delta_html = f'<div class="{delta_class}">{delta}</div>' if delta else ""
        col.markdown(f"""
<div class="stat-card">
  <div class="stat-value">{value}</div>
  <div class="stat-label">{label}</div>
  {delta_html}
</div>""", unsafe_allow_html=True)

    _card(col1, total, "Total Bets", f"{pending} Pending", delta_pos=True)
    _card(col2, f"{won}W / {lost}L", "Record", f"{win_rate:.1f}% Win Rate", delta_pos=(win_rate >= 50))
    pl_delta_str = f"{net_pl:+.2f}u"
    _card(col3, f"{net_pl:+.2f}u", "Net P&L", pl_delta_str, delta_pos=(net_pl >= 0))
    _card(col4, streak_label, "Current Streak")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Cumulative P&L Chart ---
    settled_with_returns = [(e["created_at"], e["net_return"]) for e in all_entries if e["net_return"] is not None]
    if settled_with_returns:
        import pandas as pd
        df_pl = pd.DataFrame(settled_with_returns, columns=["Date", "Return"])
        df_pl["Date"] = pd.to_datetime(df_pl["Date"]).dt.strftime("%m/%d %H:%M")
        df_pl["Cumulative P&L (units)"] = df_pl["Return"].cumsum()
        df_pl = df_pl.set_index("Date")

        st.markdown("**📈 Cumulative P&L Over Time**")
        st.line_chart(df_pl[["Cumulative P&L (units)"]], use_container_width=True, height=200)

    # --- Market Breakdown ---
    settled_data = [e for e in all_entries if e["status"] in ("Won", "Lost")]
    if settled_data:
        import pandas as pd
        from collections import defaultdict
        market_stats = defaultdict(lambda: {"won": 0, "total": 0})
        for e in settled_data:
            mtype = e.get("market_type", "Unknown")
            market_stats[mtype]["total"] += 1
            if e["status"] == "Won":
                market_stats[mtype]["won"] += 1

        market_rows = []
        for mtype, s in market_stats.items():
            wr = (s["won"] / s["total"] * 100) if s["total"] > 0 else 0
            market_rows.append({"Market": mtype, "Win Rate %": round(wr, 1), "Bets": s["total"]})

        df_mkt = pd.DataFrame(market_rows).set_index("Market")

        col_chart, col_tbl = st.columns([2, 1])
        with col_chart:
            st.markdown("**🎯 Win Rate by Market Type**")
            st.bar_chart(df_mkt[["Win Rate %"]], use_container_width=True, height=180)
        with col_tbl:
            st.markdown("**Breakdown**")
            for _, row in df_mkt.reset_index().iterrows():
                wr_color = "green" if row["Win Rate %"] >= 50 else "red"
                st.markdown(f":{wr_color}[**{row['Market']}**] — {row['Win Rate %']}% ({row['Bets']} bets)")

    # --- Recent Bets Table ---
    st.markdown("<br>**📋 Recent Settled Bets**", unsafe_allow_html=True)
    recent = sorted(
        [e for e in all_entries if e["status"] in ("Won", "Lost")],
        key=lambda x: x.get("created_at", ""),
        reverse=True
    )[:8]

    if not recent:
        st.caption("No settled bets yet.")
    else:
        for e in recent:
            color = "green" if e["status"] == "Won" else "red"
            ret_str = f"{e['net_return']:+.2f}u" if e["net_return"] is not None else "N/A"
            mtype = e.get("market_type", "")
            sel = e.get("selection", "")
            if mtype == "SGP":
                try:
                    sgp_data = json.loads(sel)
                    sel = sgp_data.get("display_name", sel)
                except Exception:
                    pass
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.markdown(f"**{sel}** `{mtype}`")
                c2.markdown(f":{color}[**{e['status']}**]")
                c3.markdown(f"**{ret_str}**")


def render_main_dashboard():
    """Renders the main application dashboard after successful authentication."""
    st.title("WC Data Dashboard")

    # Load matches from DB on startup if not already in session state
    if 'all_matches' not in st.session_state:
        try:
            matches_response = supabase.table("matches").select("*").execute()
            all_matches = [Match.model_validate(m) for m in matches_response.data]
            all_matches.sort(key=lambda m: m.kickoff_time)
            st.session_state.all_matches = all_matches
        except Exception:
            st.session_state.all_matches = []

    # --- Sidebar Configuration ---
    with st.sidebar:
        st.header("Pipeline Configuration")
        gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        odds_api_key_env = os.environ.get("ODDS_API_KEY", "")
        
        st.markdown("---")
        st.subheader("Gemini API Setup")
        st.info("Requires a Gemini API Key to run web search queries and LLM tactical evaluation.")
        api_key_input = st.text_input(
            "Gemini API Key",
            value=st.session_state.get("gemini_api_key", gemini_api_key),
            type="password",
            placeholder="AIzaSy..."
        )
        if api_key_input:
            st.session_state.gemini_api_key = api_key_input

        st.markdown("---")
        st.subheader("Odds API Setup")
        st.info("Optional: Enter your key from the-odds-api.com to pull real-time DraftKings lines automatically.")
        odds_key_input = st.text_input(
            "Odds API Key",
            value=st.session_state.get("odds_api_key", odds_api_key_env),
            type="password",
            placeholder="e.g. 7c3aed..."
        )
        if odds_key_input:
            st.session_state.odds_api_key = odds_key_input

        st.markdown("---")
        st.subheader("Match Date Filter")
        default_date = date.today()
        target_date = st.date_input(
            "View / Sync Date",
            value=default_date,
            key="sync_date",
            help="Select the date of World Cup matches you want to view or sync."
        )


    # --- Main Sync Trigger ---
    st.button(
        "Manual Sync Pipeline",
        on_click=execute_sync_pipeline,
        type="primary",
        use_container_width=True,
    )
    st.caption("On-demand trigger: Scrapes lineups, fetches lines, evaluates matchups, and audits ledger.")

    st.divider()

    # --- Performance Dashboard ---
    with st.expander("📊 Bet Tracking Dashboard", expanded=False):
        render_dashboard_tab()

    st.divider()

    # --- Match List & Research Section ---
    st.subheader("Upcoming Matches & Research")
    
    if 'all_matches' not in st.session_state:
        st.info("No matches synced yet. Press the sync button to begin.")
    elif not st.session_state.all_matches:
        st.warning("No matches found in the database. Run the sync pipeline to discover games.")
    else:
        if 'conviction_picks' not in st.session_state:
            st.session_state.conviction_picks = {}
            
        selected_date_str = target_date.strftime("%Y-%m-%d")
        day_matches = [m for m in st.session_state.all_matches if m.kickoff_time.strftime("%Y-%m-%d") == selected_date_str]
        
        if not day_matches:
            st.warning(f"No matches found in the database for {target_date.strftime('%A, %b %d, %Y')}. Run the sync pipeline to discover games for this date.")
        else:
            # Batch ledger fetch once — filter client-side per match to avoid N DB queries
            try:
                _all_ledger = supabase.table("ledger").select("match_id,selection,market_type").execute().data
            except Exception:
                _all_ledger = []
            _ledger_by_match: Dict[str, set] = {}
            for _item in _all_ledger:
                _ledger_by_match.setdefault(_item["match_id"], set()).add(
                    (_item["selection"].lower(), _item["market_type"].lower())
                )

            for match in day_matches:
                match_id = match.match_id
                
                # Retrieve active API Key
                api_key = st.session_state.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
                
                # Wrap each match card in a clean container
                with st.container(border=True):
                    st.markdown(f"⚽ **{match.home_team} vs {match.away_team}**")
                    st.caption(f"Kickoff: {match.kickoff_time.strftime('%Y-%m-%d %H:%M UTC')} | Status: {match.lineup_status}")
                    
                    # Collapsible Sandbox editor for tactical lineups and odds
                    with st.expander("🛠️ Match Sandbox (Roster & Odds Editor)", expanded=False):
                        col_status, col_gen = st.columns([1, 1])
                        with col_status:
                            new_status = st.selectbox(
                                "Lineup Status",
                                options=[LineupStatus.PROJECTED, LineupStatus.CONFIRMED],
                                index=0 if match.lineup_status == LineupStatus.PROJECTED else 1,
                                key=f"status_sel_{match_id}"
                            )
                        with col_gen:
                            st.write("") # vertical offset
                            if st.button("🪄 Auto-Generate Lineup via AI", key=f"gen_lineup_{match_id}", use_container_width=True):
                                if not api_key:
                                    st.error("Please enter your Gemini API Key in the sidebar.")
                                else:
                                    with st.spinner("Generating starting XI..."):
                                        gen_res = generate_projected_lineups(match.home_team, match.away_team, api_key)
                                        if gen_res:
                                            match.home_lineup = gen_res["home_lineup"]
                                            match.away_lineup = gen_res["away_lineup"]
                                            match.lineup_status = new_status
                                            supabase.table("matches").update({
                                                "home_lineup": match.home_lineup,
                                                "away_lineup": match.away_lineup,
                                                "lineup_status": match.lineup_status
                                            }).eq("match_id", match_id).execute()
                                            st.toast("Projected rosters successfully generated!")
                                            st.rerun()
                                        else:
                                            st.error("Failed to generate projected lineup.")
                                            
                        home_txt = st.text_area(
                            f"{match.home_team} Lineup (comma-separated)",
                            value=", ".join(match.home_lineup),
                            key=f"home_lineup_txt_{match_id}"
                        )
                        away_txt = st.text_area(
                            f"{match.away_team} Lineup (comma-separated)",
                            value=", ".join(match.away_lineup),
                            key=f"away_lineup_txt_{match_id}"
                        )
                        
                        st.markdown("---")
                        st.subheader("📈 Odds Sandbox Override")
                        
                        # Retrieve odds for this match from the database
                        try:
                            odds_resp = supabase.table("odds").select("id, market_type, selection, dk_odds").eq("match_id", match_id).execute()
                            match_odds = odds_resp.data
                        except Exception:
                            match_odds = []
                            
                        updated_odds_dict = {}
                        if not match_odds:
                            st.caption("No odds found in the database. Run the sync pipeline first.")
                        else:
                            # Group/sort odds by market type
                            match_odds.sort(key=lambda o: (o["market_type"], o["selection"]))
                            
                            # Render in 2 columns
                            odds_cols = st.columns(2)
                            for idx, odd in enumerate(match_odds):
                                col = odds_cols[idx % 2]
                                odd_id = odd["id"]
                                mtype = odd["market_type"]
                                selection = odd["selection"]
                                current_val = odd["dk_odds"]
                                
                                with col:
                                    label = f"{mtype}: {selection}"
                                    new_val = st.number_input(
                                        label,
                                        value=int(current_val),
                                        step=5,
                                        key=f"odd_input_{match_id}_{odd_id}"
                                    )
                                    updated_odds_dict[odd_id] = new_val
                                    
                        st.markdown("---")
                        col_save, col_rerun = st.columns([1, 1])
                        with col_save:
                            if st.button("💾 Save Sandbox Settings", key=f"save_lineup_{match_id}", use_container_width=True):
                                # Save lineups
                                match.home_lineup = [p.strip() for p in home_txt.split(",") if p.strip()]
                                match.away_lineup = [p.strip() for p in away_txt.split(",") if p.strip()]
                                match.lineup_status = new_status
                                supabase.table("matches").update({
                                    "home_lineup": match.home_lineup,
                                    "away_lineup": match.away_lineup,
                                    "lineup_status": match.lineup_status
                                }).eq("match_id", match_id).execute()
                                
                                # Save custom odds overrides
                                for oid, val in updated_odds_dict.items():
                                    supabase.table("odds").update({
                                        "dk_odds": val
                                    }).eq("id", oid).execute()
                                    
                                st.toast("Sandbox settings saved successfully!")
                                st.rerun()
                        with col_rerun:
                            # Render Rerun option only if picks already exist
                            if match_id in st.session_state.conviction_picks:
                                if st.button("🔄 Rerun Tactical Research", key=f"rerun_res_{match_id}", use_container_width=True):
                                    if not api_key:
                                        st.error("Please enter your Gemini API Key in the sidebar.")
                                    else:
                                        # Save lineups
                                        match.home_lineup = [p.strip() for p in home_txt.split(",") if p.strip()]
                                        match.away_lineup = [p.strip() for p in away_txt.split(",") if p.strip()]
                                        match.lineup_status = new_status
                                        supabase.table("matches").update({
                                            "home_lineup": match.home_lineup,
                                            "away_lineup": match.away_lineup,
                                            "lineup_status": match.lineup_status
                                        }).eq("match_id", match_id).execute()
                                        
                                        # Save custom odds overrides
                                        for oid, val in updated_odds_dict.items():
                                            supabase.table("odds").update({
                                                "dk_odds": val
                                            }).eq("id", oid).execute()
                                            
                                        with st.spinner(f"Re-evaluating {match.home_team} vs {match.away_team}..."):
                                            pick = evaluate_tactical_matchups_ai(match, api_key)
                                            st.session_state.conviction_picks[match_id] = pick
                                            st.rerun()

                    # Render Research Results / Action Section
                    if match_id in st.session_state.conviction_picks:
                        res_data = st.session_state.conviction_picks[match_id]
                        
                        # Handle None or old session state formats gracefully to avoid crashes
                        if res_data is None:
                            picks = []
                            injuries = {}
                            key_battle = ""
                        elif isinstance(res_data, list):
                            picks = res_data
                            injuries = {}
                            key_battle = ""
                        else:
                            picks = res_data.get("recommendations", []) or []
                            injuries = res_data.get("injuries", {}) or {}
                            key_battle = res_data.get("key_battle", "") or ""
                            
                        # Filter out already-logged picks using the batched ledger dict
                        logged_selections = _ledger_by_match.get(match_id, set())
                        picks = [p for p in picks if (p["selection"].lower(), p["market_type"].lower()) not in logged_selections]
                            
                        # Render Match-wide Injury & Tactical Report expander first!
                        if injuries.get("home_team_absences") or injuries.get("away_team_absences") or key_battle:
                            with st.expander("🚑 Match Day Injury & Tactical Report", expanded=True):
                                if key_battle:
                                    st.markdown(f"**Key Battle:** {key_battle}")
                                    st.divider()
                                    
                                col_h, col_a = st.columns([1, 1])
                                with col_h:
                                    st.markdown(f"🏥 **{match.home_team} Absences**")
                                    home_abs = injuries.get("home_team_absences", [])
                                    if home_abs:
                                        for item in home_abs:
                                            st.markdown(f"- **{item.get('player')}** ({item.get('status')}): *{item.get('reason')}*")
                                    else:
                                        st.caption("No major absences reported.")
                                with col_a:
                                    st.markdown(f"🏥 **{match.away_team} Absences**")
                                    away_abs = injuries.get("away_team_absences", [])
                                    if away_abs:
                                        for item in away_abs:
                                            st.markdown(f"- **{item.get('player')}** ({item.get('status')}): *{item.get('reason')}*")
                                    else:
                                        st.caption("No major absences reported.")
                                        
                        if picks:
                            for pick in picks:
                                render_conviction_card(pick)
                        else:
                            st.info("AI Research complete: No pending value recommendations (all logged/used or none found).")
                    else:
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            st.caption(f"Rosters: {len(match.home_lineup)} home / {len(match.away_lineup)} away")
                        with col2:
                            if st.button("🔍 Run AI Research", key=f"run_res_{match_id}", use_container_width=True):
                                if not api_key:
                                    st.error("Please enter your Gemini API Key in the sidebar.")
                                else:
                                    with st.spinner(f"Evaluating {match.home_team} vs {match.away_team}..."):
                                        pick = evaluate_tactical_matchups_ai(match, api_key)
                                        st.session_state.conviction_picks[match_id] = pick
                                        st.rerun()


    st.divider()

    # --- Ledger Display ---
    st.subheader("Selection Ledger")
    try:
        ledger_response = supabase.table("ledger").select("*").order("created_at", desc=True).limit(20).execute()
        ledger_entries = [LedgerEntry.model_validate(e) for e in ledger_response.data]
        
        if not ledger_entries:
            st.info("Ledger is empty.")
        else:
            for entry in ledger_entries:
                color = "grey"
                if entry.status == LedgerStatus.WON: color = "green"
                elif entry.status == LedgerStatus.LOST: color = "red"
                
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if entry.market_type == "SGP":
                            try:
                                import json
                                parlay_data = json.loads(entry.selection)
                                legs_desc = " + ".join([f"{leg['selection']} ({leg['base_odds']})" for leg in parlay_data.get("legs", [])])
                                st.markdown(f"**SGP:** {legs_desc} ({entry.base_odds})")
                            except Exception:
                                st.markdown(f"**{entry.selection}** ({entry.base_odds})")
                        else:
                            st.markdown(f"**{entry.selection}** ({entry.base_odds})")
                        st.caption(f"Match ID: {entry.match_id}")
                    with col2:
                        st.markdown(f"**:{color}[{entry.status.upper()}]**")
                        ret = f"{entry.net_return:+.2f}" if entry.net_return is not None else "N/A"
                        st.metric("Net", f"{ret}u", delta_color="off")

    except Exception as e:
        st.error(f"Could not load ledger: {e}")


def render_conviction_card(pick: Dict[str, Any]):
    """Renders a single, touch-friendly card for a conviction pick."""
    
    def log_selection(mark_as_used: bool = False):
        """Callback to write the selection to the ledger."""
        try:
            if mark_as_used:
                unit_risk_value = 0.01
                status = LedgerStatus.VOID
                net_return = 0.0
            else:
                unit_risk_key = f"unit_risk_{pick['match_id']}_{pick['selection']}"
                unit_risk_value = st.session_state.get(unit_risk_key, 1.0)
                status = LedgerStatus.PENDING
                net_return = None

            if pick['market_type'] == "SGP":
                import json
                selection_val = json.dumps({
                    "type": "sgp",
                    "display_name": pick['selection'],
                    "legs": pick.get("legs", [])
                })
            else:
                selection_val = pick['selection']

            new_slip = LedgerEntry(
                slip_id=str(uuid.uuid4()),
                match_id=pick['match_id'],
                market_type=pick['market_type'],
                selection=selection_val,
                base_odds=pick['base_odds'],
                unit_risk=unit_risk_value,
                status=status
            )
            data_to_insert = new_slip.model_dump(mode='json', exclude={'created_at'})
            if net_return is not None:
                data_to_insert['net_return'] = net_return
            else:
                data_to_insert.pop('net_return', None)

            supabase.table("ledger").insert(data_to_insert).execute()
            if mark_as_used:
                st.success(f"Marked as Used: {pick['selection']}")
            else:
                st.success(f"Logged: {pick['selection']} @ {pick['base_odds']}")
            # Remove only this specific selection from the conviction picks list in session state
            if pick['match_id'] in st.session_state.conviction_picks:
                res_data = st.session_state.conviction_picks[pick['match_id']]
                if isinstance(res_data, dict):
                    picks_list = res_data.get("recommendations", [])
                    updated_list = [p for p in picks_list if not (p['selection'] == pick['selection'] and p['market_type'] == pick['market_type'])]
                    res_data["recommendations"] = updated_list
                    st.session_state.conviction_picks[pick['match_id']] = res_data
                elif isinstance(res_data, list):
                    updated_list = [p for p in res_data if not (p['selection'] == pick['selection'] and p['market_type'] == pick['market_type'])]
                    if updated_list:
                        st.session_state.conviction_picks[pick['match_id']] = updated_list
                    else:
                        st.session_state.conviction_picks.pop(pick['match_id'], None)
            st.rerun()
        except Exception as e:
            st.error(f"Failed to log slip: {e}")

    with st.expander(f"🎯 {pick['market_type']}: {pick['selection']} ({pick['base_odds']})", expanded=True):
        if pick['market_type'] == "SGP":
            st.markdown("**Parlay Legs:**")
            for leg in pick.get("legs", []):
                st.markdown(f"- **{leg['selection']}** ({leg['base_odds']}) | *{leg['market_type']}*")
            st.divider()

        conviction_raw = pick.get("conviction", "High").lower()
        if conviction_raw == "low":
            advice = "Speculative Sprinkle"
            badge_color = "red"
            base_conf = 25
        elif conviction_raw == "medium":
            advice = "Standard Play"
            badge_color = "orange"
            base_conf = 52
        else:
            advice = "Strong Edge Play"
            badge_color = "green"
            base_conf = 78
            
        # Calculate suggested Kelly Criterion stake size & suggested units (1u = 2% bankroll)
        base_odds = pick.get("base_odds")
        true_odds = pick.get("true_odds")
        kelly_pct = 0.0
        suggested_units = 1.0
        edge_pct = 0.0
        if base_odds is not None and true_odds is not None:
            kelly_pct = calculate_kelly_fraction(base_odds, true_odds)
            if kelly_pct > 0.0:
                suggested_units = round((kelly_pct / 2.0) * 4) / 4.0
                suggested_units = max(0.25, min(suggested_units, 5.0))
                
            # Implied win probabilities to calculate Value Edge
            base_prob = 100.0 / (base_odds + 100.0) if base_odds > 0 else abs(base_odds) / (abs(base_odds) + 100.0)
            true_prob = 100.0 / (true_odds + 100.0) if true_odds > 0 else abs(true_odds) / (abs(true_odds) + 100.0)
            edge_pct = max(0.0, (true_prob - base_prob) * 100.0)
            
        # --- AI Confidence Score Meter ---
        edge_boost = min(edge_pct * 1.2, 22.0)  # edge contributes up to 22 pts
        confidence_score = min(100, max(0, round(base_conf + edge_boost)))
        if confidence_score >= 70:
            meter_color = "linear-gradient(90deg, #4ade80, #22d3ee)"
            meter_label_color = "#4ade80"
        elif confidence_score >= 45:
            meter_color = "linear-gradient(90deg, #fbbf24, #f97316)"
            meter_label_color = "#fbbf24"
        else:
            meter_color = "linear-gradient(90deg, #f87171, #e879f9)"
            meter_label_color = "#f87171"

        st.markdown(f"""
<div class="confidence-meter-wrap">
  <div class="confidence-meter-label">
    <span>🧠 AI Confidence Score</span>
    <span class="score-val" style="color:{meter_label_color}">{confidence_score}%</span>
  </div>
  <div class="confidence-track">
    <div class="confidence-fill" style="width:{confidence_score}%; background:{meter_color};"></div>
  </div>
</div>""", unsafe_allow_html=True)

        col_badge, col_kelly = st.columns([1, 1])
        with col_badge:
            edge_str = f" | Edge: :green[+{edge_pct:.1f}%]" if edge_pct > 0.0 else ""
            st.markdown(f"**Actionable Advice:** :{badge_color}[{advice}]{edge_str}")
        with col_kelly:
            if kelly_pct > 0.0:
                st.markdown(f"**Suggested Stake (Half-Kelly):** :green[{kelly_pct}% ({suggested_units}u)]")
            else:
                st.markdown(f"**Suggested Stake (Half-Kelly):** :grey[N/A (1.00u)]")

        st.markdown("**Rationale:**")
        st.info(pick['rationale'])

        # Display research summary if available
        if "research_summary" in pick:
            with st.expander("📚 Key Research Findings", expanded=True):
                summary = pick["research_summary"]
                if isinstance(summary, list):
                    for bullet in summary:
                        st.markdown(f"- {bullet}")
                else:
                    st.write(summary)

        # Display raw web research if available
        if "raw_research" in pick:
            with st.expander("🔍 Raw Web Research & Context"):
                st.caption("Latest web search snippets analyzed by the AI:")
                st.text(pick["raw_research"])

        # Dynamic "Market Taxation" button warning
        button_text = "Log Selection"
        if pick['is_taxed']:
            button_text = "Log Selection ⚠️ Market Tax Added"

        col1, col2 = st.columns([1, 1])
        with col1:
            st.number_input(
                "Unit Risk", 
                min_value=0.01, 
                max_value=10.0, 
                value=suggested_units, 
                step=0.25, 
                key=f"unit_risk_{pick['match_id']}_{pick['selection']}",
                format="%.2f"
            )
        with col2:
            st.button(
                button_text,
                on_click=log_selection,
                args=(False,),
                use_container_width=True,
                key=f"log_{pick['match_id']}_{pick['selection']}"
            )
        if pick.get('market_type') == "Promo/Boost" or pick.get('market_type') == "SGP":
            st.button(
                "Mark as Used / Dismiss",
                on_click=log_selection,
                args=(True,),
                use_container_width=True,
                key=f"used_{pick['match_id']}_{pick['selection']}"
            )


# --- 6. MAIN APPLICATION FLOW ---

render_main_dashboard()

