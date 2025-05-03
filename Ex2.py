import pandas as pd
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import re

# Suppress FutureWarning
pd.set_option('future.no_silent_downcasting', True)

# Load data
try:
    df = pd.read_csv("results.csv", encoding='utf-8')
    print("Columns in results.csv:", list(df.columns))
except FileNotFoundError:
    print("Error: results.csv not found.")
    exit(1)

# Clean 'Minutes' column
df['Minutes'] = df['Minutes'].str.replace(',', '').pipe(pd.to_numeric, errors='coerce')

# Define and clean percentage columns
percent_cols = ['Won%', 'Save%', 'Possession_Succ%', 'Possession_Tkld%', 'Pen Save%', 'CS%', 'SoT%']
percent_cols = [col for col in percent_cols if col in df.columns]
if not percent_cols:
    print("Warning: No percent_cols found.")
else:
    print("Processing percent_cols:", percent_cols)
    for col in percent_cols:
        df[col] = (
            df[col]
            .astype(str)
            .replace('N/a', np.nan)
            .str.replace(r'[^\d.]', '', regex=True)
            .pipe(pd.to_numeric, errors='coerce') / 100
        )

# Convert GA90 to numeric
df['GA90'] = pd.to_numeric(df['GA90'], errors='coerce')

# Define stats columns (starting from 'Goals')
stats_columns = df.columns[8:].tolist()
print("Stats columns:", stats_columns)

# Convert stats columns to numeric
for stat in stats_columns:
    df[stat] = pd.to_numeric(df[stat], errors='coerce')

def generate_top_bottom_3():
    try:
        with open('top_3.txt', 'w', encoding='utf-8') as f:
            for stat in stats_columns:
                df[stat] = pd.to_numeric(df[stat], errors='coerce')
                valid_count = df[stat].count()
                
                if valid_count < 3:
                    print(f"Skipping {stat}: Less than 3 valid entries ({valid_count})")
                    continue

                f.write(f"\n{'='*25} {stat.upper()} {'='*25}\n")
                
                # Use 'First Name' instead of 'Player'
                top3 = df[['First Name', 'Team', stat]].nlargest(3, stat)
                f.write("\nTop 3:\n")
                for _, row in top3.iterrows():
                    value = row[stat] if not pd.isna(row[stat]) else 0
                    f.write(f"{row['First Name']} ({row['Team']}): {value:.2f}\n")
                
                bottom3 = df[['First Name', 'Team', stat]].nsmallest(3, stat)
                f.write("\nBottom 3:\n")
                for _, row in bottom3.iterrows():
                    value = row[stat] if not pd.isna(row[stat]) else 0
                    f.write(f"{row['First Name']} ({row['Team']}): {value:.2f}\n")
    except Exception as e:
        print(f"Error in generate_top_bottom_3: {e}")

def calculate_statistics():
    try:
        teams = df['Team'].unique().tolist()
        # Initialize an empty list to collect rows
        results_list = []
        
        for stat in stats_columns:
            stat_data = df[stat]
            if stat_data.count() > 0:
                # Create a dictionary for overall stats
                stat_dict = {
                    'Statistic': [f'Median of {stat}', f'Mean of {stat}', f'Std of {stat}'],
                    'all': [stat_data.median(), stat_data.mean(), stat_data.std()]
                }
                # Add per-team stats
                for team in teams:
                    team_data = df[df['Team'] == team][stat]
                    if team_data.count() > 0:
                        stat_dict[team] = [team_data.median(), team_data.mean(), team_data.std()]
                    else:
                        stat_dict[team] = [np.nan, np.nan, np.nan]
                # Convert to DataFrame and append to list
                results_list.append(pd.DataFrame(stat_dict))
        
        # Concatenate all results at once
        if results_list:
            results = pd.concat(results_list, ignore_index=True)
            results.to_csv('results2.csv', index=False, float_format="%.2f", encoding='utf-8')
        else:
            print("No statistics to calculate.")
    except Exception as e:
        print(f"Error in calculate_statistics: {e}")

def generate_histograms():
    try:
        os.makedirs('histograms', exist_ok=True)
        
        for stat in stats_columns:
            stat_data = df[stat].dropna()
            if not stat_data.empty:
                plt.figure()
                plt.hist(stat_data, bins=20)
                plt.title(f'All Players - {stat}')
                plt.xlabel(stat)
                plt.ylabel('Frequency')
                safe_stat = re.sub(r'[^a-zA-Z0-9]', '_', stat)
                plt.savefig(f'histograms/all_players_{safe_stat}.png', bbox_inches='tight')
                plt.close()
            
            for team in df['Team'].unique():
                safe_team = re.sub(r'[\n<>:"/\\|?*()]', '_', team).replace(' ', '_').strip('_')
                safe_stat = re.sub(r'[^a-zA-Z0-9]', '_', stat)
                team_data = df[df['Team'] == team][stat].dropna()
                if not team_data.empty:
                    plt.figure()
                    plt.hist(team_data, bins=20)
                    plt.title(f'{team} - {stat}')
                    plt.xlabel(stat)
                    plt.ylabel('Frequency')
                    plt.savefig(f'histograms/{safe_team}_{safe_stat}.png', bbox_inches='tight')
                    plt.close()
    except Exception as e:
        print(f"Error in generate_histograms: {e}")

def analyze_data():
    try:
        team_stat = df.groupby('Team')[stats_columns].mean()
        leadership = {}
        leadership_details = []

        for stat in stats_columns:
            if team_stat[stat].count() > 0:
                leader = team_stat[stat].idxmax()
                max_value = team_stat[stat].max()
                leadership[stat] = leader
                leadership_details.append({
                    'Statistic': stat,
                    'Leading Team': leader,
                    'Mean Value': f"{max_value:.2f}"
                })

        leadership_df = pd.DataFrame(leadership_details)
        leadership_df.to_csv('leadership_details.csv', index=False, encoding='utf-8')

        leader_counts = pd.Series(leadership.values()).value_counts()
        leader_counts.to_csv('leadership_counts.csv', encoding='utf-8')

        best_team = leader_counts.idxmax() if not leader_counts.empty else "No team leads"
        best_team_count = leader_counts.max() if not leader_counts.empty else 0

        with open('best_team_analysis.txt', 'w', encoding='utf-8') as f:
            f.write("=== Team Performance Analysis ===\n\n")
            f.write("Teams Leading in Each Statistic:\n")
            for stat, team in leadership.items():
                f.write(f"{stat}: {team} (Mean: {team_stat[stat][team]:.2f})\n")
            f.write("\nLeadership Counts:\n")
            for team, count in leader_counts.items():
                f.write(f"{team}: Leads in {count} statistics\n")
            f.write("\nBest-Performing Team:\n")
            f.write(f"{best_team} leads in {best_team_count} statistics, showing strength across multiple metrics.\n")
    except Exception as e:
        print(f"Error in analyze_data: {e}")

def sanitize_filename(filename):
    invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\r', '\n']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    filename = filename.rstrip('. ')
    return filename

# Run functions
try:
    analyze_data()
    generate_histograms()
    calculate_statistics()
    generate_top_bottom_3()
    print("Script completed successfully.")
except Exception as e:
    print(f"Script failed with error: {e}")
