# Import requests to download the webpage data from the internet
import requests
# Import BeautifulSoup to search through the downloaded HTML code for links and text
from bs4 import BeautifulSoup
# Import pandas to convert HTML tables into easy-to-read data structures
import pandas as pd
# Import json to save our final formatted data into a file
import json
# Import os to interact with your computer's folder system (to save the file)
import os
# Import re (Regular Expressions) to hunt for specific number patterns in raw text
import re
# Import StringIO to safely pass HTML text into pandas without triggering warnings
from io import StringIO

# --- 1. SETUP VARIABLES ---

# The URL of the main schedule page, where we will find all the box score links
schedule_url = "https://ncataggies.com/sports/mens-basketball/schedule/2025-26"
# The base URL of the website, used to fix broken or incomplete links
base_site_url = "https://ncataggies.com"
# The path and filename where we want to save our final JSON data
output_file = "assets/data/games.json"

# A list of specific NC A&T players. The script uses this to identify which table is ours.
aggie_roster_names = ["Walker, Lureon", "Walker, Lewis", "Debrick, KJ", "Middleton", "Weluche-Ume", "Ogletree"]

# A helper function that takes a messy name string, splits it, and rejoins it with single spaces
def clean_name(name):
    return " ".join(str(name).split())

# Start a try-except block so the script prints an error instead of crashing silently if something breaks
try:
    # Print a status message to the terminal so we know the crawler started
    print(f"Crawling schedule page to find Box Score links...")
    # Create a User-Agent header so the website thinks we are a normal Chrome/Firefox browser
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # --- 2. THE CRAWLER (FINDING THE GAMES) ---
    
    # Download the HTML of the main schedule page
    schedule_response = requests.get(schedule_url, headers=headers)
    # Feed the downloaded HTML into BeautifulSoup so we can easily search it
    soup = BeautifulSoup(schedule_response.text, 'html.parser')
    
    # Create an empty list that will hold all the individual game URLs
    boxscore_urls = []
    # Loop through every single hyperlink (<a> tag) found on the schedule page
    for link in soup.find_all('a', href=True):
        # Extract the actual URL destination from the link
        href = link['href']
        # If the URL contains the word 'boxscore', it's exactly what we are looking for
        if 'boxscore' in href:
            # If the link is relative (starts with '/'), attach the base website URL to the front of it
            full_url = base_site_url + href if href.startswith('/') else href
            # Make sure we don't accidentally add the exact same game twice
            if full_url not in boxscore_urls:
                # Add the valid, unique game URL to our list
                boxscore_urls.append(full_url)
                
    # Print how many games the crawler successfully found
    print(f"Found {len(boxscore_urls)} completed games. Starting extraction...")

    # --- 3. SCRAPING EACH INDIVIDUAL GAME ---
    
    # Create a master dictionary to hold all the data we are about to scrape
    games_dataset = {}

    # Start a loop to visit every single game URL we found, one at a time
    for index, game_url in enumerate(boxscore_urls):
        # Print which game we are currently scraping to the terminal
        print(f"Scraping Game {index + 1}: {game_url}")
        
        # Download the HTML for this specific game's box score
        game_response = requests.get(game_url, headers=headers)
        # Parse the game's HTML with BeautifulSoup
        game_soup = BeautifulSoup(game_response.text, 'html.parser')
        
        # --- TITLE CLEANER (Extracting the Opponent's Name) ---
        
        # Try to find the title tag of the webpage; if missing, just use "Game X"
        page_title = game_soup.title.string if game_soup.title else f"Game {index+1}"
        # Remove generic words like "Box Score" and "Men's Basketball" from the title
        clean_title = page_title.replace("Box Score", "").replace("Men's Basketball", "").replace(" - ", "").strip()
        
        # Create a variable to figure out how the title splits the two team names
        split_word = None
        # Check if they use " vs. ", " vs ", or " at " to separate the teams
        if " vs. " in clean_title: split_word = " vs. "
        elif " vs " in clean_title: split_word = " vs "
        elif " at " in clean_title: split_word = " at "
        
        # If we successfully found a separator word
        if split_word:
            # Split the title into an array of two team names
            teams = clean_title.split(split_word)
            # If the first name is NC A&T, then the opponent must be the second name
            if "A&T" in teams[0] or "Aggies" in teams[0] or "North Carolina" in teams[0]:
                opponent_name = teams[1].strip()
            # Otherwise, the opponent is the first name
            else:
                opponent_name = teams[0].strip()
        # If we couldn't find a separator, just use the cleaned title as a fallback
        else:
            opponent_name = clean_title
            
        # --- HTML TABLE PARSING ---
        
        # Feed the entire HTML page into pandas, which extracts every single <table> it finds
        tables = pd.read_html(StringIO(game_response.text))
        
        # Create blank variables to hold the specific tables we want to find
        ncat_table = None
        opp_table = None
        # Track the order of the tables (used to determine Home vs Away)
        ncat_idx = 999
        opp_idx = 999
        # Create an empty list to hold the First Half/Second Half summary tables
        half_tables = []
        
        # Loop through every table that pandas found on the page
        for idx, df in enumerate(tables):
            # If the table has a double-stacked header, flatten it into a single row
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [str(c[1]).strip() if "Unnamed" not in str(c[1]) else str(c[0]).strip() for c in df.columns]
                
            # If the table contains a 'Player' column, it is a main roster stat table
            if "Player" in df.columns:
                # Combine the first 5 player names into a single string to check who they are
                first_players = " ".join(df['Player'].head(5).astype(str))
                # If any NC A&T player is in that string, this is our table!
                if any(aggie in first_players for aggie in aggie_roster_names):
                    ncat_table = df
                    ncat_idx = idx # Save the position where we found it
                # If it's a player table but DOESN'T have our guys, it must be the opponent's table!
                elif "PTS" in df.columns or "MIN" in df.columns:
                    # Only grab the very first opponent table we see (ignores duplicates)
                    if opp_table is None: 
                        opp_table = df
                        opp_idx = idx # Save the position where we found it
            
            # THE NEW FIX: Look for the First Half / Second Half tables
            try:
                # Look at the very first column of the table. If any row says "First Half", save this table!
                if df.iloc[:, 0].astype(str).str.contains("First Half", case=False).any():
                    half_tables.append(df)
            except:
                # If looking at the first column causes an error (e.g. empty table), just ignore it
                pass
                    
        # If we went through all the tables and never found NC A&T, print a warning and skip the game
        if ncat_table is None:
            print("  -> Could not identify NC A&T player table. Skipping.")
            continue

        # --- HELPER FUNCTION: PARSE THE PLAYER TABLES ---
        
        # A function to extract stats from whichever team table we pass into it
        def parse_team_table(team_df):
            # Create an empty list for individual players
            players_list = []
            # Create an empty dictionary for the team's total stats
            team_totals = {}
            # Loop through every row in the dataframe
            for _, row in team_df.iterrows():
                # Get the player's name from the row
                p_name = str(row.get('Player', '')).strip()
                # Skip empty rows or rows that just say "Team"
                if p_name == "nan" or p_name == "Team": continue
                    
                # A bulletproof inner-function to safely grab numbers, ignoring weird characters
                def get_val(key):
                    val = str(row.get(key, '0')).strip()
                    # If minutes are formatted like "15:30", split it and just keep the "15"
                    if ':' in val: val = val.split(':')[0]
                    # Force the value to become a number
                    num = pd.to_numeric(val, errors='coerce')
                    # Return 0 if it failed, otherwise return the integer
                    return 0 if pd.isna(num) else int(num)

                # Check if assists are labeled 'A' or 'AST' and grab the correct one
                ast_val = get_val('A') if 'A' in row else get_val('AST')

                # Build the final dictionary of stats for this row
                stats_obj = {
                    "Player": clean_name(p_name),
                    "MIN": get_val('MIN'),
                    "PTS": get_val('PTS'),
                    "REB": get_val('REB'),
                    "AST": ast_val,    
                    "STL": get_val('STL'),
                    "BLK": get_val('BLK'),
                    "TO":  get_val('TO'),
                    "PF":  get_val('PF')
                }

                # If the row is the bottom "Totals" row, save it to the team_totals dictionary
                if "Totals" in p_name:
                    team_totals = stats_obj
                # Otherwise, if the player actually played minutes, save them to the player list
                elif stats_obj["MIN"] > 0:
                    players_list.append(stats_obj)
            # Return both variables
            return players_list, team_totals

        # Run our helper function on the NC A&T table
        ncat_players, ncat_totals = parse_team_table(ncat_table)
        # Run our helper function on the opponent's table (if it exists)
        opp_players, opp_totals = parse_team_table(opp_table) if opp_table is not None else ([], {})

        # --- HELPER FUNCTION: PARSE THE FIRST/SECOND HALF TABLES ---
        
        # A function to pull the FG, 3PT, and FT splits out of the summary tables
        def get_half_stats(half_df):
            # Create a blank structure to hold the strings
            stats = {
                "first_half": {"FG": "0-0", "3PT": "0-0", "FT": "0-0"},
                "second_half": {"FG": "0-0", "3PT": "0-0", "FT": "0-0"}
            }
            try:
                # Loop through the rows of the summary table
                for _, row in half_df.iterrows():
                    # Look at the text in the first column
                    col0 = str(row.iloc[0]).strip()
                    # If this is the First Half row, grab columns 1, 2, and 3
                    if "First Half" in col0:
                        stats["first_half"] = {"FG": str(row.iloc[1]), "3PT": str(row.iloc[2]), "FT": str(row.iloc[3])}
                    # If this is the Second Half row, grab columns 1, 2, and 3
                    elif "Second Half" in col0:
                        stats["second_half"] = {"FG": str(row.iloc[1]), "3PT": str(row.iloc[2]), "FT": str(row.iloc[3])}
            except:
                pass # If it fails, just return the 0-0 defaults
            return stats

        # Determine which table belongs to which team based on their order on the page
        ncat_is_first = ncat_idx < opp_idx
        ncat_sum_idx = 0 if ncat_is_first else 1
        opp_sum_idx  = 1 if ncat_is_first else 0
        
        # Create empty variables for the half stats
        ncat_half_stats = {"first_half": {}, "second_half": {}}
        opp_half_stats = {"first_half": {}, "second_half": {}}
        
        # Boxscores should have 2 summary tables (one for each team). If they do, extract them!
        if len(half_tables) >= 2:
            ncat_half_stats = get_half_stats(half_tables[ncat_sum_idx])
            opp_half_stats = get_half_stats(half_tables[opp_sum_idx])

        # --- TEXT PARSING (Points in Paint, Fast Break, etc.) ---
        
        # Strip all HTML tags to create a massive block of raw, readable text
        plain_text = game_soup.get_text(separator=' ')
        
        # Use Regular Expressions (Regex) to find numbers hiding directly after specific phrases.
        # It will find a list of two numbers (e.g., [Away Team Paint Points, Home Team Paint Points])
        in_paint = [int(m) for m in re.findall(r"Points in the Paint:?\s*(\d+)", plain_text, re.IGNORECASE)]
        fast_break = [int(m) for m in re.findall(r"Fast Break Points:?\s*(\d+)", plain_text, re.IGNORECASE)]
        off_to = [int(m) for m in re.findall(r"Points off Turnovers:?\s*(\d+)", plain_text, re.IGNORECASE)]
        bench = [int(m) for m in re.findall(r"Bench Points:?\s*(\d+)", plain_text, re.IGNORECASE)]
        second_chance = [int(m) for m in re.findall(r"Second Chance Points:?\s*(\d+)", plain_text, re.IGNORECASE)]
        
        # A function to safely build the summary dictionary depending on if the team was Away (0) or Home (1)
        def build_summary(target_idx, half_stats):
            return {
                # Grab the number if it exists, otherwise default to 0
                "inPaint": in_paint[target_idx] if len(in_paint) > target_idx else 0,
                "fastBreak": fast_break[target_idx] if len(fast_break) > target_idx else 0,
                "offTurnovers": off_to[target_idx] if len(off_to) > target_idx else 0,
                "bench": bench[target_idx] if len(bench) > target_idx else 0,
                "secondChance": second_chance[target_idx] if len(second_chance) > target_idx else 0,
                # Add the first/second half shooting splits we scraped earlier
                "halves": half_stats
            }

        # Build the final summary blocks for both teams
        ncat_summary = build_summary(ncat_sum_idx, ncat_half_stats)
        opp_summary = build_summary(opp_sum_idx, opp_half_stats)

        # --- SAVE TO MASTER DATASET ---
        
        # Create a unique key for this game (e.g., 'game_1')
        game_key = f"game_{index + 1}"
        # Build the massive, nested JSON object containing every single stat we scraped
        games_dataset[game_key] = {
            "name": opponent_name,
            "ncat_players": ncat_players,
            "ncat_totals": ncat_totals,
            "ncat_summary": ncat_summary,
            "opp_players": opp_players,
            "opp_totals": opp_totals,
            "opp_summary": opp_summary,
            # List the stat keys so the dashboard knows which buttons to create
            "stats": ["PTS", "REB", "AST", "MIN", "STL", "BLK", "TO"]
        }

    # --- 4. EXPORT TO JSON ---
    
    # Check if the folder exists, create it if it doesn't
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    # Open the output file in write mode ('w')
    with open(output_file, 'w') as f:
        # Convert our massive Python dictionary into nicely formatted JSON
        json.dump(games_dataset, f, indent=4)

    # Print a final success message
    print(f"\nSuccess! Scraped {len(games_dataset)} games into {output_file}.")

# If the script fails, print the exact error message
except Exception as e:
    print(f"Crawler encountered an error: {e}")