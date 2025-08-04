import statsapi
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

def get_yesterdays_results():
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    print(f"Fetching MLB results for {yesterday}...")

    games = statsapi.schedule(start_date=yesterday, end_date=yesterday)

    if not games:
        print("No games found for yesterday.")
        return []

    results = []

    for game in games:
        if game['status'] != 'Final':
            continue  # skip postponed/incomplete games
        #print(game)
        game_id = game['game_id']  # this is the gamePk
        home = game['home_name']
        away = game['away_name']
        home_score = game['home_score']
        away_score = game['away_score']
        total_runs = home_score + away_score
        

        # Original ISO 8601 datetime string
        game_time = game['game_datetime']  # e.g., '2025-07-02T16:10:00Z'

        # Parse as UTC datetime
        dt_utc = datetime.strptime(game_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=ZoneInfo("UTC"))

        # Convert to Eastern Time
        dt_est = dt_utc.astimezone(ZoneInfo("America/New_York"))

        # Format date and time strings
        date_str = dt_est.strftime("%m/%d/%Y")   # e.g., '07/02/2025'
        time_str = dt_est.strftime("%I:%M %p")   # e.g., '12:10 PM'

        print(f"{date_str},{time_str},{game_id},{away} @ {home},{total_runs}")
        #total_line is the odds
        #print(f"{BOLD}{date_str},{time_str},{g['game_id']},{a} @ {h},{total_line},{total_score},{verdict2},{prediction},, {END}")


        results.append({
            'game_id': game_id,
            'home_team': home,
            'away_team': away,
            'home_score': home_score,
            'away_score': away_score,
            'total_runs': total_runs
        })

    return results

# Run the function
if __name__ == "__main__":
    get_yesterdays_results()
