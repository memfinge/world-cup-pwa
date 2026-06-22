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
# # Inject Custom Glassmorphic Dark-Mode Stylesheet at script startup to keep it persistent
CUSTOM_CSS = """
<style>
/* Refined Dark-Mode Sports Theme - Much Darker Vibe */
.stApp {
    background: linear-gradient(135deg, #020307, #060b14, #010204) !important;
    color: #cbd5e1 !important;
}

/* Glassmorphic Details Expander */
div[data-testid="stExpander"] {
    background: rgba(6, 10, 20, 0.82) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-radius: 12px !important;
    box-shadow: 0 8px 36px 0 rgba(0, 0, 0, 0.5) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    margin-bottom: 12px !important;
}

/* Outer Matchup Container: Remove wrapper border, apply pronounced borders to inner block */
div[data-testid="stVerticalBlockBorderWrapper"],
div.stVerticalBlockBorderWrapper {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    margin-bottom: 32px !important; /* Breathing room between match scorecards */
}
div[data-testid="stVerticalBlockBorderWrapper"] > div,
div.stVerticalBlockBorderWrapper > div,
div[data-testid="column"] > div > div > div,
div[data-testid="column"] > div > div > div > div {
    background: rgba(8, 12, 24, 0.92) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border: 3.5px solid rgba(255, 255, 255, 0.28) !important; /* Extremely pronounced slate/white border */
    border-left: 8px solid #7c3aed !important; /* Extra thick brand purple accent strip */
    border-radius: 12px !important;
    box-shadow: 0 12px 42px 0 rgba(0, 0, 0, 0.75) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    padding: 16px !important;
}

/* Hover effect with soft premium glow */
div[data-testid="stExpander"]:hover,
div[data-testid="stVerticalBlockBorderWrapper"] > div:hover,
div.stVerticalBlockBorderWrapper > div:hover,
div[data-testid="column"] > div > div > div:hover,
div[data-testid="column"] > div > div > div > div:hover {
    border-color: rgba(0, 242, 254, 0.65) !important;
    box-shadow: 0 12px 40px 0 rgba(0, 242, 254, 0.12) !important;
    transform: translateY(-2px) !important;
}

/* Typography Custom Fonts and Tri-Color Brand Gradient */
h1, h2, h3 {
    color: #ffffff !important;
    font-family: 'Outfit', 'Inter', sans-serif !important;
    font-weight: 700 !important;
}

h1 {
    background: linear-gradient(to right, #00f2fe, #a855f7, #facc15) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    padding-bottom: 0.2em !important;
    font-size: 2.25rem !important;
}

/* Premium Buttons (Deep Blue to Purple Gradient) */
button {
    background: linear-gradient(90deg, #111827, #3730a3) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    padding: 0.5rem 1.0rem !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 12px 0 rgba(0, 0, 0, 0.4) !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

button:hover {
    background: linear-gradient(90deg, #1f2937, #4338ca) !important;
    border-color: rgba(0, 242, 254, 0.3) !important;
    box-shadow: 0 6px 18px 0 rgba(0, 242, 254, 0.1) !important;
    transform: translateY(-1px) !important;
}

/* Form Controls & Inputs Styling */
input, select, textarea {
    background-color: rgba(4, 6, 12, 0.85) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}

/* Metric Display Values (Bright Turquoise) */
div[data-testid="stMetricValue"] {
    font-weight: 800 !important;
    color: #00f2fe !important;
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
    background: rgba(0,0,0,0.3);
    border-radius: 99px;
    overflow: hidden;
    box-shadow: inset 0 1px 4px rgba(0,0,0,0.6);
}
.confidence-fill {
    height: 100%;
    border-radius: 99px;
    transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Dashboard stat cards */
.stat-card {
    background: rgba(6, 10, 20, 0.82);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 14px;
    padding: 1rem 1.25rem;
    text-align: center;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.stat-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 30px rgba(0,242,254,0.08);
}
.stat-card .stat-value {
    font-size: 1.8rem;
    font-weight: 800;
    color: #00f2fe;
    font-family: 'Outfit', 'Inter', sans-serif;
}
.stat-card .stat-label {
    font-size: 0.72rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 2px;
}
.stat-card .stat-delta-pos { color: #00ff87; font-size: 0.85rem; font-weight: 600; }
.stat-card .stat-delta-neg { color: #ff5e62; font-size: 0.85rem; font-weight: 600; }
.stat-card .stat-delta-neu { color: #94a3b8; font-size: 0.85rem; font-weight: 600; }

/* Scoreboard Header */
.scoreboard {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    margin-bottom: 14px;
}
.scoreboard-team {
    flex: 1 1 0%;
    width: 0;
    font-size: 1.25rem;
    font-weight: 700;
    font-family: 'Outfit', 'Inter', sans-serif;
    color: #ffffff !important;
    border-radius: 6px;
    height: 48px;
    display: flex;
    align-items: center;
    background-size: cover !important;
    background-position: center !important;
    background-repeat: no-repeat !important;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.9), 0 0 2px rgba(0, 0, 0, 0.7);
}
.scoreboard-team.home {
    justify-content: flex-end;
    text-align: right;
    padding-right: 18px;
}
.scoreboard-team.away {
    justify-content: flex-start;
    text-align: left;
    padding-left: 18px;
}
.scoreboard-vs {
    font-size: 0.75rem;
    font-weight: 900;
    background: linear-gradient(135deg, #00f2fe, #7c3aed);
    color: #030712;
    padding: 3px 10px;
    border-radius: 20px;
    box-shadow: 0 0 12px rgba(0, 242, 254, 0.25);
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

/* Custom Badges */
.badge {
    display: inline-block;
    padding: 3px 8px;
    font-size: 0.7rem;
    font-weight: 700;
    border-radius: 6px;
    letter-spacing: 0.02em;
}
.badge-confirmed {
    background: rgba(0, 255, 135, 0.05) !important;
    color: #00ff87 !important;
    border: 1px solid rgba(0, 255, 135, 0.1) !important;
}
.badge-projected {
    background: rgba(124, 58, 237, 0.05) !important;
    color: #a78bfa !important;
    border: 1px solid rgba(124, 58, 237, 0.1) !important;
}
.badge-none {
    background: rgba(100, 116, 139, 0.05) !important;
    color: #94a3b8 !important;
    border: 1px solid rgba(100, 116, 139, 0.1) !important;
}
.badge-research-done {
    background: rgba(0, 242, 254, 0.05) !important;
    color: #00f2fe !important;
    border: 1px solid rgba(0, 242, 254, 0.1) !important;
}
.badge-research-pending {
    background: rgba(245, 158, 11, 0.05) !important;
    color: #f59e0b !important;
    border: 1px solid rgba(245, 158, 11, 0.1) !important;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

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
    
    # Prioritize 2.5 flash / 2.0 flash models for speed and higher quotas,
    # then fallback to 1.5 flash, 1.5 pro, and others.
    preferred_models = [
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-1.5-flash',
        'gemini-1.5-flash-8b',
        'gemini-2.5-pro',
        'gemini-1.5-pro',
        'gemini-2.0-flash-exp'
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


def scrape_confirmed_lineup(home_team: str, away_team: str) -> Optional[Dict[str, Any]]:
    """
    Searches the web for an officially announced starting XI for today's match.
    Returns {'home_lineup': [...], 'away_lineup': [...], 'confirmed': True} if a real
    lineup is found (>= 8 recognisable names per side), or None otherwise.
    """
    import re
    queries = [
        f"{home_team} vs {away_team} confirmed starting lineup XI today 2026 World Cup",
        f"{home_team} {away_team} starting 11 lineup announced official",
    ]

    raw_text = ""
    for query in queries:
        try:
            from duckduckgo_search import DDGS
            with DDGS(timeout=3) as ddgs:
                results = list(ddgs.text(query, max_results=5))
                for r in results:
                    raw_text += f" {r.get('title', '')} {r.get('body', '')}"
            if len(raw_text.strip()) > 200:
                break
        except Exception:
            pass

    if len(raw_text.strip()) < 100:
        try:
            import urllib.parse
            url = f"https://news.search.yahoo.com/search?p={urllib.parse.quote(queries[0])}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for item in soup.find_all("div", class_="NewsArticle")[:5]:
                    title = (item.find("h4") or item.find("a") or "")
                    snippet = (item.find("p") or item.find(class_="compText") or "")
                    raw_text += f" {title.get_text() if hasattr(title,'get_text') else ''} {snippet.get_text() if hasattr(snippet,'get_text') else ''}"
        except Exception:
            pass

    # Keyword check — only proceed if page actually discusses a confirmed lineup
    confirmed_keywords = [
        "starting xi", "starting lineup", "confirmed lineup", "line-up",
        "starting eleven", "named lineup", "official lineup", "announced lineup"
    ]
    text_lower = raw_text.lower()
    if not any(kw in text_lower for kw in confirmed_keywords):
        return None  # No confirmed lineup language found

    # Extract plausible player name tokens: "Firstname Lastname" capitalised pairs,
    # or single-word names like "Musiala", "Ronaldo", "Mbappe"
    name_pattern = re.compile(r'\b([A-Z][a-záéíóúãçñüàèìòùâêîôûäëïöü]+(?:\s+[A-Z][a-záéíóúãçñüàèìòùâêîôûäëïöü]+){0,2})\b')
    candidates = name_pattern.findall(raw_text)

    # Filter out obvious false positives (countries, month names, common words)
    stop_words = {
        home_team, away_team, "World", "Cup", "FIFA", "Match", "Today", "Group",
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
        "January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December",
        "Starting", "Lineup", "Confirmed", "Official", "Preview"
    }
    # Only keep tokens that appear at least twice (more likely to be actual players)
    from collections import Counter
    counts = Counter(candidates)
    players = [name for name, cnt in counts.most_common(30) if cnt >= 1 and name not in stop_words and len(name) > 3]

    if len(players) < 8:
        return None  # Not enough names found to constitute a real lineup

    # Split heuristically: first ~11 into home, next ~11 into away
    # (Web snippets rarely split cleanly; we return what we have and let AI fill gaps)
    home_players = players[:11]
    away_players = players[11:22]

    if len(home_players) < 8:
        return None

    return {
        "home_lineup": home_players,
        "away_lineup": away_players,
        "confirmed": len(away_players) >= 8
    }


def fetch_and_store_lineups(match_objects: List["Match"], api_key: str) -> None:
    """
    For each match in match_objects that does NOT already have a confirmed 11-man lineup,
    fetches the lineup via a 3-tier priority:
      1. API-Football /fixtures/lineups  (most reliable — official data when announced)
      2. Web scrape (DuckDuckGo/Yahoo) for confirmed starting XI articles
      3. Gemini AI projection (always produces a result — guaranteed non-empty fallback)
    Updates the match record in Supabase.
    Works for any date's matches — not restricted to today.
    """
    af_key = os.environ.get("API_FOOTBALL_KEY", "")

    for match in match_objects:
        # Skip if already confirmed with a full 11-man lineup
        if match.lineup_status == LineupStatus.CONFIRMED and len(match.home_lineup) >= 11:
            st.write(f"  ✅ `{match.home_team} vs {match.away_team}`: confirmed lineup already stored, skipping.")
            continue

        home_lineup: List[str] = []
        away_lineup: List[str] = []
        new_status = LineupStatus.PROJECTED
        source_label = ""

        # -------------------------------------------------------------------
        # TIER 1: API-Football /fixtures/lineups
        # Looks up the fixture by date + team, then fetches its official lineup.
        # Only returns data once the lineup has been officially announced (~1hr before KO).
        # -------------------------------------------------------------------
        if af_key:
            try:
                headers = {"x-apisports-key": af_key}
                match_date = match.kickoff_time.date().isoformat()
                home_id = _af_find_team_id(match.home_team)
                away_id = _af_find_team_id(match.away_team)

                if home_id:
                    fx_resp = requests.get(
                        f"{_AF_BASE}/fixtures",
                        headers=headers,
                        params={"league": _AF_WC_LEAGUE, "season": _AF_WC_SEASON,
                                "team": home_id, "date": match_date},
                        timeout=10
                    )
                    if fx_resp.status_code == 200:
                        fx_list = fx_resp.json().get("response", [])
                        # Find the fixture matching both teams
                        fx_id = None
                        for fx in fx_list:
                            h_id = fx["teams"]["home"]["id"]
                            a_id = fx["teams"]["away"]["id"]
                            if (h_id == home_id and a_id == away_id) or \
                               (h_id == away_id and a_id == home_id):
                                fx_id = fx["fixture"]["id"]
                                break

                        if fx_id:
                            lu_resp = requests.get(
                                f"{_AF_BASE}/fixtures/lineups",
                                headers=headers,
                                params={"fixture": fx_id},
                                timeout=10
                            )
                            if lu_resp.status_code == 200:
                                lu_data = lu_resp.json().get("response", [])
                                for team_lu in lu_data:
                                    tid = team_lu["team"]["id"]
                                    starters = [p["player"]["name"] for p in team_lu.get("startXI", [])]
                                    if tid == home_id:
                                        home_lineup = starters
                                    elif tid == away_id:
                                        away_lineup = starters

                                if len(home_lineup) >= 11 and len(away_lineup) >= 11:
                                    new_status = LineupStatus.CONFIRMED
                                    source_label = "🟢 Confirmed (API-Football)"
                                    print(f"[AF] Lineups confirmed for {match.match_id}: {len(home_lineup)}/{len(away_lineup)} players")
            except Exception as af_err:
                print(f"[DEBUG] API-Football lineup fetch failed for {match.match_id}: {af_err}")

        # -------------------------------------------------------------------
        # TIER 2: Web scrape (DuckDuckGo / Yahoo News)
        # Used when API-Football hasn't announced the lineup yet.
        # -------------------------------------------------------------------
        if len(home_lineup) < 11 or len(away_lineup) < 11:
            try:
                scraped = scrape_confirmed_lineup(match.home_team, match.away_team)
                if scraped and len(scraped.get("home_lineup", [])) >= 8:
                    if len(home_lineup) < 11:
                        home_lineup = scraped["home_lineup"][:11]
                    if len(away_lineup) < 11:
                        away_lineup = scraped.get("away_lineup", [])[:11]
                    if scraped.get("confirmed") and len(home_lineup) >= 8 and len(away_lineup) >= 8:
                        new_status = LineupStatus.CONFIRMED
                        source_label = "🟢 Confirmed (web)"
                    else:
                        source_label = "🟡 Partial (web scrape)"
            except Exception as scrape_err:
                print(f"[DEBUG] Web lineup scrape failed for {match.match_id}: {scrape_err}")

        # -------------------------------------------------------------------
        # TIER 3: Gemini AI projection
        # Always runs if either lineup is still incomplete — guarantees non-empty result.
        # -------------------------------------------------------------------
        if (len(home_lineup) < 11 or len(away_lineup) < 11) and api_key:
            try:
                gen = generate_projected_lineups(match.home_team, match.away_team, api_key)
                if gen:
                    if len(home_lineup) < 11:
                        home_lineup = gen.get("home_lineup", [])
                    if len(away_lineup) < 11:
                        away_lineup = gen.get("away_lineup", [])
                    if not source_label:
                        source_label = "🔵 AI Projected"
                    elif "Confirmed" not in source_label:
                        source_label += " + AI fill"
                    new_status = LineupStatus.PROJECTED
            except Exception as gen_err:
                print(f"[DEBUG] AI lineup generation failed for {match.match_id}: {gen_err}")

        if not home_lineup and not away_lineup:
            st.write(f"  ⚠️ `{match.home_team} vs {match.away_team}`: all lineup sources failed.")
            continue

        # --- Persist to Supabase ---
        try:
            supabase.table("matches").update({
                "home_lineup": home_lineup,
                "away_lineup": away_lineup,
                "lineup_status": new_status
            }).eq("match_id", match.match_id).execute()

            match.home_lineup = home_lineup
            match.away_lineup = away_lineup
            match.lineup_status = new_status

            st.write(f"  {source_label} — `{match.home_team} vs {match.away_team}` ({len(home_lineup)} / {len(away_lineup)} players)")
        except Exception as db_err:
            print(f"[DEBUG] Failed to store lineup for {match.match_id}: {db_err}")


# Keep old name as alias for backward compat
fetch_and_store_lineups_for_today = fetch_and_store_lineups




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
    Correctly extracts the UTC offset from strings like "3:00 pm UTC-6" and
    converts the local time to true UTC for accurate storage and display.
    """
    import re
    from datetime import timedelta
    # Replace non-breaking spaces
    time_str = time_str.replace('\xa0', ' ').strip()
    # Normalize unicode minus signs to standard hyphen-minus
    time_str = time_str.replace('\u2212', '-').replace('\u2013', '-')

    # Extract UTC offset (e.g. UTC-6, UTC+2) before stripping it
    utc_offset_hours = 0
    offset_match = re.search(r'UTC([+-])(\d+)', time_str)
    if offset_match:
        sign = 1 if offset_match.group(1) == '+' else -1
        utc_offset_hours = sign * int(offset_match.group(2))

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

    # Apply the offset to convert local venue time → true UTC
    dt_utc = dt - timedelta(hours=utc_offset_hours)
    return dt_utc.replace(tzinfo=timezone.utc)


def to_central_time(dt_utc: datetime) -> tuple:
    """
    Converts a UTC datetime to US Central Time (CDT = UTC-5 in summer,
    CST = UTC-6 Nov–Mar). Returns (dt_central, label) where label is
    'CDT' or 'CST'.
    """
    from datetime import timedelta
    # CDT (UTC-5): second Sunday in March through first Sunday in November
    year = dt_utc.year
    # Second Sunday in March
    march = datetime(year, 3, 1)
    dst_start = march.replace(day=8 + (6 - march.weekday()) % 7)  # first Sunday
    dst_start = dst_start.replace(day=dst_start.day + 7)           # second Sunday
    # First Sunday in November
    november = datetime(year, 11, 1)
    dst_end = november.replace(day=1 + (6 - november.weekday()) % 7)
    # Both boundaries at 02:00 UTC (07:00 CST → spring forward / 06:00 CDT → fall back)
    dst_start_utc = dst_start.replace(hour=8, tzinfo=timezone.utc)   # 02:00 CST = 08:00 UTC
    dst_end_utc   = dst_end.replace(hour=7, tzinfo=timezone.utc)     # 02:00 CDT = 07:00 UTC
    if dst_start_utc <= dt_utc < dst_end_utc:
        return dt_utc + timedelta(hours=-5), "CDT"
    else:
        return dt_utc + timedelta(hours=-6), "CST"


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


_COUNTRY_CODES = {
    "germany": "de",
    "sweden": "se",
    "netherlands": "nl",
    "belgium": "be",
    "spain": "es",
    "ivorycoast": "ci",
    "cotedivoire": "ci",
    "japan": "jp",
    "saudiarabia": "sa",
    "egypt": "eg",
    "uruguay": "uy",
    "argentina": "ar",
    "france": "fr",
    "norway": "no",
    "senegal": "sn",
    "jordan": "jo",
    "algeria": "dz",
    "iraq": "iq",
    "newzealand": "nz",
    "ecuador": "ec",
    "usa": "us",
    "unitedstates": "us",
    "mexico": "mx",
    "canada": "ca",
    "brazil": "br",
    "england": "gb-eng",
    "portugal": "pt",
    "morocco": "ma",
    "croatia": "hr",
    "italy": "it",
    "curacao": "cw",
    "tunisia": "tn",
    "austria": "at",
    "iran": "ir",
    "capeverde": "cv",
    "colombia": "co",
    "chile": "cl",
    "peru": "pe",
    "venezuela": "ve",
    "paraguay": "py",
    "bolivia": "bo",
    "southkorea": "kr",
    "korearepublic": "kr",
    "china": "cn",
    "qatar": "qa",
    "unitedarabemirates": "ae",
    "uae": "ae",
    "nigeria": "ng",
    "cameroon": "cm",
    "ghana": "gh",
    "southafrica": "za",
    "switzerland": "ch",
    "denmark": "dk",
    "poland": "pl",
    "ukraine": "ua",
    "turkey": "tr",
    "turkiye": "tr",
    "greece": "gr",
    "czechrepublic": "cz",
    "czechia": "cz",
    "hungary": "hu",
    "romania": "ro",
    "scotland": "gb-sct",
    "wales": "gb-wls",
    "slovakia": "sk",
    "slovenia": "si",
    "finland": "fi",
    "ireland": "ie",
    "republicofireland": "ie",
    "iceland": "is",
    "jamaica": "jm",
    "costarica": "cr",
    "panama": "pa",
    "honduras": "hn",
    "elsalvador": "sv",
    "haiti": "ht",
    "australia": "au"
}

def get_country_code(team_name: str) -> Optional[str]:
    clean_team = clean_name(team_name)
    # Exact match first
    for k, v in _COUNTRY_CODES.items():
        if clean_name(k) == clean_team:
            return v
    # Substring match second
    for k, v in _COUNTRY_CODES.items():
        clean_k = clean_name(k)
        if clean_k in clean_team or clean_team in clean_k:
            return v
    return None


_FBREF_SQUAD_MAP = {
    "germany": "c1e260a9/Germany-Men-Stats",
    "sweden": "4c23f20f/Sweden-Men-Stats",
    "netherlands": "f666f289/Netherlands-Men-Stats",
    "belgium": "361ca2ad/Belgium-Men-Stats",
    "spain": "b561befe/Spain-Men-Stats",
    "ivorycoast": "f2043e09/Ivory-Coast-Men-Stats",
    "japan": "c85f3a22/Japan-Men-Stats",
    "saudiarabia": "b26f5fcf/Saudi-Arabia-Men-Stats",
    "egypt": "26e382d5/Egypt-Men-Stats",
    "uruguay": "87ca1a50/Uruguay-Men-Stats",
    "argentina": "f9f3c054/Argentina-Men-Stats",
    "france": "370d0a8b/France-Men-Stats",
    "norway": "80e922b0/Norway-Men-Stats",
    "senegal": "22d5f2f5/Senegal-Men-Stats",
    "jordan": "70df5cfa/Jordan-Men-Stats",
    "algeria": "97c0f0df/Algeria-Men-Stats",
    "iraq": "72dfdf2a/Iraq-Men-Stats",
    "newzealand": "76f0c10f/New-Zealand-Men-Stats",
    "ecuador": "2f8d488c/Ecuador-Men-Stats",
}

@st.cache_data(ttl=86400)
def get_fbref_squad_stats(team_name: str) -> dict:
    """
    Scrapes the FBRef team stats page for advanced metrics (possession, xG, shots, etc.).
    Cached for 24 hours to prevent rate limit blocks.
    """
    clean_team = clean_name(team_name)
    squad_slug = _FBREF_SQUAD_MAP.get(clean_team)
    if not squad_slug:
        # Fallback: search clean name key
        for k, v in _FBREF_SQUAD_MAP.items():
            if k in clean_team or clean_team in k:
                squad_slug = v
                break
                
    if not squad_slug:
        return {}

    url = f"https://fbref.com/en/squads/{squad_slug}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        import re
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            return {}
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        stats = {}
        
        # 1. Parse standard stats (possession, goals, xG, etc.)
        std_table = soup.find("table", id=re.compile(r"stats_standard"))
        if std_table:
            tfoot = std_table.find("tfoot")
            if tfoot:
                cols = tfoot.find_all("td")
                for td in cols:
                    stat_name = td.get("data-stat")
                    if stat_name in ("goals", "assists", "xg", "xg_xgag_co", "pens_made"):
                        stats[stat_name] = td.get_text().strip()
                        
        # 2. Parse shooting stats (shots, shots on target, etc.)
        shoot_table = soup.find("table", id=re.compile(r"stats_shooting"))
        if shoot_table:
            tfoot = shoot_table.find("tfoot")
            if tfoot:
                cols = tfoot.find_all("td")
                for td in cols:
                    stat_name = td.get("data-stat")
                    if stat_name in ("shots", "shots_on_target", "shots_on_target_pct", "shots_per90", "shots_on_target_per90"):
                        stats[stat_name] = td.get_text().strip()

        return stats
    except Exception as e:
        print(f"[DEBUG] Error scraping FBRef for {team_name}: {e}")
        return {}


@st.cache_data(ttl=7200)
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


_AF_BASE = "https://v3.football.api-sports.io"
_AF_WC_LEAGUE = 1      # FIFA World Cup
_AF_WC_SEASON = 2026   # 2026 season

# ---------------------------------------------------------------------------
# Budget-aware API-Football request helper
# Each call is independently cached by (endpoint, frozen params, ttl bucket)
# so different data types can have different cache lifetimes.
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)   # 1 hour — default for most match-day data
def _af_get_1h(endpoint: str, params_key: str, params: dict) -> dict:
    """Cached GET with 1-hour TTL. params_key must be a hashable string."""
    api_key = os.environ.get("API_FOOTBALL_KEY", "")
    if not api_key:
        return {}
    try:
        headers = {"x-apisports-key": api_key}
        resp = requests.get(f"{_AF_BASE}/{endpoint}", headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            remaining = resp.headers.get("x-ratelimit-requests-remaining", "?")
            print(f"[AF] {endpoint} | remaining today: {remaining}")
            return resp.json()
    except Exception as e:
        print(f"[DEBUG] API-Football request failed ({endpoint}): {e}")
    return {}


@st.cache_data(ttl=14400)  # 4 hours — slow-changing data (injuries, player stats, team stats)
def _af_get_4h(endpoint: str, params_key: str, params: dict) -> dict:
    """Cached GET with 4-hour TTL. params_key must be a hashable string."""
    api_key = os.environ.get("API_FOOTBALL_KEY", "")
    if not api_key:
        return {}
    try:
        headers = {"x-apisports-key": api_key}
        resp = requests.get(f"{_AF_BASE}/{endpoint}", headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            remaining = resp.headers.get("x-ratelimit-requests-remaining", "?")
            print(f"[AF] {endpoint} | remaining today: {remaining}")
            return resp.json()
    except Exception as e:
        print(f"[DEBUG] API-Football request failed ({endpoint}): {e}")
    return {}


# Keep backward compat — existing calls used _af_get at 15min TTL;
# migrate them to 1h since lineup/form don't need 15-min refresh.
def _af_get(endpoint: str, params: dict) -> dict:
    """Convenience wrapper — routes to 1h cache."""
    return _af_get_1h(endpoint, str(sorted(params.items())), params)


@st.cache_data(ttl=3600)
def _af_find_team_id(team_name: str) -> Optional[int]:
    """Searches API-Football for a team by name and returns its integer ID."""
    data = _af_get_1h("teams", str({"name": team_name, "league": _AF_WC_LEAGUE}),
                      {"name": team_name, "league": _AF_WC_LEAGUE, "season": _AF_WC_SEASON})
    teams = data.get("response", [])
    if teams:
        return teams[0]["team"]["id"]
    # Broad fallback — search without league filter
    data2 = _af_get_1h("teams", str({"name": team_name}), {"name": team_name})
    teams2 = data2.get("response", [])
    if teams2:
        return teams2[0]["team"]["id"]
    return None


def get_api_football_context(home_team: str, away_team: str) -> str:
    """
    Fetches structured, factual data from API-Football for the given match.
    Budget: ~15 requests on first call, ~0 on repeat (cached).

    Data fetched:
      1. Last 5 results + form string per team             (2 req, 1hr cache)
      2. Head-to-head record, last 10 meetings             (1 req, 1hr cache)
      3. Group standings                                   (1 req, 1hr cache)
      4. Today's confirmed lineup                          (2 req, 1hr cache)
      5. Tournament aggregate team stats (shots/corners…)  (2 req, 4hr cache)  ← NEW
      6. Active injury list per team                       (2 req, 4hr cache)  ← NEW
      7. Model predictions (win %, goals, comparison)      (1 req, 1hr cache)  ← NEW
      8. Per-player tournament stats (starters only)       (2 req, 4hr cache)  ← NEW
    """
    api_key = os.environ.get("API_FOOTBALL_KEY", "")
    if not api_key:
        return ""

    sections = []

    # --- Resolve team IDs ---
    home_id = _af_find_team_id(home_team)
    away_id = _af_find_team_id(away_team)

    if not home_id or not away_id:
        print(f"[DEBUG] API-Football: could not resolve team IDs for {home_team} ({home_id}) / {away_team} ({away_id})")
        return ""

    # --- Last 5 fixtures for each team ---
    def _format_form(team_name: str, team_id: int) -> str:
        data = _af_get_1h("fixtures", str({"team": team_id, "last": 5}),
                          {"team": team_id, "league": _AF_WC_LEAGUE, "season": _AF_WC_SEASON,
                           "last": 5, "status": "FT"})
        fixtures = data.get("response", [])
        if not fixtures:
            return f"{team_name}: No recent results found in API-Football."
        lines = [f"{team_name} — Last {len(fixtures)} results:"]
        form_chars = []
        for f in reversed(fixtures):
            home = f["teams"]["home"]["name"]
            away = f["teams"]["away"]["name"]
            hg = f["goals"]["home"] if f["goals"]["home"] is not None else "?"
            ag = f["goals"]["away"] if f["goals"]["away"] is not None else "?"
            winner = f["teams"]["home"]["winner"]
            if f["teams"]["home"]["id"] == team_id:
                result = "W" if winner is True else ("L" if winner is False else "D")
                lines.append(f"  {result}  {home} {hg}\u2013{ag} {away}")
            else:
                result = "W" if winner is False else ("L" if winner is True else "D")
                lines.append(f"  {result}  {home} {hg}\u2013{ag} {away}")
            form_chars.append(result)
        lines.append(f"  Form (oldest\u2192newest): {''.join(form_chars)}")
        return "\n".join(lines)

    sections.append("[TEAM FORM — API-Football (Real Data)]")
    sections.append(_format_form(home_team, home_id))
    sections.append("")
    sections.append(_format_form(away_team, away_id))

    # --- Head-to-Head ---
    h2h_data = _af_get_1h("fixtures/headtohead",
                           str({"h2h": f"{home_id}-{away_id}", "last": 10}),
                           {"h2h": f"{home_id}-{away_id}", "last": 10})
    h2h_fixtures = h2h_data.get("response", [])
    if h2h_fixtures:
        sections.append("")
        sections.append("[HEAD-TO-HEAD — API-Football (Real Data, Last 10)]")
        home_wins = away_wins = draws = 0
        for f in h2h_fixtures:
            home = f["teams"]["home"]["name"]
            away = f["teams"]["away"]["name"]
            hg = f["goals"]["home"] if f["goals"]["home"] is not None else "?"
            ag = f["goals"]["away"] if f["goals"]["away"] is not None else "?"
            winner = f["teams"]["home"]["winner"]
            dt = f["fixture"]["date"][:10]
            sections.append(f"  {dt}: {home} {hg}\u2013{ag} {away}")
            if winner is None:
                draws += 1
            elif f["teams"]["home"]["id"] == home_id and winner is True:
                home_wins += 1
            elif f["teams"]["away"]["id"] == home_id and winner is False:
                home_wins += 1
            else:
                away_wins += 1
        sections.append(f"  Summary: {home_team} {home_wins}W \u2014 {draws}D \u2014 {away_wins}W {away_team}")

    # --- Group Standings ---
    standings_data = _af_get_1h("standings", str({"league": _AF_WC_LEAGUE, "season": _AF_WC_SEASON}),
                                {"league": _AF_WC_LEAGUE, "season": _AF_WC_SEASON})
    standings_resp = standings_data.get("response", [])
    if standings_resp:
        all_groups = standings_resp[0].get("league", {}).get("standings", [])
        home_group = away_group = None
        for grp in all_groups:
            team_ids_in_group = [t["team"]["id"] for t in grp]
            if home_id in team_ids_in_group:
                home_group = grp
            if away_id in team_ids_in_group:
                away_group = grp

        def _format_group(group: list) -> str:
            lines = []
            for t in group:
                rank = t.get("rank", "?")
                name = t["team"]["name"]
                pts = t["points"]
                played = t["all"]["played"]
                gd = t["goalsDiff"]
                gf = t["all"]["goals"]["for"]
                ga = t["all"]["goals"]["against"]
                form = t.get("form", "")
                # Qualification context
                status = t.get("description", "")
                status_note = f" [{status}]" if status else ""
                lines.append(f"  {rank}. {name:<25} {played}P  {pts}pts  GD:{gd:+d}  ({gf}:{ga})  Form:{form}{status_note}")
            return "\n".join(lines)

        if home_group:
            sections.append("")
            sections.append(f"[GROUP STANDINGS \u2014 {home_team}'s Group]")
            sections.append(_format_group(home_group))
        if away_group and away_group is not home_group:
            sections.append("")
            sections.append(f"[GROUP STANDINGS \u2014 {away_team}'s Group]")
            sections.append(_format_group(away_group))

    # --- Today's Confirmed Lineup (if announced) ---
    today_str = date.today().isoformat()
    fixture_data = _af_get_1h("fixtures", str({"team": home_id, "date": today_str}),
                              {"team": home_id, "league": _AF_WC_LEAGUE,
                               "season": _AF_WC_SEASON, "date": today_str})
    today_fixtures = fixture_data.get("response", [])
    fixture_id = None
    confirmed_starters: dict = {}   # team_id -> list of player names
    for fx in today_fixtures:
        h_id = fx["teams"]["home"]["id"]
        a_id = fx["teams"]["away"]["id"]
        if (h_id == home_id and a_id == away_id) or (h_id == away_id and a_id == home_id):
            fixture_id = fx["fixture"]["id"]
            break

    if fixture_id:
        lineup_data = _af_get_1h("fixtures/lineups", str({"fixture": fixture_id}),
                                 {"fixture": fixture_id})
        lineup_resp = lineup_data.get("response", [])
        if lineup_resp:
            sections.append("")
            sections.append("[CONFIRMED LINEUPS \u2014 API-Football]")
            for team_lu in lineup_resp:
                tname = team_lu["team"]["name"]
                tid = team_lu["team"]["id"]
                formation = team_lu.get("formation", "N/A")
                starters = [p["player"]["name"] for p in team_lu.get("startXI", [])]
                confirmed_starters[tid] = starters
                sections.append(f"  {tname} ({formation}): {', '.join(starters)}")

    # -----------------------------------------------------------------------
    # NEW SECTION 5: Tournament aggregate team statistics (4hr cache)
    # 1 request per team = 2 requests total
    # -----------------------------------------------------------------------
    def _format_team_stats(team_name: str, team_id: int) -> str:
        data = _af_get_4h("teams/statistics",
                          str({"team": team_id, "league": _AF_WC_LEAGUE}),
                          {"team": team_id, "league": _AF_WC_LEAGUE, "season": _AF_WC_SEASON})
        resp = data.get("response", {})
        if not resp:
            return f"{team_name}: No tournament stats available yet."

        fixtures = resp.get("fixtures", {})
        goals_for = resp.get("goals", {}).get("for", {})
        goals_against = resp.get("goals", {}).get("against", {})
        played = fixtures.get("played", {}).get("total", 0) or 1  # avoid div/0

        gf_total = goals_for.get("total", {}).get("total", 0) or 0
        ga_total = goals_against.get("total", {}).get("total", 0) or 0
        gf_avg = round(gf_total / played, 2)
        ga_avg = round(ga_total / played, 2)

        clean_sheets = resp.get("clean_sheet", {}).get("total", "N/A")
        failed_to_score = resp.get("failed_to_score", {}).get("total", "N/A")

        wins = fixtures.get("wins", {}).get("total", "?")
        draws = fixtures.get("draws", {}).get("total", "?")
        losses = fixtures.get("loses", {}).get("total", "?")

        lines = [
            f"{team_name} — Tournament Aggregate Stats ({played} games played):",
            f"  Record: {wins}W {draws}D {losses}L",
            f"  Goals For: {gf_total} ({gf_avg}/game) | Goals Against: {ga_total} ({ga_avg}/game)",
            f"  Clean Sheets: {clean_sheets} | Failed to Score: {failed_to_score}",
        ]

        # Biggest win / heaviest defeat
        biggest = resp.get("biggest", {})
        bw = biggest.get("wins", {}).get("total", "")
        bl = biggest.get("loses", {}).get("total", "")
        if bw:
            lines.append(f"  Biggest Win: {bw}")
        if bl:
            lines.append(f"  Heaviest Defeat: {bl}")

        # Average goals by half
        gf_h1 = goals_for.get("minute", {}).get("0-45", {}).get("total", 0) or 0
        gf_h2 = goals_for.get("minute", {}).get("46-90", {}).get("total", 0) or 0
        ga_h1 = goals_against.get("minute", {}).get("0-45", {}).get("total", 0) or 0
        ga_h2 = goals_against.get("minute", {}).get("46-90", {}).get("total", 0) or 0
        lines.append(f"  Goals by Half — Scored: H1={gf_h1} H2={gf_h2} | Conceded: H1={ga_h1} H2={ga_h2}")

        return "\n".join(lines)

    sections.append("")
    sections.append("[TEAM TOURNAMENT STATISTICS \u2014 API-Football (Real Data)]")
    sections.append(_format_team_stats(home_team, home_id))
    sections.append("")
    sections.append(_format_team_stats(away_team, away_id))

    # -----------------------------------------------------------------------
    # NEW SECTION 6: Active injuries (4hr cache)
    # 1 request per team = 2 requests total
    # -----------------------------------------------------------------------
    def _format_injuries(team_name: str, team_id: int) -> str:
        data = _af_get_4h("injuries",
                          str({"team": team_id, "league": _AF_WC_LEAGUE, "season": _AF_WC_SEASON}),
                          {"team": team_id, "league": _AF_WC_LEAGUE, "season": _AF_WC_SEASON})
        inj_list = data.get("response", [])
        if not inj_list:
            return f"{team_name}: No injuries reported in API-Football."
        lines = [f"{team_name} Injury Report:"]
        for entry in inj_list[:10]:  # cap at 10 to avoid prompt bloat
            player = entry.get("player", {}).get("name", "Unknown")
            ptype = entry.get("player", {}).get("type", "")
            reason = entry.get("player", {}).get("reason", "")
            lines.append(f"  \u2022 {player} \u2014 {ptype}: {reason}")
        return "\n".join(lines)

    sections.append("")
    sections.append("[INJURY REPORT \u2014 API-Football (Real Data)]")
    sections.append(_format_injuries(home_team, home_id))
    sections.append("")
    sections.append(_format_injuries(away_team, away_id))

    # -----------------------------------------------------------------------
    # NEW SECTION 7: Model predictions (1hr cache)
    # 1 request per fixture
    # Only runs when fixture_id is known (today's game)
    # -----------------------------------------------------------------------
    if fixture_id:
        pred_data = _af_get_1h("predictions",
                               str({"fixture": fixture_id}),
                               {"fixture": fixture_id})
        pred_resp = pred_data.get("response", [])
        if pred_resp:
            pred = pred_resp[0]
            predictions = pred.get("predictions", {})
            winner_pred = predictions.get("winner", {}) or {}
            advice = predictions.get("advice", "")
            goals_home = predictions.get("goals", {}).get("home", "?")
            goals_away = predictions.get("goals", {}).get("away", "?")
            under_over = predictions.get("under_over", "?")  # e.g. "+2.5" or "-2.5"

            comparison = pred.get("comparison", {})

            def _comp(key: str) -> str:
                c = comparison.get(key, {})
                h = c.get("home", "?")
                a = c.get("away", "?")
                return f"{h} / {a}"

            sections.append("")
            sections.append("[API-FOOTBALL MODEL PREDICTIONS \u2014 Statistical Model Output]")
            sections.append(f"  Predicted winner: {winner_pred.get('name', '?')} (comment: {winner_pred.get('comment', '?')})")
            sections.append(f"  Model advice: {advice}")
            sections.append(f"  Predicted goals: {home_team} {goals_home} \u2013 {goals_away} {away_team}")
            sections.append(f"  Model over/under lean: {under_over}")
            sections.append("  Team comparison scores (home / away):")
            for metric in ["form", "att", "def", "poisson_distribution", "h2h", "goals", "total"]:
                val = _comp(metric)
                if val != "? / ?":
                    sections.append(f"    {metric:<22}: {val}")
            sections.append("  NOTE: Use this as a supplementary signal, not a primary source.")

    # -----------------------------------------------------------------------
    # NEW SECTION 8: Per-player tournament stats (starters only, 4hr cache)
    # 1 request per team = 2 requests total
    # Filtered to players in the confirmed starting XI to stay focused
    # -----------------------------------------------------------------------
    def _format_player_stats(team_name: str, team_id: int, starter_names: list) -> str:
        data = _af_get_4h("players",
                          str({"team": team_id, "league": _AF_WC_LEAGUE, "season": _AF_WC_SEASON}),
                          {"team": team_id, "league": _AF_WC_LEAGUE, "season": _AF_WC_SEASON})
        players = data.get("response", [])
        if not players:
            return f"{team_name}: No player stats available yet."

        # If we have starter names, filter to just those. Otherwise show top 11 by minutes.
        def _name_match(api_name: str, starter_list: list) -> bool:
            api_lower = api_name.lower()
            return any(
                s.lower() in api_lower or api_lower in s.lower()
                for s in starter_list
            )

        if starter_names:
            relevant = [p for p in players if _name_match(p["player"]["name"], starter_names)]
        else:
            relevant = sorted(players,
                              key=lambda p: p["statistics"][0].get("games", {}).get("minutes", 0) or 0,
                              reverse=True)[:11]

        if not relevant:
            return f"{team_name}: Could not match player stats to starters."

        lines = [f"{team_name} — Player Tournament Stats (starters):"]
        lines.append(f"  {'Name':<22} {'Pos':<5} {'Min':>4} {'G':>3} {'A':>3} {'Sh':>4} {'SoT':>4} {'KP':>4} {'FC':>4} {'YC':>3}")
        lines.append(f"  {'-'*70}")
        for entry in relevant:
            p = entry["player"]
            s = entry["statistics"][0] if entry.get("statistics") else {}
            name = p.get("name", "?")[:22]
            pos = (s.get("games", {}).get("position") or "?")[:5]
            mins = s.get("games", {}).get("minutes") or 0
            goals = s.get("goals", {}).get("total") or 0
            assists = s.get("goals", {}).get("assists") or 0
            shots = s.get("shots", {}).get("total") or 0
            sot = s.get("shots", {}).get("on") or 0
            kp = s.get("passes", {}).get("key") or 0
            fc = s.get("fouls", {}).get("committed") or 0
            yc = s.get("cards", {}).get("yellow") or 0
            lines.append(f"  {name:<22} {pos:<5} {mins:>4} {goals:>3} {assists:>3} {shots:>4} {sot:>4} {kp:>4} {fc:>4} {yc:>3}")
        lines.append("  (Cols: Min=minutes, G=goals, A=assists, Sh=shots, SoT=shots on target, KP=key passes, FC=fouls committed, YC=yellow cards)")
        return "\n".join(lines)

    home_starters = confirmed_starters.get(home_id, [])
    away_starters = confirmed_starters.get(away_id, [])

    sections.append("")
    sections.append("[PLAYER TOURNAMENT STATISTICS \u2014 API-Football (Real Data)]")
    sections.append("Use shot (Sh/SoT) columns for player shots props. Use YC/FC for cards markets.")
    sections.append(_format_player_stats(home_team, home_id, home_starters))
    sections.append("")
    sections.append(_format_player_stats(away_team, away_id, away_starters))

    return "\n".join(sections)


@st.cache_data(ttl=7200)
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
            with DDGS(timeout=3) as ddgs:
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


@st.cache_data(ttl=7200)
def get_general_news_context(home_team: str, away_team: str) -> str:
    """
    Fetches general team news and injury intel for the match, with a 2-hour cache.
    """
    raw_research = ""
    try:
        from duckduckgo_search import DDGS
        with DDGS(timeout=3) as ddgs:
            query = f"{home_team} vs {away_team} world cup 2026 team news injuries"
            results = list(ddgs.news(query, max_results=5))
            if not results:
                results = list(ddgs.news(f"{home_team} vs {away_team} football", max_results=5))
            for r in results:
                raw_research += f"  • {r.get('title')}: {r.get('body', '')}\n"
    except Exception as ddg_err:
        print(f"[DEBUG] DDG news failed: {ddg_err}")

    # Fallback to Yahoo News
    if len(raw_research.strip()) < 50:
        try:
            query = f"{home_team} vs {away_team} world cup 2026 team news"
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

    return raw_research


def try_grounded_generation(prompt: str, api_key: str) -> Optional[str]:
    """
    Attempts to use Google Search Grounding for real-time web research during generation.
    Tries Gemini 2.0/2.5 models with grounding enabled, with a 25-second timeout.
    Returns None on any failure so the caller can fall back to manual DDG search.
    """
    genai.configure(api_key=api_key)
    grounding_models = ['gemini-2.5-flash', 'gemini-2.0-flash']

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
                request_options={"timeout": 12}
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
    # Convert to lowercase
    n = name.lower()
    # Normalize special characters/unicodes
    n = n.replace("\ufffd", "c")  # handles Curaao/Curaao style encoding issues
    n = n.replace("ç", "c")
    n = n.replace("ã", "a")
    n = n.replace("í", "i")
    n = n.replace("é", "e")
    n = n.replace("&", "and")
    # Remove any characters that are not lowercase letters or digits
    import re
    n = re.sub(r'[^a-z0-9]', '', n)
    return n


def compress_and_structure_news(raw_news: str) -> str:
    """
    Compresses raw news snippets by filtering for lines containing tactical,
    injury, card, referee, or line information, and eliminating near-duplicate lines.
    """
    if not raw_news:
        return ""
    import re
    keywords = [
        "injur", "out", "doubt", "questionable", "suspend", "miss", "absence", "return",
        "recover", "fitness", "muscle", "hamstring", "ankle", "knee", "calf", "groin",
        "card", "red", "yellow", "referee", "appoint", "lineup", "tactical", "formation",
        "pressing", "style", "odds", "boost", "promo", "total", "spread", "moneyline",
        "goalscorer", "shots", "corners", "history", "h2h", "xg", "expected goals", "versus", "vs"
    ]
    seen_normalized = set()
    cleaned_lines = []
    
    # Split raw news into lines/bullets
    for line in raw_news.split("\n"):
        line = line.strip()
        if not line:
            continue
        
        # Check if line matches keywords
        lower_line = line.lower()
        if not any(kw in lower_line for kw in keywords):
            continue
            
        # Deduplicate using alphanumeric characters
        norm_key = re.sub(r'[^a-z0-9]', '', lower_line)
        # Skip if we already have this line or a very short substring
        if norm_key in seen_normalized:
            continue
        
        # Keep track
        seen_normalized.add(norm_key)
        
        # Format bullet nicely if it isn't already
        if not line.startswith("•") and not line.startswith("-") and not line.startswith("*"):
            line = f"• {line}"
            
        cleaned_lines.append(line)
        
    return "\n".join(cleaned_lines)


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

        # Check cache unless bypassed
        bypass = st.session_state.get("bypass_sync_cache", False)
        if not bypass:
            try:
                existing_matches = supabase.table("matches").select("match_id, updated_at").filter("kickoff_time", "gte", f"{target_date_iso}T00:00:00-05:00").filter("kickoff_time", "lte", f"{target_date_iso}T23:59:59-05:00").execute()
                if existing_matches.data:
                    newest_update = None
                    for m in existing_matches.data:
                        up_at = m.get("updated_at")
                        if up_at:
                            try:
                                dt = datetime.fromisoformat(up_at.replace("Z", "+00:00"))
                                if newest_update is None or dt > newest_update:
                                    newest_update = dt
                            except Exception:
                                pass
                    if newest_update:
                        now_utc = datetime.now(timezone.utc)
                        diff_sec = (now_utc - newest_update).total_seconds()
                        if diff_sec < 900:  # 15 minutes
                            st.info(f"⚡ Using cached match & odds data (synced {int(diff_sec // 60)}m ago). Check 'Bypass Sync Cache' in the sidebar to force refresh.")
                            # Re-populate venue_map
                            venue_map = {}
                            try:
                                all_matches = get_wikipedia_matches()
                                for wm in all_matches:
                                    if wm["date"] == target_date_iso:
                                        venue_map[f"{wm['home_team']}|{wm['away_team']}"] = wm.get("venue_city", "")
                            except Exception:
                                pass
                            st.session_state['venue_map'] = venue_map
                            return
            except Exception as cache_check_err:
                print(f"[DEBUG] Error checking sync cache: {cache_check_err}")
        
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

                    # --- Game Lines: Moneyline, Spread, Total ---
                    if dg_desc == "Game Lines":
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            outcomes = []
                            for out in market.get("outcomes", []):
                                outcomes.append({
                                    "selection": out.get("description"),
                                    "price": out.get("price", {}).get("american")
                                })
                            if m_desc == "3-Way Moneyline":
                                bovada_odds_summary["Moneyline"] = outcomes
                            elif m_desc == "Total":
                                bovada_odds_summary["Total Goals"] = outcomes
                            elif m_desc == "Goal Spread":
                                bovada_odds_summary["Spread"] = outcomes

                    # --- Goalscorer: Anytime, First, 2+, Hat Trick, Header ---
                    elif dg_desc == "Goalscorer":
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            outcomes = []
                            for out in market.get("outcomes", []):
                                outcomes.append({
                                    "player": out.get("description"),
                                    "price": out.get("price", {}).get("american")
                                })
                            if m_desc == "Anytime Goal Scorer":
                                bovada_odds_summary["Anytime Goalscorer"] = outcomes
                            elif m_desc == "First Goal Scorer":
                                bovada_odds_summary["First Goalscorer"] = outcomes
                            elif m_desc == "To Score 2 or More Goals":
                                bovada_odds_summary["To Score 2+ Goals"] = outcomes
                            elif m_desc == "To Score a Hat Trick":
                                bovada_odds_summary["Hat Trick Scorer"] = outcomes
                            elif m_desc == "To Score a Header":
                                bovada_odds_summary["Header Scorer"] = outcomes
                            elif m_desc == "To Score or Assist a Goal":
                                bovada_odds_summary["To Score or Assist"] = outcomes

                    # --- Assists ---
                    elif dg_desc == "Assists":
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            outcomes = []
                            for out in market.get("outcomes", []):
                                outcomes.append({
                                    "player": out.get("description"),
                                    "price": out.get("price", {}).get("american")
                                })
                            if m_desc == "To Assist a Goal":
                                bovada_odds_summary["To Assist a Goal"] = outcomes
                            elif m_desc == "To Score or Assist a Goal":
                                bovada_odds_summary["To Score or Assist (Assists)"] = outcomes

                    # --- Player Props: Shots, Shots on Target, Saves, Tackles per player ---
                    elif dg_desc == "Player Props":
                        shots_markets = {}
                        sot_markets = {}
                        saves_markets = {}
                        tackles_markets = {}
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            outcomes = []
                            for out in market.get("outcomes", []):
                                outcomes.append({
                                    "selection": out.get("description"),
                                    "price": out.get("price", {}).get("american")
                                })
                            if m_desc.startswith("Shots on Target - "):
                                player = m_desc.replace("Shots on Target - ", "")
                                sot_markets[player] = outcomes
                            elif m_desc.startswith("Shots - "):
                                player = m_desc.replace("Shots - ", "")
                                shots_markets[player] = outcomes
                            elif m_desc.startswith("Saves - "):
                                player = m_desc.replace("Saves - ", "")
                                saves_markets[player] = outcomes
                            elif m_desc.startswith("Tackles - "):
                                player = m_desc.replace("Tackles - ", "")
                                tackles_markets[player] = outcomes
                        if shots_markets:
                            bovada_odds_summary["Player Shots"] = shots_markets
                        if sot_markets:
                            bovada_odds_summary["Player Shots on Target"] = sot_markets
                        if saves_markets:
                            bovada_odds_summary["Player Saves"] = saves_markets
                        if tackles_markets:
                            bovada_odds_summary["Player Tackles"] = tackles_markets

                    # --- Game Stats: Team-level shots / shots on target ---
                    elif dg_desc == "Game Stats":
                        game_stats = {}
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            outcomes = []
                            for out in market.get("outcomes", []):
                                outcomes.append({
                                    "selection": out.get("description"),
                                    "price": out.get("price", {}).get("american")
                                })
                            game_stats[m_desc] = outcomes
                        if game_stats:
                            bovada_odds_summary["Game Stats"] = game_stats

                    # --- Corners: Total, Race to X ---
                    elif dg_desc == "Corners":
                        corners_data = {}
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            outcomes = []
                            for out in market.get("outcomes", []):
                                outcomes.append({
                                    "selection": out.get("description"),
                                    "price": out.get("price", {}).get("american")
                                })
                            corners_data[m_desc] = outcomes
                        if "Total Corners" in corners_data:
                            bovada_odds_summary["Corners"] = corners_data["Total Corners"]
                        bovada_odds_summary["Corners Markets"] = corners_data

                    # --- Cards: Total Cards O/U, Player to be shown a card ---
                    elif dg_desc == "Cards":
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            outcomes = []
                            for out in market.get("outcomes", []):
                                outcomes.append({
                                    "selection": out.get("description"),
                                    "price": out.get("price", {}).get("american")
                                })
                            if m_desc == "Total Cards Under/Over":
                                bovada_odds_summary["Total Cards"] = outcomes
                            elif m_desc == "To be Shown a Card":
                                bovada_odds_summary["Player Cards"] = outcomes

                    # --- Game Props: BTTS, Double Chance, Draw No Bet, Correct Score ---
                    elif dg_desc == "Game Props":
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            outcomes = []
                            for out in market.get("outcomes", []):
                                outcomes.append({
                                    "selection": out.get("description"),
                                    "price": out.get("price", {}).get("american")
                                })
                            if m_desc == "Both Teams To Score":
                                bovada_odds_summary["Both Teams to Score"] = outcomes
                            elif m_desc == "Double Chance":
                                bovada_odds_summary["Double Chance"] = outcomes
                            elif m_desc == "Draw No Bet":
                                bovada_odds_summary["Draw No Bet"] = outcomes
                            elif m_desc == "Correct Score":
                                bovada_odds_summary["Correct Score"] = outcomes

                    # --- Combo Props: Result + BTTS, Result + O/U ---
                    elif dg_desc == "Combo Props":
                        combo_data = {}
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            outcomes = []
                            for out in market.get("outcomes", []):
                                outcomes.append({
                                    "selection": out.get("description"),
                                    "price": out.get("price", {}).get("american")
                                })
                            combo_data[m_desc] = outcomes
                        if combo_data:
                            bovada_odds_summary["Combo Props"] = combo_data

                    # --- Alternate Lines ---
                    elif dg_desc == "Alternate Lines":
                        alt_data = {}
                        for market in dg.get("markets", []):
                            m_desc = market.get("description", "")
                            outcomes = []
                            for out in market.get("outcomes", []):
                                outcomes.append({
                                    "selection": out.get("description"),
                                    "price": out.get("price", {}).get("american")
                                })
                            alt_data[m_desc] = outcomes
                        if alt_data:
                            bovada_odds_summary["Alternate Lines"] = alt_data

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

We have also fetched comprehensive live data from Bovada (if available), including:
- Game Lines (Moneyline, Spread, Total)
- All Goalscorer markets (Anytime, First, 2+, Hat Trick, Header)
- Player Props per individual player (Shots, Shots on Target, Saves, Tackles)
- Game Stats (team-level total shots, total shots on target)
- Corners (Total Corners and Race to X)
- Cards (Total Cards O/U, Player Cards)
- Assists (To Assist a Goal)
- Game Props (BTTS, Double Chance, Draw No Bet, Correct Score)
- Combo Props (Result + BTTS, Result + Over/Under)
- Alternate Lines
{bovada_odds_context if bovada_odds_context else "None available"}

And we have scraped the following recent web search snippets (including player prop lines and sportsbook previews) for these matchups:
{rag_search_context if rag_search_context else "None available"}

We have also scraped the following general and match-specific DraftKings promotions and odds boosts snippets:
{dk_promos_context if dk_promos_context else "None available"}

Task:
Generate a unique match_id (e.g. "GER-CIV-2026") for each match, and provide betting odds for ALL available markets grounded on the real Bovada and Odds API data above.

CRITICAL ODDS MAPPING REQUIREMENTS:
1. For ALL markets where Bovada has live data, you MUST use those EXACT prices and selections:
   - "Moneyline" → use Bovada 3-Way Moneyline prices exactly (Home, Away, Draw).
   - "BTTS" → use Bovada "Both Teams to Score" prices exactly.
   - "Total Goals" → use Bovada "Total Goals" prices exactly.
   - "Spread" → use Bovada "Goal Spread" prices exactly.
   - "Corners" → use Bovada "Total Corners" prices exactly.
   - "Anytime Goalscorer" → output ALL players from Bovada with exact prices.
   - "First Goalscorer" → output ALL players from Bovada with exact prices.
   - "To Score 2+ Goals" → output ALL players from Bovada with exact prices.
   - "Hat Trick Scorer" → output ALL players from Bovada with exact prices.
   - "Header Scorer" → output ALL players from Bovada with exact prices.
   - "To Assist a Goal" → output ALL players from Bovada with exact prices.
   - "To Score or Assist" → output ALL players from Bovada with exact prices.
   - "Player Shots on Target" → output ALL players, ALL outcome lines from Bovada with exact prices.
   - "Player Shots" → output ALL players, ALL outcome lines from Bovada with exact prices.
   - "Player Saves" → output ALL goalkeepers, ALL outcome lines from Bovada with exact prices.
   - "Player Tackles" → output ALL players, ALL outcome lines from Bovada with exact prices.
   - "Game Stats" → use Bovada team-level shots/SOT lines with exact prices.
   - "Total Cards" → use Bovada "Total Cards" lines with exact prices.
   - "Player Cards" → output ALL players from Bovada with exact prices.
   - "Double Chance" → use Bovada "Double Chance" prices exactly.
   - "Draw No Bet" → use Bovada "Draw No Bet" prices exactly.
   - "Correct Score" → use Bovada "Correct Score" prices exactly.
   - "Combo Props" → use Bovada "Combo Props" prices exactly.
2. Format Player Prop selections as: "Player Name Over X.5 Shots on Target", "Player Name 2+ Tackles", etc.
3. Only estimate/simulate odds when NO real data exists from any source.
4. For Promo/Boost: only add if found in DraftKings snippet data.


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
     {{"match_id": "...", "market_type": "Moneyline", "selection": "Home Team name, Away Team name, or Draw", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "BTTS", "selection": "Yes or No", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Total Goals", "selection": "Over X.5 or Under X.5", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Spread", "selection": "Team Name +/-X.5", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Corners", "selection": "Over Y.5 Corners or Under Y.5 Corners", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Anytime Goalscorer", "selection": "Player Name to Score", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "First Goalscorer", "selection": "Player Name", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "To Score 2+ Goals", "selection": "Player Name", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Hat Trick Scorer", "selection": "Player Name", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Header Scorer", "selection": "Player Name", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "To Assist a Goal", "selection": "Player Name", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "To Score or Assist", "selection": "Player Name", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Player Shots", "selection": "Player Name Over/Under X.5 Shots", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Player Shots on Target", "selection": "Player Name Over/Under X.5 Shots on Target", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Player Saves", "selection": "Player Name Over/Under X.5 Saves", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Player Tackles", "selection": "Player Name Over/Under X.5 Tackles", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Game Stats", "selection": "e.g. Total Shots Over 22.5", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Total Cards", "selection": "Over/Under X.5 Cards", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Player Cards", "selection": "Player Name to be Shown a Card", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Double Chance", "selection": "e.g. Home/Draw or Away/Draw", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Draw No Bet", "selection": "Home Team or Away Team", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Correct Score", "selection": "e.g. 1-0 or 2-1", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Combo Props", "selection": "e.g. Japan win and Yes BTTS", "dk_odds": integer}},
     {{"match_id": "...", "market_type": "Promo/Boost", "selection": "Descriptive boosted selection string", "dk_odds": integer}}
  ]
}}

Guidelines:
1. Three Moneyline selections per match using Bovada exact prices.
2. Two BTTS selections (Yes/No) using Bovada exact prices.
3. Two Total Goals selections using the exact Bovada line and prices.
4. Two Spread selections using the exact Bovada handicap and prices.
5. Two Corners selections using the exact Bovada Total Corners line and prices.
6. Anytime Goalscorer, First Goalscorer, To Score 2+ Goals, Hat Trick Scorer, Header Scorer: output ALL players from Bovada with exact prices.
7. To Assist a Goal and To Score or Assist: output ALL players from Bovada with exact prices.
8. Player Shots, Player SOT, Player Saves, Player Tackles: output ALL players, ALL lines from Bovada with exact prices. Format: "Player Name Over/Under X.5 [stat]".
9. Game Stats (team shots/SOT): output all available Bovada lines exactly.
10. Total Cards and Player Cards: output all Bovada lines exactly.
11. Double Chance, Draw No Bet, Correct Score, Combo Props: use Bovada prices exactly.
12. Promo/Boost: only include if found in DraftKings snippet data.
13. Use integer American odds (EVEN → 100, +150 → 150, -110 → -110).
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
        if 'odds_trend_history' not in st.session_state:
            st.session_state['odds_trend_history'] = {}

        try:
            matches_to_del = supabase.table("matches").select("match_id").filter("kickoff_time", "gte", f"{target_date_iso}T00:00:00-05:00").filter("kickoff_time", "lte", f"{target_date_iso}T23:59:59-05:00").execute()
            ids_to_del = [m['match_id'] for m in matches_to_del.data]
            if ids_to_del:
                # Snapshot current odds BEFORE deleting (line movement baseline)
                existing_odds_resp = supabase.table("odds").select("match_id,market_type,selection,dk_odds").in_("match_id", ids_to_del).execute()
                for o in existing_odds_resp.data:
                    key = f"{o['match_id']}|{o['market_type']}|{o['selection']}"
                    line_movement_data[key] = o['dk_odds']
                    # Log to trend history
                    history = st.session_state['odds_trend_history'].setdefault(key, [])
                    if not history or history[-1] != o['dk_odds']:
                        history.append(o['dk_odds'])
                        if len(history) > 5:
                            history.pop(0)

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
            # Record final synced odds in trend history
            for o in discovered_odds:
                key = f"{o['match_id']}|{o['market_type']}|{o['selection']}"
                history = st.session_state.setdefault('odds_trend_history', {}).setdefault(key, [])
                if not history or history[-1] != o['dk_odds']:
                    history.append(o['dk_odds'])
                    if len(history) > 5:
                        history.pop(0)
            
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


def validate_sgp_legs(legs: list) -> bool:
    """
    Programmatically checks SGP legs for logical contradictions and mathematical impossibility.
    Returns True if valid (no contradictions), and False if invalid (contradiction found).
    """
    if not legs or len(legs) < 2:
        return False
        
    moneylines = []
    btts_selections = []
    totals = {}
    spreads = {}
    
    for leg in legs:
        sel = leg.get("selection", "").strip()
        mtype = leg.get("market_type", "").strip()
        
        # 1. Moneyline contradictions
        if mtype == "Moneyline":
            moneylines.append(sel.lower())
            
        # 2. BTTS contradictions
        elif mtype == "BTTS":
            btts_selections.append(sel.lower())
            
        # 3. Total Goals contradictions
        elif mtype == "Total Goals":
            parts = sel.split()
            if len(parts) == 2:
                direction = parts[0].lower() # over/under
                try:
                    line = float(parts[1])
                    totals[direction] = line
                except ValueError:
                    pass
                    
        # 4. Spread contradictions
        elif mtype == "Spread":
            parts = sel.split()
            if len(parts) >= 2:
                team = " ".join(parts[:-1]).lower()
                handicap_str = parts[-1]
                try:
                    handicap = float(handicap_str)
                    spreads[team] = handicap
                except ValueError:
                    pass

    # -- Apply logical rule checks --
    
    # Rule A: Cannot select more than one Moneyline outcome
    if len(moneylines) > 1:
        print(f"[DEBUG] SGP Validation Failed: Multiple Moneyline outcomes selected ({moneylines})")
        return False
        
    # Rule B: Cannot select both BTTS Yes and BTTS No
    if "yes" in btts_selections and "no" in btts_selections:
        print(f"[DEBUG] SGP Validation Failed: Both BTTS Yes and No selected")
        return False
        
    # Rule C: Conflicting Total Goals limits (e.g. Over 2.5 and Under 2.5)
    if "over" in totals and "under" in totals:
        over_val = totals["over"]
        under_val = totals["under"]
        if over_val >= under_val:
            print(f"[DEBUG] SGP Validation Failed: Contradictory goals limits (Over {over_val} vs Under {under_val})")
            return False
            
    # Rule D: BTTS Yes and Under 1.5 Goals is impossible
    if "yes" in btts_selections:
        if "under" in totals and totals["under"] <= 1.5:
            print(f"[DEBUG] SGP Validation Failed: BTTS Yes is incompatible with Under {totals['under']} goals")
            return False
            
    # Rule E: Contradictory Spreads (e.g. Germany -1.5 and Ivory Coast -1.5)
    if len(spreads) > 1:
        negative_spreads = [t for t, h in spreads.items() if h < 0]
        if len(negative_spreads) > 1:
            print(f"[DEBUG] SGP Validation Failed: Multiple negative spreads selected ({spreads})")
            return False
            
    return True


def compute_implied_probabilities(odds_data: list) -> str:
    """
    Pre-computes implied and vig-adjusted probabilities for every market in odds_data.
    Groups selections by market_type, strips the bookmaker's vig, then returns a
    formatted string table ready to paste directly into the AI prompt.

    For a two-outcome market (e.g. BTTS Yes/No):
      raw_implied  = 1 / decimal_odds   for each outcome
      vig          = sum(raw_implied) - 1.0
      vig_adjusted = raw_implied / sum(raw_implied)   (normalised to 100%)

    For three-outcome markets (Moneyline: Home / Draw / Away) the same formula applies.
    """
    from collections import defaultdict

    def american_to_decimal(odds: int) -> float:
        if odds >= 0:
            return (odds / 100.0) + 1.0
        else:
            return (100.0 / abs(odds)) + 1.0

    def american_to_raw_implied(odds: int) -> float:
        dec = american_to_decimal(odds)
        return 1.0 / dec if dec > 0 else 0.0

    # Group by market_type
    markets: dict = defaultdict(list)
    for o in odds_data:
        markets[o["market_type"]].append(o)

    lines = []
    lines.append(f"{'Market':<30} {'Selection':<35} {'Odds':>7} {'Raw Impl%':>10} {'Vig-Adj%':>10} {'Vig':>6} {'EV/1u':>8}")
    lines.append("-" * 110)

    for mtype, entries in sorted(markets.items()):
        # Compute raw implied probabilities
        raw_implieds = [american_to_raw_implied(e["dk_odds"]) for e in entries]
        total_raw = sum(raw_implieds)
        vig_pct = (total_raw - 1.0) * 100.0 if total_raw > 0 else 0.0

        for entry, raw_imp in zip(entries, raw_implieds):
            odds = entry["dk_odds"]
            sel  = entry["selection"]

            # Vig-adjusted (fair) probability
            vig_adj = (raw_imp / total_raw * 100.0) if total_raw > 0 else 0.0

            # EV per 1 unit staked, assuming the vig-adjusted prob is the TRUE probability
            # EV = p_true * profit - (1 - p_true) * stake
            # At these fair odds, EV = 0 (breakeven). The AI's job is to decide if true prob > vig_adj.
            # We show EV assuming the vig-adjusted prob *is* true (should be ~0 at fair odds).
            dec = american_to_decimal(odds)
            profit = dec - 1.0
            p = vig_adj / 100.0
            ev = round((p * profit) - ((1.0 - p) * 1.0), 3)

            lines.append(
                f"{mtype:<30} {sel:<35} {odds:>+7d} {raw_imp*100:>9.1f}% {vig_adj:>9.1f}% {vig_pct:>5.1f}% {ev:>+8.3f}u"
            )
        lines.append("")  # blank row between markets

    return "\n".join(lines)


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
            return {"error": "No odds data found in the database for this match. Please run the sync pipeline first."}
        valid_options_str = "\n".join(
            [f"- Selection: '{o['selection']}' | Market Type: '{o['market_type']}'" for o in odds_data]
        )

        # --- 1b. Pre-compute implied probabilities (strips vig, gives AI clean numbers) ---
        prob_table = compute_implied_probabilities(odds_data)

        # --- 2. Line movement context (multi-sync trend) ---
        trend_history = st.session_state.get('odds_trend_history', {})
        line_movement_str = ""
        movements = []
        for o in odds_data:
            key = f"{o['match_id']}|{o['market_type']}|{o['selection']}"
            history = trend_history.get(key, [])
            if len(history) >= 2:
                trajectory_str = " → ".join([f"{val:+d}" for val in history])
                delta = history[-1] - history[0]
                direction = "▲ SHARPER" if delta < 0 else "▼ LONGER"
                movements.append(
                    f"  {o['market_type']}: {o['selection']} trend: {trajectory_str} ({direction}, total Δ{delta:+d})"
                )
            else:
                line_movement_data = st.session_state.get('line_movement_data', {})
                old_odds = line_movement_data.get(key)
                if old_odds is not None and old_odds != o['dk_odds']:
                    delta = o['dk_odds'] - old_odds
                    direction = "▲ SHARPER" if delta < 0 else "▼ LONGER"
                    movements.append(
                        f"  {o['market_type']}: {o['selection']} moved {old_odds:+d} → {o['dk_odds']:+d} ({direction}, Δ{delta:+d})"
                    )
        if movements:
            line_movement_str = "\n".join(movements)
            print(f"[DEBUG] Detected line movement(s) for {match.match_id}:\n{line_movement_str}")

        # --- 3. Venue weather context ---
        match_date_str = match.kickoff_time.strftime("%Y-%m-%d")
        venue_map = st.session_state.get('venue_map', {})
        venue_city = venue_map.get(f"{match.home_team}|{match.away_team}", "")
        weather_str = get_weather_context(venue_city, match_date_str) if venue_city else ""
        print(f"[DEBUG] Weather context for {match.match_id}: {weather_str[:80] if weather_str else 'N/A'}")

        # --- 4. Form, H2H, xG, referee context (DDG fallback) ---
        print(f"[DEBUG] Fetching form/H2H/xG/referee context for {match.home_team} vs {match.away_team}...")
        extended_research = get_form_and_h2h_context(match.home_team, match.away_team)

        # --- 4b. API-Football structured data (real stats — higher priority than DDG snippets) ---
        print(f"[DEBUG] Fetching API-Football structured data for {match.home_team} vs {match.away_team}...")
        api_football_context = get_api_football_context(match.home_team, match.away_team)
        if api_football_context:
            print(f"[DEBUG] API-Football returned {len(api_football_context)} chars of structured data.")
        else:
            print(f"[DEBUG] API-Football returned no data (key missing or teams not found).")

        # --- 4c. FBRef advanced squad stats ---
        print(f"[DEBUG] Fetching FBRef advanced squad stats for {match.home_team} vs {match.away_team}...")
        fbref_home_stats = get_fbref_squad_stats(match.home_team)
        fbref_away_stats = get_fbref_squad_stats(match.away_team)
        fbref_context = f"""
{match.home_team} FBRef Stats:
{json.dumps(fbref_home_stats, indent=2) if fbref_home_stats else "No FBRef stats found or squad not mapped."}

{match.away_team} FBRef Stats:
{json.dumps(fbref_away_stats, indent=2) if fbref_away_stats else "No FBRef stats found or squad not mapped."}
"""

        # --- 5. General match news (DDG/Yahoo) ---
        print(f"[DEBUG] Fetching general match news for {match.home_team} vs {match.away_team}...")
        raw_research = get_general_news_context(match.home_team, match.away_team)

        # Compress news & research before sending to AI
        compressed_news = compress_and_structure_news(raw_research)
        if not compressed_news.strip() and raw_research.strip():
            compressed_news = "\n".join([f"• {line.strip()}" for line in raw_research.split("\n") if line.strip()][:5])

        compressed_extended = compress_and_structure_news(extended_research)
        if not compressed_extended.strip() and extended_research.strip():
            compressed_extended = "\n".join([f"• {line.strip()}" for line in extended_research.split("\n") if line.strip()][:8])

        # --- 6. Build structured prompt ---
        prompt = f"""
You are an elite sports betting analyst, oddsmaker, and tactical football expert.
Your task: evaluate the World Cup 2026 match {match.home_team} vs {match.away_team} using ALL data sections below.
For EVERY recommendation, explicitly cite which section(s) of data most influenced it.
All bet types are on the table: Moneyline, BTTS, Total Goals, Spread, Corners, Anytime Goalscorer, Player Shots, Player Shots on Target, Promo/Boost, SGP.

══════════════════════════════════════════
[SECTION 1: LIVE ODDS, IMPLIED PROBABILITIES & LINE MOVEMENT]
══════════════════════════════════════════
PRE-COMPUTED MARKET PROBABILITIES (vig already stripped — use these directly):
Columns: Market | Selection | DK Odds | Raw Implied% | Vig-Adjusted% | Book Vig% | Breakeven EV/1u

HOW TO USE: Your job is to estimate whether the TRUE win probability for a selection
exceeds its Vig-Adjusted% figure. If your estimate is higher, there is positive expected value (EV).
EV formula: EV = (your_true_prob × potential_profit) − ((1 − your_true_prob) × 1u stake)
Only recommend selections where you assess TRUE probability > Vig-Adjusted%.

{prob_table}

Line Movement Since Last Sync (sharp money indicator):
{line_movement_str if line_movement_str else "No prior snapshot available (first sync or no change)."}
NOTE: Lines moving shorter (more negative) WITHOUT proportional public volume = sharp/professional money. This is a HIGH-VALUE signal.

══════════════════════════════════════════
[SECTION 2: CONFIRMED LINEUPS]
══════════════════════════════════════════
{match.home_team}: {", ".join(match.home_lineup) if match.home_lineup else 'Not yet confirmed'}
{match.away_team}: {", ".join(match.away_lineup) if match.away_lineup else 'Not yet confirmed'}

══════════════════════════════════════════
[SECTION 3: STRUCTURED STATS — API-Football (REAL DATA — PRIORITISE THIS)]
══════════════════════════════════════════
This section contains verified factual data pulled directly from the API-Football database.
Use it as the primary source for team form, H2H history, group standings, and confirmed lineups.
Do NOT override this data with assumptions from other sections.

{api_football_context if api_football_context else 'API-Football data unavailable for this match (key not set or teams not found).'}

══════════════════════════════════════════
[SECTION 3b: ADVANCED TEAM STATS — FBRef (xG, SHOTS)]
══════════════════════════════════════════
Use these verified squad-level metrics from FBRef (shots, shots on target, xG, xGA, etc.) to analyze tactical efficiency:
{fbref_context}

══════════════════════════════════════════
[SECTION 4: SUPPLEMENTAL FORM, H2H & xG — WEB SEARCH SNIPPETS]
══════════════════════════════════════════
Use these web search snippets to supplement Section 3 (e.g. for xG, pressing stats, referee data not available from API-Football).
If Section 3 contradicts these snippets, trust Section 3.
{compressed_extended if compressed_extended else 'No extended research data retrieved.'}

══════════════════════════════════════════
[SECTION 5: MATCH NEWS & INJURY INTEL]
══════════════════════════════════════════
{compressed_news if compressed_news else 'No match news retrieved — use your knowledge base.'}

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
9. Tactical style clash: Using Sections 3, 3b, 4, and your own knowledge, explicitly analyze the style matchup:
   - What formation/system does each team use?
   - Is one team a high-press side facing a slow-buildup team? A possession side facing a low-block?
   - Which team's style exploits the other's known weakness?
   - Does this style clash favor high or low total goals? More or fewer corners? More or fewer cards?
   - Use this style analysis to refine ALL your Total Goals, BTTS, Corners, and Spread recommendations.
10. Fair value assessment: For EACH selection you consider recommending:
    a. State your estimated TRUE win probability as a percentage.
    b. Compare it to the Vig-Adjusted% from Section 1.
    c. Calculate EV = (true_prob × potential_profit) − ((1 − true_prob) × 1.0u)
    d. Only recommend if EV > 0 (true_prob > Vig-Adjusted%).
    e. Set edge_pct = true_prob − Vig-Adjusted% (e.g. if you assess 58% true vs 51.2% vig-adj, edge_pct = 6.8)
11. Recommend ALL positive-EV selections. For Promo/Boost, compare boosted odds vs your true odds.
12. If 2+ value picks exist, evaluate whether combining them into an SGP makes betting sense:
    - Only construct an SGP if the legs have a strong positive correlation (e.g. Under 2.5 and Underdog Spread) such that the parlay offers a correlation edge.
    - Do NOT construct an SGP if the picks are uncorrelated, negatively correlated, or redundant.
    - The rationale for the SGP MUST explain the correlation dynamics.
13. Conviction level: "High" (multiple confirming signals + edge_pct > 5%), "Medium" (1-2 signals or edge_pct 2-5%), "Low" (single signal or edge_pct < 2%).
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
      "true_prob_pct": number,
      "vig_adj_pct": number,
      "edge_pct": number,
      "ev_per_unit": number,
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
        raw_research_display += f"[MATCH NEWS]\n{raw_research}\n\n[FBRef ADVANCED STATS]\n{fbref_context}\n\n[FORM / H2H / xG / REFEREE]\n{extended_research}\n\n[WEATHER]\n{weather_str}\n\n[LINE MOVEMENT]\n{line_movement_str or 'None detected'}"

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
                return {"error": f"AI responded with invalid JSON format that could not be parsed: {e2}"}
            
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
                    
                if not validate_sgp_legs(validated_legs):
                    print(f"[DEBUG] SGP failed correlation validation. Skipping recommendation.")
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
        return {"error": str(e)}

def get_final_scores(api_key: str = "") -> Dict[str, str]:
    """
    Fetches final scores for completed World Cup matches.
    Primary source: API-Football /fixtures?status=FT (structured, accurate).
    Fallback: Wikipedia schedule scrape (less reliable, used only if API-Football key absent).
    Returns a dict mapping match_id -> score string e.g. "2-1".
    Also stores fixture_id -> match_id mapping in session state for prop resolution.
    """
    af_key = os.environ.get("API_FOOTBALL_KEY", "")

    # --- Primary: API-Football ---
    if af_key:
        try:
            headers = {"x-apisports-key": af_key}
            resp = requests.get(
                f"{_AF_BASE}/fixtures",
                headers=headers,
                params={"league": _AF_WC_LEAGUE, "season": _AF_WC_SEASON, "status": "FT"},
                timeout=12
            )
            if resp.status_code == 200:
                fixtures = resp.json().get("response", [])
                print(f"[AF] get_final_scores: {len(fixtures)} FT fixtures found.")

                # Build match_id -> score map by fuzzy-matching against our DB
                matches_resp = supabase.table("matches").select("match_id,home_team,away_team").execute()
                db_matches = matches_resp.data

                final_scores: Dict[str, str] = {}
                fixture_id_map: Dict[str, int] = {}  # match_id -> af fixture_id

                for fx in fixtures:
                    af_home = fx["teams"]["home"]["name"].lower()
                    af_away = fx["teams"]["away"]["name"].lower()
                    hg = fx["goals"]["home"]
                    ag = fx["goals"]["away"]
                    if hg is None or ag is None:
                        continue
                    score_str = f"{hg}-{ag}"
                    fx_id = fx["fixture"]["id"]

                    # Fuzzy match against DB
                    for dbm in db_matches:
                        db_home = dbm["home_team"].lower()
                        db_away = dbm["away_team"].lower()
                        home_match = af_home in db_home or db_home in af_home
                        away_match = af_away in db_away or db_away in af_away
                        if home_match and away_match:
                            final_scores[dbm["match_id"]] = score_str
                            fixture_id_map[dbm["match_id"]] = fx_id
                            break

                # Persist fixture_id_map in session state for prop resolution lookups
                st.session_state["af_fixture_id_map"] = fixture_id_map
                if final_scores:
                    return final_scores
                # Fall through to Wikipedia fallback if no matches aligned
        except Exception as e:
            print(f"[DEBUG] API-Football final scores failed: {e}")

    # --- Fallback: Wikipedia ---
    try:
        import re
        wiki_matches = get_wikipedia_matches()
        completed = [m for m in wiki_matches if re.match(r'^\d+-\d+$', m.get("score", ""))]
        if not completed:
            return {}
        matches_resp = supabase.table("matches").select("match_id,home_team,away_team").execute()
        db_matches = matches_resp.data
        final_scores = {}
        for m in completed:
            home = m["home_team"].lower()
            away = m["away_team"].lower()
            db_match = next(
                (dbm for dbm in db_matches
                 if home in dbm["home_team"].lower() and away in dbm["away_team"].lower()),
                None
            )
            if db_match:
                final_scores[db_match["match_id"]] = m["score"]
        return final_scores
    except Exception as e:
        print(f"[DEBUG] Wikipedia fallback for final scores failed: {e}")
        return {}


def get_af_fixture_stats(match_id: str) -> Dict[str, Any]:
    """
    Fetches structured per-player events and team statistics from API-Football
    for a completed fixture identified by match_id.
    Used to ground prop settlement with real stats instead of AI guesswork.
    Returns a dict with keys: 'events', 'statistics', 'players'.
    """
    af_key = os.environ.get("API_FOOTBALL_KEY", "")
    if not af_key:
        return {}

    # Look up the API-Football fixture ID from session state
    fixture_id_map = st.session_state.get("af_fixture_id_map", {})
    fx_id = fixture_id_map.get(match_id)
    if not fx_id:
        print(f"[DEBUG] get_af_fixture_stats: no fixture_id for match_id={match_id}")
        return {}

    headers = {"x-apisports-key": af_key}
    result: Dict[str, Any] = {}

    # 1. Fixture events (goals, cards, subs)
    try:
        ev_resp = requests.get(
            f"{_AF_BASE}/fixtures/events",
            headers=headers,
            params={"fixture": fx_id},
            timeout=10
        )
        if ev_resp.status_code == 200:
            result["events"] = ev_resp.json().get("response", [])
            print(f"[AF] fixture/events: {len(result['events'])} events for fixture {fx_id}")
    except Exception as e:
        print(f"[DEBUG] AF fixture/events failed: {e}")

    # 2. Team statistics (shots, corners, cards totals per team)
    try:
        st_resp = requests.get(
            f"{_AF_BASE}/fixtures/statistics",
            headers=headers,
            params={"fixture": fx_id},
            timeout=10
        )
        if st_resp.status_code == 200:
            result["statistics"] = st_resp.json().get("response", [])
            print(f"[AF] fixture/statistics: {len(result['statistics'])} team stat blocks for fixture {fx_id}")
    except Exception as e:
        print(f"[DEBUG] AF fixture/statistics failed: {e}")

    # 3. Per-player match stats (shots, saves, tackles, passes, cards)
    try:
        pl_resp = requests.get(
            f"{_AF_BASE}/fixtures/players",
            headers=headers,
            params={"fixture": fx_id},
            timeout=10
        )
        if pl_resp.status_code == 200:
            result["players"] = pl_resp.json().get("response", [])
            print(f"[AF] fixture/players: {len(result['players'])} player stat blocks for fixture {fx_id}")
    except Exception as e:
        print(f"[DEBUG] AF fixture/players failed: {e}")

    return result


def _format_af_stats_for_settlement(stats: Dict[str, Any], match: "Match") -> str:
    """
    Formats API-Football fixture stats into a readable string to inject into the
    settlement AI prompt, providing concrete grounding for prop resolution.
    """
    lines = []

    # Team statistics block (shots, corners, cards)
    if stats.get("statistics"):
        lines.append("=== OFFICIAL MATCH STATISTICS (API-Football) ===")
        for team_block in stats["statistics"]:
            tname = team_block.get("team", {}).get("name", "?")
            lines.append(f"\n{tname}:")
            for stat in team_block.get("statistics", []):
                stype = stat.get("type", "")
                sval = stat.get("value", "N/A")
                lines.append(f"  {stype}: {sval}")

    # Events (goals, cards, subs)
    if stats.get("events"):
        lines.append("\n=== MATCH EVENTS (Goals, Cards, Subs) ===")
        for ev in stats["events"]:
            minute = ev.get("time", {}).get("elapsed", "?")
            team = ev.get("team", {}).get("name", "?")
            player = ev.get("player", {}).get("name", "?")
            etype = ev.get("type", "?")
            detail = ev.get("detail", "")
            lines.append(f"  {minute}' [{team}] {player} — {etype} ({detail})")

    # Per-player stats
    if stats.get("players"):
        lines.append("\n=== PER-PLAYER MATCH STATISTICS ===")
        lines.append(f"  {'Player':<22} {'Team':<20} {'Min':>4} {'G':>3} {'A':>3} {'Sh':>4} {'SoT':>4} {'Sv':>4} {'Tk':>4} {'YC':>3} {'RC':>3}")
        lines.append(f"  {'-'*80}")
        for team_block in stats["players"]:
            tname = team_block.get("team", {}).get("name", "?")[:20]
            for entry in team_block.get("players", []):
                p = entry.get("player", {})
                s = entry.get("statistics", [{}])[0] if entry.get("statistics") else {}
                name = p.get("name", "?")[:22]
                mins = s.get("games", {}).get("minutes") or 0
                goals = s.get("goals", {}).get("total") or 0
                assists = s.get("goals", {}).get("assists") or 0
                shots = s.get("shots", {}).get("total") or 0
                sot = s.get("shots", {}).get("on") or 0
                saves = s.get("goals", {}).get("saves") or 0
                tackles = s.get("tackles", {}).get("total") or 0
                yc = s.get("cards", {}).get("yellow") or 0
                rc = s.get("cards", {}).get("red") or 0
                lines.append(f"  {name:<22} {tname:<20} {mins:>4} {goals:>3} {assists:>3} {shots:>4} {sot:>4} {saves:>4} {tackles:>4} {yc:>3} {rc:>3}")
        lines.append("  (Cols: Min=minutes, G=goals, A=assists, Sh=shots, SoT=shots on target, Sv=saves, Tk=tackles, YC=yellow cards, RC=red cards)")

    return "\n".join(lines) if lines else ""

def resolve_prop_with_ai(slip: LedgerEntry, match: "Match", api_key: str) -> LedgerStatus:
    """
    Resolves a player prop or stat-based bet for a completed match.
    Strategy:
      1. Fetch structured API-Football fixture stats (goals, shots, corners, cards per player).
      2. Inject those stats as grounded context into the Gemini prompt.
      3. If AF stats are available, Gemini can resolve deterministically from real data.
      4. If AF stats unavailable, fall back to Gemini Grounded Search.
    """
    if not api_key:
        return LedgerStatus.VOID

    # --- Step 1: Fetch structured API-Football stats for this fixture ---
    af_stats = get_af_fixture_stats(match.match_id)
    af_context = _format_af_stats_for_settlement(af_stats, match) if af_stats else ""

    if af_context:
        print(f"[DEBUG] resolve_prop_with_ai: Using API-Football structured stats for {match.match_id}")
        data_source_note = "Use the official API-Football statistics provided below as your PRIMARY source. Do NOT estimate."
    else:
        print(f"[DEBUG] resolve_prop_with_ai: No AF stats — falling back to Gemini grounded search for {match.match_id}")
        data_source_note = "Search the web for the official verified statistics for this match."

    prompt = f"""You are settling a sports bet for the completed World Cup 2026 match:
{match.home_team} vs {match.away_team} — {match.kickoff_time.strftime('%A, %B %d, %Y')}

Bet to settle:
- Market Type: {slip.market_type}
- Selection: {slip.selection}

{data_source_note}

{af_context if af_context else ''}

Based on the statistics above, determine if this bet WON, LOST, or should be VOID.
A bet is VOID only if the player did not start or play in the match.

For Over/Under props (e.g. "Mbappe Over 1.5 Shots on Target"):
- Find the player's actual stat value in the per-player table above.
- Compare it to the threshold in the selection string.
- Output WON or LOST accordingly.

For goalscorer props: check the Events section for Goal events.
For card props: check the Events section for Card events and the per-player YC/RC columns.
For corner props: check the Team Statistics for 'Corner Kicks'.
For saves props: check the per-player Sv column.
For tackles props: check the per-player Tk column.

Format your output strictly as JSON:
{{
  "outcome": "Won|Lost|Void",
  "stat_value": "The actual stat value found (e.g. '2 shots on target', '11 corners', 'scored in 34th minute')",
  "source": "API-Football structured data" or "web search"
}}
"""
    try:
        grounded_result = try_grounded_generation(prompt, api_key)
        content = grounded_result if grounded_result else generate_content_with_fallback(api_key, prompt, json_mode=True)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            data = json.loads(content)

        outcome_str = data.get("outcome", "Void").strip().lower()
        print(f"[DEBUG] Prop settled: '{slip.selection}' ({slip.market_type}) → {outcome_str.upper()} | stat={data.get('stat_value')} | source={data.get('source')}")

        if outcome_str == "won":
            return LedgerStatus.WON
        elif outcome_str == "lost":
            return LedgerStatus.LOST
        else:
            return LedgerStatus.VOID
    except Exception as e:
        print(f"[DEBUG] Error in resolve_prop_with_ai: {e}")
        return LedgerStatus.VOID


def determine_settlement_status(slip: LedgerEntry, match: Match, final_score_str: str, api_key: str = "") -> LedgerStatus:
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
                    status = determine_settlement_status(leg_slip, match, final_score_str, api_key)
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

        elif slip.market_type == "Corners":
            if api_key:
                return resolve_prop_with_ai(slip, match, api_key)
            return LedgerStatus.VOID

        elif slip.market_type == "Anytime Goalscorer":
            if api_key:
                return resolve_prop_with_ai(slip, match, api_key)
            return LedgerStatus.VOID

        elif slip.market_type in ("Player Shots", "Player Shots on Target"):
            if api_key:
                return resolve_prop_with_ai(slip, match, api_key)
            return LedgerStatus.VOID

        elif slip.market_type == "Promo/Boost":
            if api_key:
                return resolve_prop_with_ai(slip, match, api_key)
            return LedgerStatus.VOID

    except (ValueError, IndexError):
        # If score is malformed, cannot determine status
        return LedgerStatus.PENDING

    return LedgerStatus.PENDING  # Default to pending if no logic matches


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
            final_status = determine_settlement_status(slip, match, final_score, api_key)

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
                                status = determine_settlement_status(leg_slip, match, final_score, api_key)
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
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
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

            # Step 2b: Fetch lineups for the synced date's matches
            # Runs for any date — AI projection always produces a result as final fallback.
            target_matches = [
                m for m in all_matches
                if to_central_time(m.kickoff_time)[0].date() == target_date
            ]
            if target_matches:
                status.update(label=f"Fetching lineups for {len(target_matches)} match(es) on {target_date}...")
                st.write(f"**⚽ Lineup Discovery ({target_date})**")
                fetch_and_store_lineups(target_matches, api_key)
            else:
                st.info(f"ℹ️ No matches found for {target_date} — lineup step skipped.")


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
    unit_val = st.session_state.get("unit_value", 10.0)
    net_usd = net_pl * unit_val
    pl_delta_str = f"{net_pl:+.2f}u"
    _card(col3, f"${net_usd:+.2f}", "Net P&L (USD)", pl_delta_str, delta_pos=(net_pl >= 0))
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
            unit_val = st.session_state.get("unit_value", 10.0)
            usd_val = e['net_return'] * unit_val if e['net_return'] is not None else None
            ret_str = f"{e['net_return']:+.2f}u" if e["net_return"] is not None else "N/A"
            if usd_val is not None:
                ret_str += f" (${usd_val:+.2f})"
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
                c3.markdown(f":{color}[**{ret_str}**]")


def render_main_dashboard():
    """Renders the main application dashboard after successful authentication."""
    if os.path.exists("world_cup_2026_banner.png"):
        st.image("world_cup_2026_banner.png", use_container_width=True)
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

        st.checkbox(
            "Bypass Sync Cache (Force Refresh)",
            value=False,
            key="bypass_sync_cache",
            help="Check this to force the pipeline to fetch fresh odds and details from external APIs rather than using cached entries."
        )

        st.markdown("---")
        st.subheader("Unit Customization")
        st.number_input(
            "Unit Value ($)",
            min_value=0.01,
            value=10.0,
            step=1.0,
            key="unit_value",
            help="Define the dollar value of 1 Unit to track real cash returns."
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
        day_matches = [m for m in st.session_state.all_matches if to_central_time(m.kickoff_time)[0].strftime("%Y-%m-%d") == selected_date_str]
        
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

            # Batch sandbox odds fetch once — filter client-side per match
            _match_ids = [m.match_id for m in day_matches]
            try:
                _all_odds = supabase.table("odds").select("id, match_id, market_type, selection, dk_odds").in_("match_id", _match_ids).execute().data
            except Exception:
                _all_odds = []
            _odds_by_match: Dict[str, list] = {}
            for _o in _all_odds:
                _odds_by_match.setdefault(_o["match_id"], []).append(_o)

            # Render matches in a 2-column grid layout
            for i in range(0, len(day_matches), 2):
                chunk = day_matches[i:i+2]
                cols = st.columns(2)
                for col_idx, match in enumerate(chunk):
                    with cols[col_idx]:
                        match_id = match.match_id

                        # Retrieve active API Key
                        api_key = st.session_state.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")

                        # Wrap each match card in a clean container
                        with st.container(border=True):
                            _ct, _ct_label = to_central_time(match.kickoff_time)

                            if match.lineup_status == LineupStatus.CONFIRMED and len(match.home_lineup) >= 11:
                                badge_html = '<span class="badge badge-confirmed">🟢 CONFIRMED LINEUP</span>'
                            elif match.home_lineup:
                                badge_html = '<span class="badge badge-projected">🔵 AI PROJECTED LINEUP</span>'
                            else:
                                badge_html = '<span class="badge badge-none">⚪ NO LINEUP YET</span>'

                            # Clean AI Research status badge
                            res_data = st.session_state.conviction_picks.get(match_id)
                            if res_data is not None:
                                if isinstance(res_data, dict) and "error" in res_data:
                                    research_badge_html = '<span class="badge badge-research-pending">⚠️ FAILED</span>'
                                else:
                                    research_badge_html = '<span class="badge badge-research-done">🧠 RESEARCH DONE</span>'
                            else:
                                research_badge_html = '<span class="badge badge-research-pending">⚪ PENDING</span>'

                            # Resolve country codes for background watermark flags
                            home_code = get_country_code(match.home_team)
                            away_code = get_country_code(match.away_team)

                            home_style = ""
                            if home_code:
                                home_style = f"background: linear-gradient(to right, rgba(15, 23, 42, 0.70), rgba(15, 23, 42, 0.35)), url('https://flagcdn.com/w160/{home_code}.png') no-repeat center; background-size: cover;"

                            away_style = ""
                            if away_code:
                                away_style = f"background: linear-gradient(to left, rgba(15, 23, 42, 0.70), rgba(15, 23, 42, 0.35)), url('https://flagcdn.com/w160/{away_code}.png') no-repeat center; background-size: cover;"

                            st.markdown(f"""
        <div class="scoreboard">
            <div class="scoreboard-team home" style="{home_style}">{match.home_team}</div>
            <div class="scoreboard-vs">VS</div>
            <div class="scoreboard-team away" style="{away_style}">{match.away_team}</div>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; margin-top:-4px;">
            <div style="font-size:0.78rem; color:#94a3b8;">📅 Kickoff: {_ct.strftime('%a %b %d, %I:%M %p')} {_ct_label}</div>
            <div style="display: flex; gap: 8px; align-items: center;">
                {badge_html}
                {research_badge_html}
            </div>
        </div>
        """, unsafe_allow_html=True)

                            # Quick AI Research action button (Clean layout)
                            btn_label = "🔄 Rerun AI Research" if res_data is not None else "🔍 Run AI Research"
                            if st.button(btn_label, key=f"outer_run_res_{match_id}", use_container_width=True):
                                if not api_key:
                                    st.error("Please enter your Gemini API Key in the sidebar.")
                                else:
                                    with st.spinner(f"Evaluating {match.home_team} vs {match.away_team}..."):
                                        pick = evaluate_tactical_matchups_ai(match, api_key)
                                        st.session_state.conviction_picks[match_id] = pick
                                        st.rerun()

                            # Collapsible details expander
                            with st.expander("🔍 Match Details & Analysis", expanded=False):
                                # Create Tabs
                                tab_match, tab_odds, tab_tactics, tab_convictions = st.tabs([
                                    "📋 Match & Lineups",
                                    "📊 Market Odds",
                                    "🧠 Tactical Research",
                                    "🔥 AI Convictions"
                                ])

                                with tab_match:
                                    # Rosters side-by-side
                                    col_h_lineup, col_a_lineup = st.columns(2)
                                    with col_h_lineup:
                                        st.markdown(f"**🛡️ {match.home_team} Lineup**")
                                        if match.home_lineup:
                                            for idx, p in enumerate(match.home_lineup):
                                                st.markdown(f"{idx+1}. {p}")
                                        else:
                                            st.caption("No lineup data.")
                                    with col_a_lineup:
                                        st.markdown(f"**⚔️ {match.away_team} Lineup**")
                                        if match.away_lineup:
                                            for idx, p in enumerate(match.away_lineup):
                                                st.markdown(f"{idx+1}. {p}")
                                        else:
                                            st.caption("No lineup data.")

                                    st.markdown("---")
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
                                            if st.button("🔵 Generate AI Projected Lineup", key=f"gen_lineup_{match_id}", use_container_width=True):
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

                                        # Retrieve odds for this match from the batched dictionary
                                        match_odds = _odds_by_match.get(match_id, [])

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

                                with tab_odds:
                                    match_odds = _odds_by_match.get(match_id, [])
                                    if not match_odds:
                                        st.info("No odds found in the database. Run the sync pipeline to load odds.")
                                    else:
                                        st.markdown("### 📊 Market Odds Comparison")
                                        # Render live odds in a clean table
                                        import pandas as pd
                                        df_display = pd.DataFrame([
                                            {"Market": o["market_type"], "Selection": o["selection"], "Odds": f"{o['dk_odds']:+d}"}
                                            for o in match_odds
                                        ])
                                        st.table(df_display.set_index("Market"))

                                # Retrieve Conviction Picks if they exist
                                picks = []
                                injuries = {}
                                key_battle = ""
                                if res_data is not None:
                                    if isinstance(res_data, dict) and "error" in res_data:
                                        pass
                                    elif isinstance(res_data, list):
                                        picks = res_data
                                    else:
                                        picks = res_data.get("recommendations", []) or []
                                        injuries = res_data.get("injuries", {}) or {}
                                        key_battle = res_data.get("key_battle", "") or {}

                                    # Filter out already-logged picks using the batched ledger dict
                                    logged_selections = _ledger_by_match.get(match_id, set())
                                    picks = [p for p in picks if (p["selection"].lower(), p["market_type"].lower()) not in logged_selections]

                                with tab_tactics:
                                    if res_data is not None and isinstance(res_data, dict) and "error" in res_data:
                                        st.error(f"⚠️ AI Evaluation failed: {res_data['error']}")
                                        st.info("This is typically caused by a rate limit (429) on your free API Key. Please wait a minute and try Rerunning from the top row.")
                                    elif res_data is not None:
                                        if key_battle:
                                            st.markdown(f"⚔️ **Key Battle:** {key_battle}")
                                            st.divider()

                                        col_h, col_a = st.columns(2)
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
                                    else:
                                        st.info("Tactical Research context has not been fetched yet. Click the 'Run AI Research' button above to run AI evaluation.")

                                with tab_convictions:
                                    if res_data is not None:
                                        if picks:
                                            for pick in picks:
                                                render_conviction_card(pick)
                                        else:
                                            st.info("AI Research complete: No pending value recommendations (all logged/used or none found).")
                                    else:
                                        st.info("Run AI Research using the button above to generate conviction picks.")


    st.divider()

    # --- Ledger Display ---
    with st.expander("📋 Selection Ledger", expanded=False):
        # Prop bet types that require manual settlement
        _MANUAL_SETTLE_TYPES = {"Corners", "Anytime Goalscorer", "Player Shots", "Player Shots on Target", "Promo/Boost"}
        try:
            ledger_response = supabase.table("ledger").select("*").order("created_at", desc=True).limit(20).execute()
            ledger_entries = [LedgerEntry.model_validate(e) for e in ledger_response.data]

            if not ledger_entries:
                st.info("Ledger is empty.")
            else:
                has_pending_props = any(
                    e.status == LedgerStatus.PENDING and e.market_type in _MANUAL_SETTLE_TYPES
                    for e in ledger_entries
                )
                if has_pending_props:
                    st.caption(
                        "⚠️ **Prop bets** (Corners, Anytime Goalscorer, Shots) cannot be auto-settled from the scoreline. "
                        "Use the **Won / Lost / Void** buttons below to manually settle them. "
                        "Running the sync pipeline will also automatically void any unsettled props once a final score is recorded."
                    )

                for entry in ledger_entries:
                    status_color = "#94a3b8"
                    if entry.status == LedgerStatus.WON: status_color = "#00ff87"
                    elif entry.status == LedgerStatus.LOST: status_color = "#ff5e62"
                    elif entry.status == LedgerStatus.VOID: status_color = "#ffaa00"

                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            if entry.market_type == "SGP":
                                try:
                                    parlay_data = json.loads(entry.selection)
                                    legs_desc = " + ".join([f"{leg['selection']} ({leg['base_odds']})" for leg in parlay_data.get("legs", [])])
                                    st.markdown(f"**SGP:** {legs_desc} ({entry.base_odds})")
                                except Exception:
                                    st.markdown(f"**{entry.selection}** ({entry.base_odds})")
                            else:
                                st.markdown(f"**{entry.selection}** ({entry.base_odds})")
                            st.caption(f"`{entry.market_type}` · Match: {entry.match_id}")
                        with col2:
                            st.markdown(f'<div style="font-size: 0.9rem; font-weight: 800; color: {status_color}; margin-bottom: 2px;">{entry.status.upper()}</div>', unsafe_allow_html=True)
                            if entry.net_return is not None:
                                unit_val = st.session_state.get("unit_value", 10.0)
                                ret_usd = entry.net_return * unit_val
                                st.markdown(f'<div style="font-size: 1.35rem; font-weight: 900; color: {status_color}; line-height: 1.25;">${ret_usd:+.2f}</div>', unsafe_allow_html=True)
                                st.markdown(f'<div style="font-size: 0.8rem; font-weight: 600; color: {status_color}; opacity: 0.85;">{entry.net_return:+.2f}u</div>', unsafe_allow_html=True)
                            else:
                                st.markdown('<div style="font-size: 1.35rem; font-weight: 900; color: #94a3b8;">N/A</div>', unsafe_allow_html=True)

                        # Manual override and delete controls
                        with st.expander("🛠️ Settle or Delete Bet", expanded=False):
                            mc1, mc2, mc3, mc4 = st.columns(4)
                            slip_id = entry.slip_id
                            base_odds = entry.base_odds
                            unit_risk = entry.unit_risk

                            def _manual_settle(sid=slip_id, outcome=LedgerStatus.WON, odds=base_odds, risk=unit_risk):
                                if outcome == LedgerStatus.WON:
                                    if odds > 0:
                                        nr = round(risk * (odds / 100.0), 2)
                                    else:
                                        nr = round(risk * (100.0 / abs(odds)), 2)
                                elif outcome == LedgerStatus.LOST:
                                    nr = round(-risk, 2)
                                else:
                                    nr = 0.0
                                supabase.table("ledger").update({
                                    "status": outcome.value,
                                    "net_return": nr
                                }).eq("slip_id", sid).execute()
                                st.rerun()

                            def _delete_bet(sid=slip_id):
                                supabase.table("ledger").delete().eq("slip_id", sid).execute()
                                st.rerun()

                            with mc1:
                                if st.button("✅ Won", key=f"manual_won_{slip_id}", use_container_width=True):
                                    _manual_settle(sid=slip_id, outcome=LedgerStatus.WON, odds=base_odds, risk=unit_risk)
                            with mc2:
                                if st.button("❌ Lost", key=f"manual_lost_{slip_id}", use_container_width=True):
                                    _manual_settle(sid=slip_id, outcome=LedgerStatus.LOST, odds=base_odds, risk=unit_risk)
                            with mc3:
                                if st.button("↩️ Void", key=f"manual_void_{slip_id}", use_container_width=True):
                                    _manual_settle(sid=slip_id, outcome=LedgerStatus.VOID, odds=base_odds, risk=unit_risk)
                            with mc4:
                                if st.button("🗑️ Delete", key=f"manual_delete_{slip_id}", use_container_width=True):
                                    _delete_bet(sid=slip_id)

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

        # Prefer the AI-computed edge fields (more accurate — based on vig-adjusted probs)
        ai_edge_pct     = pick.get("edge_pct")       # AI: true_prob - vig_adj_pct
        ai_ev_per_unit  = pick.get("ev_per_unit")    # AI: EV at 1 unit stake
        ai_true_prob    = pick.get("true_prob_pct")  # AI: estimated win probability
        ai_vig_adj      = pick.get("vig_adj_pct")    # AI: vig-stripped fair probability

        if base_odds is not None and true_odds is not None:
            kelly_pct = calculate_kelly_fraction(base_odds, true_odds)
            if kelly_pct > 0.0:
                suggested_units = round((kelly_pct / 2.0) * 4) / 4.0
                suggested_units = max(0.25, min(suggested_units, 5.0))

            if ai_edge_pct is not None:
                edge_pct = float(ai_edge_pct)
            else:
                # Fallback: compute client-side from raw odds if AI didn't return edge fields
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

            # Show probability breakdown if AI returned the new fields
            if ai_true_prob is not None and ai_vig_adj is not None:
                ev_str = f" | EV: :green[+{ai_ev_per_unit:.3f}u]" if ai_ev_per_unit and ai_ev_per_unit > 0 else (
                    f" | EV: :red[{ai_ev_per_unit:.3f}u]" if ai_ev_per_unit else ""
                )
                st.caption(
                    f"True prob: **{ai_true_prob:.1f}%** vs Vig-adj: {ai_vig_adj:.1f}% "
                    f"(Edge: +{edge_pct:.1f}%){ev_str}"
                )
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

