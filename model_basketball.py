import json
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, accuracy_score
import os

# --- 1. LOAD THE DATA ---
file_path = "assets/data/games.json"

if not os.path.exists(file_path):
    print("Error: games.json not found. Run your scraper first!")
    exit()

with open(file_path, 'r') as f:
    games_data = json.load(f)

# --- 2. FEATURE ENGINEERING (Flattening the JSON) ---
# We need to extract the specific stats we want the model to learn from.
data_rows = []

for game_id, game in games_data.items():
    try:
        ncat_pts = game['ncat_totals'].get('PTS', 0)
        opp_pts = game['opp_totals'].get('PTS', 0)
        
        # Skip if game didn't parse correctly
        if ncat_pts == 0 or opp_pts == 0:
            continue
            
        row = {
            # Target Variables (What we want to predict)
            "ncat_pts": ncat_pts,
            "win": 1 if ncat_pts > opp_pts else 0,  # 1 for Win, 0 for Loss
            
            # Features (The inputs the model will use to guess the target)
            "opp_rebounds": game['opp_totals'].get('REB', 0),
            "opp_turnovers": game['opp_totals'].get('TO', 0),
            "opp_blocks": game['opp_totals'].get('BLK', 0),
            "ncat_paint_pts": game['ncat_summary'].get('inPaint', 0),
            "ncat_fastbreak": game['ncat_summary'].get('fastBreak', 0)
        }
        data_rows.append(row)
    except Exception as e:
        continue

# Convert our list of rows into a Pandas DataFrame (like an Excel sheet)
df = pd.DataFrame(data_rows)
print(f"Successfully loaded {len(df)} games for modeling.\n")

# --- 3. LINEAR REGRESSION (Predicting NC A&T Points) ---
print("--- LINEAR REGRESSION: Predicting NC A&T Total Points ---")

# Define our Inputs (X) and Target (y)
# We are asking the model: "How do these 4 stats affect our total points?"
X_lin = df[['opp_rebounds', 'opp_turnovers', 'ncat_paint_pts', 'ncat_fastbreak']]
y_lin = df['ncat_pts']

# Initialize and train the model
lin_model = LinearRegression()
lin_model.fit(X_lin, y_lin)

# Check the accuracy
predictions = lin_model.predict(X_lin)
error = mean_absolute_error(y_lin, predictions)
print(f"Model Accuracy: On average, the model's guess is off by {round(error, 1)} points.")

# Print the "Weights" (How much each stat matters)
print("Stat Impact on NC A&T Points:")
for feature, weight in zip(X_lin.columns, lin_model.coef_):
    # A positive weight means it adds to our score. Negative means it lowers it.
    print(f"  - {feature}: {round(weight, 2)} pts")


# --- 4. LOGISTIC REGRESSION (Predicting Win/Loss) ---
print("\n--- LOGISTIC REGRESSION: Predicting Win or Loss ---")

# Define our Inputs (X) and Target (y)
X_log = df[['opp_rebounds', 'opp_turnovers', 'ncat_paint_pts', 'ncat_fastbreak']]
y_log = df['win']

# Initialize and train the model
log_model = LogisticRegression()
log_model.fit(X_log, y_log)

# Check the accuracy
win_predictions = log_model.predict(X_log)
accuracy = accuracy_score(y_log, win_predictions)
print(f"Model Accuracy: Correctly predicted the Win/Loss {round(accuracy * 100, 1)}% of the time.")

# Print the "Weights" (How much each stat contributes to winning)
print("Stat Impact on Winning (Positive = Helps win, Negative = Causes loss):")
for feature, weight in zip(X_log.columns, log_model.coef_[0]):
    print(f"  - {feature}: {round(weight, 3)}")

print("\n(Note: This is baseline inference. With only 30 games, the model will learn heavy biases!)")