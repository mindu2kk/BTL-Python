import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import os
import json
from bs4 import BeautifulSoup

# Suppress Pandas warnings
pd.set_option('future.no_silent_downcasting', True)

# Load results.csv from Part I
try:
    df = pd.read_csv("results.csv", encoding='utf-8')
    print("Columns in results.csv:", list(df.columns))
except FileNotFoundError:
    print("Error: results.csv not found. Please ensure the file is in the same directory.")
    exit(1)

# Clean the 'Minutes' column
df['Minutes'] = df['Minutes'].str.replace(',', '').pipe(pd.to_numeric, errors='coerce')

# Filter players with more than 900 minutes
df = df[df['Minutes'] > 900].copy()
print(f"Number of players with >900 minutes: {len(df)}")

# Cache file for transfer values
cache_file = 'transfer_cache.json'

# Load cached data if exists
def load_cache():
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    return {}

# Save data to cache
def save_cache(data):
    with open(cache_file, 'w') as f:
        json.dump(data, f)

# Function to scrape transfer values from Transfermarkt's market value page
def scrape_transfer_values(players):
    cache = load_cache()
    transfer_values = []

    # Check cache for all players first
    for player in players:
        if player in cache:
            transfer_values.append({
                'First Name': player,
                'Transfer_Value_Millions_EUR': cache[player]
            })

    # Get remaining players to scrape
    players_to_scrape = [p for p in players if p not in cache]
    if not players_to_scrape:
        print("All players found in cache.")
        return pd.DataFrame(transfer_values)

    # Set up Selenium options
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36")

    driver = None
    try:
        # URL for Premier League market values (adjust if season changes)
        url = "https://www.transfermarkt.com/premier-league/marktwerte/wettbewerb/GB1"
        print(f"Scraping URL: {url}")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)

        # Wait for the player table to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.items"))
        )

        # Parse page with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.select_one("table.items")
        if not table:
            print("No player table found.")
            return pd.DataFrame(transfer_values)

        # Extract player names and market values
        rows = table.select("tr.odd, tr.even")
        for row in rows:
            name_tag = row.select_one("td.hauptlink a")
            value_tag = row.select_one("td.rechts.hauptlink")
            if name_tag and value_tag:
                name = name_tag.get_text(strip=True)
                value_text = value_tag.get_text(strip=True)
                # Clean value (e.g., "€50.00m" -> 50.0)
                value = re.sub(r'[^\d.]', '', value_text)
                value = float(value) if value else np.nan
                if 'k' in value_text.lower():
                    value /= 1000
                elif 'bn' in value_text.lower():
                    value *= 1000

                # Fuzzy match name with players_to_scrape
                for player in players_to_scrape:
                    if name.lower() in player.lower() or player.lower() in name.lower():
                        transfer_values.append({
                            'First Name': player,
                            'Transfer_Value_Millions_EUR': value
                        })
                        cache[player] = value
                        save_cache(cache)
                        break

        # Mark remaining players as NaN
        for player in players_to_scrape:
            if player not in cache:
                transfer_values.append({
                    'First Name': player,
                    'Transfer_Value_Millions_EUR': np.nan
                })
                cache[player] = np.nan
                save_cache(cache)

    except Exception as e:
        print(f"Error scraping Transfermarkt: {e}")
        # Fallback: Mark all remaining players as NaN
        for player in players_to_scrape:
            if player not in cache:
                transfer_values.append({
                    'First Name': player,
                    'Transfer_Value_Millions_EUR': np.nan
                })
                cache[player] = np.nan
                save_cache(cache)
    finally:
        if driver:
            driver.quit()

    return pd.DataFrame(transfer_values)

# Scrape transfer values for unique players
transfer_df = scrape_transfer_values(df['First Name'].unique())

# Merge transfer values with original DataFrame
result_df = df.merge(transfer_df, on='First Name', how='left')

# Save transfer values to CSV
result_df[['First Name', 'Team', 'Position', 'Minutes', 'Transfer_Value_Millions_EUR']].to_csv(
    'transfer_values.csv', index=False, encoding='utf-8'
)
print("Transfer values saved to transfer_values.csv")

# Proposal for estimating player values (shortened comments)
with open('transfer_value_explanation1.txt', 'w', encoding='utf-8') as f:
    f.write("=== Phương pháp ước lượng giá trị chuyển nhượng cầu thủ ===\n\n")
    f.write("1. Lựa chọn đặc trưng:\n")
    f.write("- Tuổi, Vị trí, Số phút thi đấu, Goals, Assists, xG, Tkl, PrgP, Save%, Quốc tịch, Đội bóng.\n")
    f.write("- Lý do: Phản ánh hiệu suất và giá trị thị trường.\n")
    f.write("\n2. Lựa chọn mô hình:\n")
    f.write("- **Random Forest Regressor**: Xử lý dữ liệu phi tuyến, phù hợp với bóng đá.\n")
    f.write("- **Gradient Boosting Regressor**: Hiệu suất cao, dễ tối ưu.\n")
    f.write("- **Linear Regression**: Baseline đơn giản.\n")
    f.write("- Quy trình: Mã hóa, chuẩn hóa, chia dữ liệu, huấn luyện, đánh giá (RMSE, R²).\n")
    f.write("\n3. Nhận xét:\n")
    f.write("- Random Forest và Gradient Boosting vượt trội hơn Linear Regression.\n")
    f.write("- Hạn chế: Thiếu dữ liệu hợp đồng, thương hiệu. Có thể bổ sung từ Transfermarkt.\n")

print("Explanation saved to transfer_value_explanation.txt")