import pandas as pd
import numpy as np
import os
import matplotlib
# Use a non-interactive backend to avoid Tkinter issues
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import re

# Suppress the FutureWarning by opting into the future behavior
pd.set_option('future.no_silent_downcasting', True)

# Load the data with the same encoding as the first script
try:
    df = pd.read_csv("results.csv", encoding='utf-8')
    print("Columns in results.csv:", list(df.columns))  # Debug: Print column names
except FileNotFoundError:
    print("Error: results.csv not found. Please ensure the file is in the same directory.")
    exit(1)

# Clean the 'Minutes' column by removing commas and converting to numeric
df['Minutes'] = df['Minutes'].str.replace(',', '').pipe(pd.to_numeric, errors='coerce')

# Define percentage columns based on results.csv
percent_cols = ['Won%', 'Save%', 'Possession_Succ%', 'Possession_Tkld%', 'Pen Save%', 'CS%', 'SoT%']
# Filter out columns that don't exist in the DataFrame
percent_cols = [col for col in percent_cols if col in df.columns]
if not percent_cols:
    print("Warning: None of the specified percent_cols exist in the DataFrame.")
else:
    print("Processing percent_cols:", percent_cols)
for col in percent_cols:
    # Ensure the column is treated as string before using .str
    df[col] = (
        df[col]
        .astype(str)  # Convert to string to allow .str operations
        .replace('N/a', np.nan)
        .str.replace(r'[^\d.]', '', regex=True)
        .pipe(pd.to_numeric, errors='coerce')  # Convert to numeric after cleaning
        / 100
    )

# Convert GA90 to numeric
df['GA90'] = pd.to_numeric(df['GA90'], errors='coerce')

# Define stats columns based on results.csv structure
# Non-stats columns: Player, Nation, Team, Position, Age, Match played, Starts, Minutes
# Stats start from 'Goals' (index 8)
stats_columns = df.columns[8:].tolist()
print("Stats columns:", stats_columns)  # Debug: Print stats columns

# Convert all stats columns to numeric, handling "N/a"
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
                
                # Use 'Player' and 'Team' to match results.csv column names
                top3 = df[['Player', 'Team', stat]].nlargest(3, stat)
                f.write("\nTop 3:\n")
                for _, row in top3.iterrows():
                    value = row[stat] if not pd.isna(row[stat]) else 0
                    f.write(f"{row['Player']} ({row['Team']}): {value:.2f}\n")
                
                bottom3 = df[['Player', 'Team', stat]].nsmallest(3, stat)
                f.write("\nBottom 3:\n")
                for _, row in bottom3.iterrows():
                    value = row[stat] if not pd.isna(row[stat]) else 0
                    f.write(f"{row['Player']} ({row['Team']}): {value:.2f}\n")
    except Exception as e:
        print(f"Error in generate_top_bottom_3: {e}")

def calculate_statistics():
    try:
        teams = df['Team'].unique().tolist()
        results = pd.DataFrame(columns=['Statistic'] + teams + ['all'])
        
        for stat in stats_columns:
            # Calculate overall stats
            stat_data = df[stat]
            if stat_data.count() > 0:  # Only proceed if there are non-NaN values
                results = pd.concat([
                    results,
                    pd.DataFrame({
                        'Statistic': [f'Median of {stat}', f'Mean of {stat}', f'Std of {stat}'],
                        'all': [stat_data.median(), stat_data.mean(), stat_data.std()]
                    })
                ])
            
            # Calculate per-team stats
            for team in teams:
                team_data = df[df['Team'] == team][stat]
                if team_data.count() > 0:  # Only calculate if there are non-NaN values
                    results.loc[results['Statistic'] == f'Median of {stat}', team] = team_data.median()
                    results.loc[results['Statistic'] == f'Mean of {stat}', team] = team_data.mean()
                    results.loc[results['Statistic'] == f'Std of {stat}', team] = team_data.std()
                else:
                    # Fill with NaN if no valid data
                    results.loc[results['Statistic'] == f'Median of {stat}', team] = np.nan
                    results.loc[results['Statistic'] == f'Mean of {stat}', team] = np.nan
                    results.loc[results['Statistic'] == f'Std of {stat}', team] = np.nan

        results.to_csv('results2.csv', index=False, float_format="%.2f", encoding='utf-8')
    except Exception as e:
        print(f"Error in calculate_statistics: {e}")

def generate_histograms():
    try:
        os.makedirs('histograms', exist_ok=True)
        
        for stat in stats_columns:
            # Overall histogram for all players
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
            
            # Team-specific histograms
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
                    safe_filename = f'histograms/{safe_team}_{safe_stat}.png'
                    plt.savefig(safe_filename, bbox_inches='tight')
                    plt.close()
    except Exception as e:
        print(f"Error in generate_histograms: {e}")

def analyze_data():
    try:
        # Calculate mean stats per team
        team_stat = df.groupby('Team')[stats_columns].mean()
        leadership = {}
        leadership_details = []

        # Identify the team with the highest mean score for each statistic
        for stat in stats_columns:
            if team_stat[stat].count() > 0:  # Only proceed if there are non-NaN values
                leader = team_stat[stat].idxmax()
                max_value = team_stat[stat].max()
                leadership[stat] = leader
                leadership_details.append({
                    'Statistic': stat,
                    'Leading Team': leader,
                    'Mean Value': f"{max_value:.2f}"
                })

        # Save leadership details to a CSV file
        leadership_df = pd.DataFrame(leadership_details)
        leadership_df.to_csv('leadership_details.csv', index=False, encoding='utf-8')

        # Count how many times each team leads in a statistic
        leader_counts = pd.Series(leadership.values()).value_counts()
        leader_counts.to_csv('leadership_counts.csv', encoding='utf-8')

        # Determine the best-performing team
        best_team = leader_counts.idxmax() if not leader_counts.empty else "No team leads in any stat"
        best_team_count = leader_counts.max() if not leader_counts.empty else 0

        # Write analysis to a text file
        with open('best_team_analysis.txt', 'w', encoding='utf-8') as f:
            f.write("=== Team Performance Analysis ===\n\n")
            f.write("Teams Leading in Each Statistic:\n")
            for stat, team in leadership.items():
                f.write(f"{stat}: {team} (Mean: {team_stat[stat][team]:.2f})\n")
            f.write("\nLeadership Counts:\n")
            for team, count in leader_counts.items():
                f.write(f"{team}: Leads in {count} statistics\n")
            f.write("\nBest-Performing Team Analysis:\n")
            f.write(f"Based on the analysis, {best_team} is considered the best-performing team in the 2024-2025 Premier League season.\n")
            f.write(f"This team leads in {best_team_count} out of {len(stats_columns)} statistics, indicating strong performance across multiple aspects of the game, such as goals, assists, defensive actions, and possession metrics.\n")
            f.write("This analysis is based on mean statistics per team, which reflects the overall contribution of players with more than 90 minutes of playtime.\n")

    except Exception as e:
        print(f"Error in analyze_data: {e}")

def sanitize_filename(filename):
    invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\r', '\n']
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    filename = filename.rstrip('. ')
    return filename

# Run functions with error handling
try:
    analyze_data()
    generate_histograms()
    calculate_statistics()
    generate_top_bottom_3()
    print("Script completed successfully.")
except Exception as e:
    print(f"Script failed with error: {e}")