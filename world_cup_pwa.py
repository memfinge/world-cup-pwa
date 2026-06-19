# world_cup_pwa.py

import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, field_validator
from strenum import StrEnum
from supabase import Client, create_client, PostgrestAPIResponse

# --- 1. INITIAL CONFIGURATION & SETUP ---

# Load environment variables from .env file
load_dotenv()

# Set Streamlit page configuration for a mobile-first experience
st.set_page_config(
    page_title="WC Data Pipeline",
    layout="centered",
    initial_sidebar_state="collapsed",
)

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
        return create_client(supabase_url, supabase_key)
    except KeyError:
        st.error("Supabase credentials not found. Please set SUPABASE_URL and SUPABASE_KEY in your .env file.")
        st.stop()

supabase = get_supabase_client()

# --- 4. CORE APPLICATION LOGIC & PIPELINE ---

def scrape_and_update_match_data():
    """
    Scrapes lineup and odds data from a source, parses it, and updates the database.
    NOTE: This function currently reads from a local HTML file for demonstration.
    To scrape a live website, replace the file reading with requests.get(url).
    """
    scraped_matches = []
    scraped_odds = []
    try:
        # In a real scenario:
        # headers = {'User-Agent': 'Mozilla/5.0 ...'}
        # response = requests.get("https://your-target-lineup-url.com", headers=headers)
        # response.raise_for_status() # Raises an exception for bad status codes
        # soup = BeautifulSoup(response.content, "html.parser")

        # For this stable example, we read from a local file:
        with open("mock_lineups.html", "r") as f:
            soup = BeautifulSoup(f, "html.parser")

        match_containers = soup.find_all('div', class_='match-container')
        if not match_containers:
            st.warning("Scraper ran, but no match containers were found in the source.")
            return

        for container in match_containers:
            match_id = container['data-match-id']
            home_team = container.find('h2', class_='home-team').text.strip()
            away_team = container.find('h2', class_='away-team').text.strip()

            home_lineup_tags = container.select('.home-lineup li')
            away_lineup_tags = container.select('.away-lineup li')

            home_lineup = [li.text.strip() for li in home_lineup_tags]
            away_lineup = [li.text.strip() for li in away_lineup_tags]

            market_tags = container.select('.markets .market')
            for market in market_tags:
                odds_obj = Odds(
                    match_id=match_id,
                    market_type=market['data-type'],
                    selection=market['data-selection'],
                    # Convert odds string like "+105" or "-110" to integer
                    dk_odds=int(market['data-odds'])
                )
                scraped_odds.append(odds_obj)

            match_obj = Match(
                match_id=match_id,
                kickoff_time=datetime.now(timezone.utc), # In a real app, this would be scraped too
                home_team=home_team,
                away_team=away_team,
                lineup_status=LineupStatus.CONFIRMED, # We assume scraped lineups are confirmed
                home_lineup=home_lineup,
                away_lineup=away_lineup
            )
            scraped_matches.append(match_obj)

        if scraped_matches:
            supabase.table("matches").upsert([m.model_dump(mode='json', exclude={'updated_at'}) for m in scraped_matches]).execute()
            st.toast(f"Successfully scraped and updated {len(scraped_matches)} matches.")

        if scraped_odds:
            supabase.table("odds").upsert([o.model_dump(mode='json', exclude={'id', 'updated_at'}) for o in scraped_odds], on_conflict="match_id,market_type,selection").execute()
            st.toast(f"Successfully scraped and updated {len(scraped_odds)} market odds.")

    except FileNotFoundError:
        st.error("`mock_lineups.html` not found. Please create it to run the scraper.")
    except Exception as e:
        st.error(f"An error occurred during scraping: {e}")

def evaluate_tactical_matchups(match: Match) -> Optional[Dict[str, Any]]:
    """
    Simulates an AI context injection to evaluate tactical matchups.
    This function contains the dynamic conviction and valuation rules.
    Each 'if' or 'elif' block represents a specific rule for a matchup.
    """
    # Rule 1: High conviction if a key midfielder is forced to play Center Back.
    # Case Study: Edson Álvarez (a top defensive midfielder) is playing at Center Back.
    # This might create midfield vulnerabilities for Mexico that South Korea's attack can exploit.
    if (
        match.home_team == "Mexico" and
        "Álvarez" in match.home_lineup and
        "Son Heung-min" in match.away_lineup and
        "Lee Kang-in" in match.away_lineup
    ):
        # AI Valuation: The tactical mismatch suggests South Korea has a better chance than odds imply.
        # Let's say our model values South Korea ML closer to +250.
        true_odds = 250
        selection = "South Korea"
        market_type = "Moneyline"
        
        # Fetch live odds to compare against our valuation
        try:
            response: PostgrestAPIResponse = supabase.table("odds").select("dk_odds").eq("match_id", match.match_id).eq("selection", selection).single().execute()
            live_odds = response.data['dk_odds']
            
            # Market Taxation Rule: A market is "taxed" if the live odds are worse (lower) than our valued odds.
            is_taxed = live_odds < true_odds # e.g., live is +220, our model says it should be +250. Bad value (taxed).
            
            return {
                "match_id": match.match_id,
                "selection": selection,
                "market_type": market_type,
                "base_odds": live_odds,
                "is_taxed": is_taxed,
                "rationale": "High conviction on SK ML. Mexico's Edson Álvarez moving to CB weakens their elite midfield shield, which is vulnerable to SK's potent Son/Lee Kang-in attacking duo."
            }
        except Exception:
            # Could not fetch odds for the selection
            return None

    # Rule 2: High conviction on a favorite due to a massive talent gap in a key area.
    # This is just another example of a rule you could add for a different game.
    elif (
        match.home_team == "Brazil" and
        "Neymar" in match.home_lineup and
        "Vinícius Jr." in match.home_lineup
    ):
        # AI Valuation: Brazil's attack is so potent that the market is undervaluing them, even as favorites.
        # Let's say our model values Brazil ML at -150.
        true_odds = -150
        selection = "Brazil"
        market_type = "Moneyline"

        try:
            response: PostgrestAPIResponse = supabase.table("odds").select("dk_odds").eq("match_id", match.match_id).eq("selection", selection).single().execute()
            live_odds = response.data['dk_odds']
            # For negative odds, better odds are closer to zero (e.g., -110 is better than -150).
            # The market is taxed if the live odds are worse (more negative) than our valuation.
            is_taxed = live_odds < true_odds # e.g., live is -180, our model says -150. Bad value (taxed).
            return {
                "match_id": match.match_id,
                "selection": selection,
                "market_type": market_type,
                "base_odds": live_odds,
                "is_taxed": is_taxed,
                "rationale": "High conviction on BRA ML. The attacking talent of Neymar and Vinícius Jr. presents a schematic mismatch for Germany's current defensive line. Model indicates value even at favorite odds."
            }
        except Exception:
            return None
    return None
def get_final_scores() -> Dict[str, str]:
    """
    Scrapes the data source to get final scores for completed matches.
    Returns a dictionary mapping match_id to a score string (e.g., "1-2").
    """
    final_scores = {}
    try:
        with open("mock_lineups.html", "r") as f:
            soup = BeautifulSoup(f, "html.parser")
        
        match_containers = soup.find_all('div', class_='match-container')
        for container in match_containers:
            if container.has_attr('data-final-score'):
                match_id = container['data-match-id']
                score = container['data-final-score']
                final_scores[match_id] = score
        return final_scores
    except Exception:
        # Silently fail if scraping scores fails, as it's a non-critical part of the sync
        return {}

def determine_settlement_status(slip: LedgerEntry, match: Match, final_score_str: str) -> LedgerStatus:
    """
    Determines the outcome of a bet based on the final score.
    """
    try:
        home_score_str, away_score_str = final_score_str.split('-')
        home_score = int(home_score_str)
        away_score = int(away_score_str)

        if slip.market_type == "Moneyline":
            if home_score > away_score:
                winner = match.home_team
            elif away_score > home_score:
                winner = match.away_team
            else:
                winner = "Draw"
            
            return LedgerStatus.WON if slip.selection == winner else LedgerStatus.LOST

        elif slip.market_type == "BTTS": # Both Teams To Score
            is_btts = home_score > 0 and away_score > 0
            if slip.selection == "Yes":
                return LedgerStatus.WON if is_btts else LedgerStatus.LOST
            elif slip.selection == "No":
                return LedgerStatus.WON if not is_btts else LedgerStatus.LOST

        # Add more market type settlement logic here in the future

    except (ValueError, IndexError):
        # If score is malformed, cannot determine status
        return LedgerStatus.PENDING

    return LedgerStatus.PENDING # Default to pending if no logic matches

def audit_pending_ledger() -> None:
    """
    Audits historical 'Pending' records against final scores and settles them.
    """
    st.write("`[Ledger]` Auditing pending slips...")
    try:
        final_scores = get_final_scores()
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

            if final_status in [LedgerStatus.WON, LedgerStatus.LOST]:
                net_return = 0.0
                if final_status == LedgerStatus.WON:
                    if slip.base_odds > 0: net_return = slip.unit_risk * (slip.base_odds / 100.0)
                    else: net_return = slip.unit_risk * (100.0 / abs(slip.base_odds))
                elif final_status == LedgerStatus.LOST:
                    net_return = -slip.unit_risk

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
            # Step 0: Audit ledger first (as per rules)
            status.update(label="Auditing pending ledger entries...")
            audit_pending_ledger()

            # Step 1: Scrape active lineups and update the database
            status.update(label="Scraping live match data...")
            scrape_and_update_match_data()

            # Step 2: Fetch all confirmed matches from DB for evaluation
            status.update(label="Fetching confirmed matches from database...")
            matches_response = supabase.table("matches").select("*").eq("lineup_status", LineupStatus.CONFIRMED).execute()
            all_matches = [Match.model_validate(m) for m in matches_response.data]

            if not all_matches:
                st.session_state.conviction_picks = []
                status.update(label="Sync complete. No confirmed matches found.", state="complete")
                st.warning("No confirmed matches found in the database to evaluate.")
                st.rerun()
                return

            # Step 3: Evaluate tactical matchups for each match
            status.update(label=f"Evaluating {len(all_matches)} match(es)...")
            evaluated_picks = []
            for match in all_matches:
                pick = evaluate_tactical_matchups(match)
                if pick:
                    evaluated_picks.append(pick)
            
            st.session_state.conviction_picks = evaluated_picks

            # Step 4: Render dashboard (handled by main UI flow after this)
            status.update(label="Sync complete. Ready to render UI.", state="complete")
        except Exception as e:
            status.update(label=f"Pipeline failed: {e}", state="error")


# --- 5. USER INTERFACE (Mobile-First Streamlit Components) ---

def render_pin_lock_screen():
    """Displays a PIN lock screen to shield the primary view."""
    st.header("WC Data Pipeline")
    st.write("Enter PIN to access the dashboard.")
    
    app_pin = os.environ.get("APP_PIN", "1234") # Default PIN if not in .env
    pin_input = st.text_input("4-Digit PIN", type="password", max_chars=4, key="pin_input")

    if st.button("Unlock"):
        if pin_input == app_pin:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid PIN.")

def render_main_dashboard():
    """Renders the main application dashboard after successful authentication."""
    st.title("WC Data Dashboard")

    # --- Main Sync Trigger ---
    st.button(
        "Manual Sync Pipeline",
        on_click=execute_sync_pipeline,
        type="primary",
        use_container_width=True,
    )
    st.caption("On-demand trigger: Scrapes lineups, fetches lines, evaluates matchups, and audits ledger.")
    
    st.divider()

    # --- Conviction Picks Display ---
    st.subheader("High-Conviction Targets")
    if 'conviction_picks' not in st.session_state:
        st.info("No data synced yet. Press the sync button to begin.")
    elif not st.session_state.conviction_picks:
        st.success("Sync complete. No high-conviction targets found. Lines appear efficient.")
    else:
        for pick in st.session_state.conviction_picks:
            render_conviction_card(pick)

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
    
    def log_selection():
        """Callback to write the selection to the ledger."""
        try:
            # Construct the dynamic key to retrieve the correct unit risk from session state
            unit_risk_key = f"unit_risk_{pick['match_id']}_{pick['selection']}"
            unit_risk_value = st.session_state.get(unit_risk_key, 1.0)

            new_slip = LedgerEntry(
                slip_id=str(uuid.uuid4()),
                match_id=pick['match_id'],
                selection=pick['selection'],
                base_odds=pick['base_odds'],
                unit_risk=unit_risk_value,
                status=LedgerStatus.PENDING
            )
            supabase.table("ledger").insert(new_slip.model_dump(mode='json', exclude={'net_return', 'created_at'})).execute()
            st.success(f"Logged: {pick['selection']} @ {pick['base_odds']}")
            # Clear picks so we don't log duplicates
            st.session_state.conviction_picks = []
        except Exception as e:
            st.error(f"Failed to log slip: {e}")

    with st.expander(f"🎯 {pick['selection']} ({pick['base_odds']}) - {pick['match_id']}", expanded=True):
        st.markdown("**Rationale:**")
        st.info(pick['rationale'])

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
                value=1.0, 
                step=0.25, 
                key=f"unit_risk_{pick['match_id']}_{pick['selection']}",
                format="%.2f"
            )
        with col2:
            st.button(
                button_text,
                on_click=log_selection,
                use_container_width=True,
                key=f"log_{pick['match_id']}_{pick['selection']}"
            )


# --- 6. MAIN APPLICATION FLOW ---

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if st.session_state.authenticated:
    render_main_dashboard()
else:
    render_pin_lock_screen()
