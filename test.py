import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import concurrent.futures
import time
import json
import os
import re
import logging
from threading import Lock

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

STAT_CATEGORIES = {
    "standard": [
        ("Nation", "nationality"), ("Team", "team"), ("Position", "position"), ("Age", "age"),
        ("Matches Played", "games"), ("Starts", "games_starts"), ("Minutes", "minutes"),
        ("Goals", "goals"), ("Assists", "assists"), ("Yellow Cards", "cards_yellow"),
        ("Red Cards", "cards_red"), ("xG", "xg"), ("xAG", "xg_assist"),
        ("PrgC", "progressive_carries"), ("PrgP", "progressive_passes"), ("PrgR", "progressive_passes_received"),
        ("Gls/90", "goals_per90"), ("Ast/90", "assists_per90"), ("xG/90", "xg_per90"), ("xAG/90", "xg_assist_per90")
    ],
    "keeper": [
        ("GA90", "gk_goals_against_per90"), ("Save%", "gk_save_pct"), ("CS%", "gk_clean_sheets_pct"),
        ("PK Save%", "gk_pens_save_pct")
    ],
    "shooting": [
        ("SoT%", "shots_on_target_pct"), ("SoT/90", "shots_on_target_per90"),
        ("G/Sh", "goals_per_shot"), ("Dist", "average_shot_distance")
    ],
    "passing": [
        ("Cmp", "passes_completed"), ("Cmp%", "passes_pct"), ("TotDist", "passes_total_distance"),
        ("KP", "assisted_shots"), ("1/3", "passes_into_final_third"), ("PPA", "passes_into_penalty_area"),
        ("CrsPA", "crosses_into_penalty_area"), ("PrgP", "progressive_passes"),
        ("Short Cmp%", "passes_pct_short"), ("Medium Cmp%", "passes_pct_medium"), ("Long Cmp%", "passes_pct_long")
    ],
    "gca": [
        ("SCA", "sca"), ("SCA90", "sca_per90"), ("GCA", "gca"), ("GCA90", "gca_per90")
    ],
    "defense": [
        ("Tkl", "tackles"), ("TklW", "tackles_won"), ("Att", "challenges"), ("Lost", "challenges_lost"),
        ("Blocks", "blocks"), ("Sh", "blocked_shots"), ("Pass", "blocked_passes"), ("Int", "interceptions")
    ],
    "possession": [
        ("Touches", "touches"), ("Def Pen", "touches_def_pen_area"), ("Def 3rd", "touches_def_3rd"),
        ("Mid 3rd", "touches_mid_3rd"), ("Att 3rd", "touches_att_3rd"), ("Att Pen", "touches_att_pen_area"),
        ("Att (Take-Ons)", "take_ons"), ("Succ% (Take-Ons)", "take_ons_won_pct"),
        ("Tkld% (Take-Ons)", "take_ons_tackled_pct"), ("Carries", "carries"),
        ("PrgDist", "carries_progressive_distance"), ("ProgC", "progressive_carries"),
        ("1/3 (Carries)", "carries_into_final_third"), ("CPA", "carries_into_penalty_area"),
        ("Mis", "miscontrols"), ("Dis", "dispossessed"), ("Rec", "passes_received"),
        ("PrgR", "progressive_passes_received")
    ],
    "misc": [
        ("Fls", "fouls"), ("Fld", "fouled"), ("Off", "offsides"), ("Crs", "crosses"),
        ("Recov", "ball_recoveries"), ("Won (Aerial)", "aerials_won"),
        ("Lost (Aerial)", "aerials_lost"), ("Won% (Aerial)", "aerials_won_pct")
    ]
}

URLS = {
    "standard": "https://fbref.com/en/comps/9/stats/Premier-League-Stats",
    "keeper": "https://fbref.com/en/comps/9/keepers/Premier-League-Stats",
    "keeper_adv": "https://fbref.com/en/comps/9/keepersadv/Premier-League-Stats",
    "shooting": "https://fbref.com/en/comps/9/shooting/Premier-League-Stats",
    "passing": "https://fbref.com/en/comps/9/passing/Premier-League-Stats",
    "passing_types": "https://fbref.com/en/comps/9/passing_types/Premier-League-Stats",
    "gca": "https://fbref.com/en/comps/9/gca/Premier-League-Stats",
    "defense": "https://fbref.com/en/comps/9/defense/Premier-League-Stats",
    "possession": "https://fbref.com/en/comps/9/possession/Premier-League-Stats",
    "misc": "https://fbref.com/en/comps/9/misc/Premier-League-Stats"
}

TABLE_IDS = {
    "standard": "stats_standard",
    "keeper": "stats_keeper",
    "keeper_adv": "stats_keeper_adv",
    "shooting": "stats_shooting",
    "passing": "stats_passing",
    "passing_types": "stats_passing_types",
    "gca": "stats_gca",
    "defense": "stats_defense",
    "possession": "stats_possession",
    "misc": "stats_misc"
}

CACHE_FILE = "fbref_cache.json"

def get_first_name(full_name):
    if not full_name or not isinstance(full_name, str) or re.match(r'^\d+$', full_name) or not any(c.isalpha() for c in full_name):
        return "Unknown"
    parts = full_name.strip().split()
    return parts[0] if parts else "Unknown"

def parse_minutes(minutes_str):
    try:
        cleaned = str(minutes_str).replace(",", "")
        return int(cleaned) if cleaned.isdigit() else 0
    except (ValueError, AttributeError):
        return 0

def scrape_table(url, table_id, stat_category, max_retries=2):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36")

    for attempt in range(max_retries):
        driver = None
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, table_id)))

            soup = BeautifulSoup(driver.page_source, "html.parser")
            table = soup.find("table", id=table_id)
            if not table:
                logging.error(f"No table found with id {table_id} at {url}")
                return {}

            headers = table.find("thead").find_all("tr")[-1].find_all(["th", "td"])
            stat_to_index = {header.get("data-stat"): idx for idx, header in enumerate(headers) if header.get("data-stat")}

            data = {}
            rows = table.find("tbody").find_all("tr")
            for row in rows:
                player_cell = row.find(["th", "td"], {"data-stat": "player"})
                if not player_cell:
                    continue
                player_name = player_cell.text.strip()
                if not player_name or re.match(r'^\d+$', player_name):
                    continue

                if player_name in data:
                    logging.warning(f"Duplicate player found in {stat_category}: {player_name}")

                data[player_name] = {}
                cells = row.find_all(["th", "td"])
                for stat_name, data_stat in STAT_CATEGORIES[stat_category]:
                    idx = stat_to_index.get(data_stat)
                    if idx is not None and idx < len(cells):
                        value = cells[idx].text.strip()
                        data[player_name][stat_name] = value if value and value != "" else "N/a"
                    else:
                        data[player_name][stat_name] = "N/a"

                if stat_category == "standard":
                    idx = stat_to_index.get("minutes")
                    data[player_name]["Minutes_raw"] = cells[idx].text.strip().replace(",", "") if idx is not None and idx < len(cells) else "N/a"

            return data

        except Exception as e:
            logging.error(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                logging.error(f"Failed to scrape {url} after {max_retries} attempts")
                return {}
        finally:
            if driver:
                driver.quit()

def load_cached_data():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return None

def save_to_cache(data):
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f)

def scrape_all_stats(force_scrape=False):
    if not force_scrape:
        cached_data = load_cached_data()
        if cached_data:
            df = pd.DataFrame.from_dict(cached_data, orient="index")
            df = df.fillna("N/a")
            df = df.replace("", "N/a")
            return df

    all_players_data = {}
    data_lock = Lock()

    def process_table(category):
        table_data = scrape_table(URLS[category], TABLE_IDS[category], category)
        with data_lock:
            for player, stats in table_data.items():
                if player not in all_players_data:
                    all_players_data[player] = {"First Name": get_first_name(player)}
                all_players_data[player].update(stats)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(process_table, URLS.keys())

    # Filter players with > 90 minutes
    filtered_players = {
        player: data for player, data in all_players_data.items()
        if parse_minutes(data.get("Minutes_raw", "0")) > 90
    }

    # Log filtered players count
    logging.info(f"Found {len(filtered_players)} players with > 90 minutes")

    # Define required columns
    required_columns = ["First Name"] + [stat_name for stats in STAT_CATEGORIES.values() for stat_name, _ in stats]

    # Fill missing values with "N/a"
    for player in filtered_players:
        for col in required_columns:
            filtered_players[player][col] = filtered_players[player].get(col, "N/a")

    save_to_cache(filtered_players)
    df = pd.DataFrame.from_dict(filtered_players, orient="index").reset_index(drop=True)
    df = df[required_columns].sort_values(by="First Name").reset_index(drop=True)

    # Ensure no duplicate indices
    if not df.index.is_unique:
        logging.warning("Duplicate indices detected in final DataFrame")
        df = df.drop_duplicates().reset_index(drop=True)

    # Replace any remaining NaN or empty values with "N/a"
    df = df.fillna("N/a")
    df = df.replace("", "N/a")

    return df

if __name__ == "__main__":
    try:
        df = scrape_all_stats(force_scrape=True)
        if df is not None and not df.empty:
            df.to_csv("results.csv", index=False)
            logging.info("Data successfully exported to results.csv")
        else:
            logging.error("No data was scraped or DataFrame is empty")
    except Exception as e:
        logging.error(f"Script failed: {str(e)}")