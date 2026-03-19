# Import pandas to create our data table and do advanced math (like rolling averages)
import pandas as pd
# Import json to read our scraped games data
import json
# Import os to check if files and folders exist
import os

# --- 1. SETUP AND LOAD DATA ---
input_file = "assets/data/games.json"
output_file = "assets/data/ml_features.csv"

# Check if the games.json file actually exists before trying to open it
if not os.path.exists(input_file):
    print(f"Error: {input_file} not found. Run update_boxscores.py first!")
    exit()

# Open the JSON file and load it into a Python dictionary
with open(input_file, 'r') as f:
    games_data = json.load(f)

print(f"Loaded {len(games_data)} games. Engineering pre-game features...")

# --- 2. FLATTEN THE JSON INTO A SPREADSHEET ---
# We need to extract the raw stats from the nested JSON into a simple list of rows
raw_rows = []

# Loop through every game in the JSON file
for game_id, game in games_data.items():
    try:
        # Grab the total points scored by NC A&T and the Opponent
        ncat_pts = game['ncat_totals'].get('PTS', 0)
        opp_pts = game['opp_totals'].get('PTS', 0)
        
        # If the points are 0, the game probably hasn't been played yet, so skip it
        if ncat_pts == 0 or opp_pts == 0:
            continue
            
        # Create a dictionary representing exactly one game
        row = {
            "game_id": game_id,
            "opponent": game['name'],
            # The Targets (What the ML model will try to predict)
            "target_ncat_pts": ncat_pts,
            "target_win": 1 if ncat_pts > opp_pts else 0, # 1 for a Win, 0 for a Loss
            
            # The Raw Stats for NC A&T
            "ncat_pts": ncat_pts,
            "ncat_reb": game['ncat_totals'].get('REB', 0),
            "ncat_ast": game['ncat_totals'].get('AST', 0),
            "ncat_to": game['ncat_totals'].get('TO', 0),
            "ncat_paint": game['ncat_summary'].get('inPaint', 0)
        }
        # Add this game to our list
        raw_rows.append(row)
    except Exception as e:
        # If a game has broken data, skip it
        continue

# Convert our list of dictionaries into a pandas DataFrame (which works just like an Excel sheet)
df = pd.DataFrame(raw_rows)

# --- 3. FEATURE ENGINEERING (THE MAGIC) ---
# We use .shift(1) to tell pandas: "Look at the PREVIOUS game, not the current game."
# We use .rolling(3) to tell pandas: "Average the last 3 games together."

# Calculate NC A&T's average points over their last 3 games BEFORE today
df['pregame_rolling_pts'] = df['ncat_pts'].shift(1).rolling(window=3).mean()

# Calculate NC A&T's average rebounds over their last 3 games BEFORE today
df['pregame_rolling_reb'] = df['ncat_reb'].shift(1).rolling(window=3).mean()

# Calculate NC A&T's average turnovers over their last 3 games BEFORE today
df['pregame_rolling_to'] = df['ncat_to'].shift(1).rolling(window=3).mean()

# Calculate NC A&T's average points in the paint over their last 3 games BEFORE today
df['pregame_rolling_paint'] = df['ncat_paint'].shift(1).rolling(window=3).mean()

# Calculate "Win Streak": The sum of wins over the last 3 games (0 = Cold, 3 = Hot streak)
df['pregame_win_streak'] = df['target_win'].shift(1).rolling(window=3).sum()


# --- 4. CLEANUP AND EXPORT ---
# The first 3 games of the season won't have a "Last 3 Games" average (they will be blank/NaN).
# Machine learning models crash if they see blank data, so we drop those first 3 rows.
df = df.dropna()

# We don't want the ML model cheating by looking at the raw stats of the current game,
# so we delete the raw stat columns and ONLY keep our Targets and our Pregame Features.
ml_dataframe = df[[
    'game_id', 'opponent', 
    'target_win', 'target_ncat_pts',  # Targets to predict
    'pregame_rolling_pts', 'pregame_rolling_reb', 'pregame_rolling_to', 
    'pregame_rolling_paint', 'pregame_win_streak' # Pre-game inputs
]]

# Ensure the output directory exists
os.makedirs(os.path.dirname(output_file), exist_ok=True)

# Save our engineered dataframe as a CSV file (which is the preferred format for scikit-learn ML models)
ml_dataframe.to_csv(output_file, index=False)

print(f"Success! Engineered features saved to {output_file}.")
print(f"Total games ready for Machine Learning: {len(ml_dataframe)}")
print("\nPreview of the data the ML model will see:")
print(ml_dataframe.head())