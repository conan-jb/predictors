# mlb_over_under_predictor_full_with_bullpen.py

import statsapi
import requests
import requests_cache
from zoneinfo import ZoneInfo
from dateutil import parser as dt_parser
from datetime import datetime, timedelta, timezone
import argparse
import math
from config import app_config, keys_config
from db.createtables import create_tables
from db.inserts import insert_or_update_prediction, close_out_game, insert_or_update_mlb_games, buildRecord, insert_pitcher
from db.queries import get_prediction, get_pitcher_id

def calc_wind_score(win_direction, wind_speed, park, humidity):
    park_angle = app_config['PARK_DIRECTIONS'].get(park, 0)
    relative = (win_direction - park_angle + 360) % 360

    #print(f"Wind Direction: {win_direction}° | Park Direction: {park_angle}° | Relative: {relative}°")

    # Normalize to -1 to 1 using cosine
    wind_alignment = math.cos(math.radians(relative))

    # Scale by wind speed (e.g., 10 mph wind is full effect, <5 = mild impact)
    scaled_effect = wind_alignment * min(wind_speed / 10, 1.0)

    # Optional: adjust by humidity (drier air = more carry, so add slight boost)
    humidity_factor = (100 - humidity) / 100  # drier = higher factor
    adjusted_score = scaled_effect * (1 + 0.1 * humidity_factor)

    # Clip final result between -1 and 1
    adjusted_score = max(-1, min(1, adjusted_score))

    #print(f"Wind Score: {adjusted_score:.2f} (tailwind +, headwind -)")
    
    return adjusted_score

#return LINEUP_FACTORS.get(team_name, 0.75)  # default average
def get_category_score(category,pts) :
    match category :
        case "pitcher_era" :
            return pts > app_config["THRESHOLD_PITCHER_ERA"]
        case "recent_er" :
            return pts >= app_config["THRESHOLD_RECENT_ER"]  #if the sum of the last 2 games for this pitcher is >=6 then add a point, that means if they average
        case "bullpen_era" :
            return pts > app_config["THRESHOLD_BULLPEN_ERA"]
        case "runs_per_game" :
            return pts > app_config["THRESHOLD_RUNS_PER_GAME"]
        case "temp" :
            return pts > app_config["THRESHOLD_TEMP"]
        case "wind" :
            return pts >= app_config["THRESHOLD_WIND"]
        case "hitters_park" :
            return pts
        case "line_up" :
            return pts
        case "hitters_park_scaled" :
            return round((pts - 1) * app_config["THRESHOLD_HITTERS_PARK"],2)
        case "line_up_scaled" :
            return round(pts * app_config["THRESHOLD_LINEUP"],2)
        case "wind_park_factor" :
            return round(pts * app_config["THRESHOLD_WIND_PARK_FACTOR"],2)  #Scale up so that wind/humidty, direction have more of an impact.  
        case _:
            return 0

# Scoring logic
def calc_over_score(pitcher_era, recent_er, bullpen_era, runs_per_game,
                    temp, wind, hitters_park, line_up, wind_park_factor):
    inputs = [
        ("pitcher_era", pitcher_era),
        ("recent_er", recent_er),
        ("bullpen_era", bullpen_era),
        ("runs_per_game", runs_per_game),
        ("temp", temp),
        ("wind", wind),
        ("hitters_park", hitters_park),
        ("line_up", line_up),
        ("hitters_park_scaled", hitters_park),
        ("line_up_scaled", line_up),
        ("wind_park_factor", wind_park_factor)
    ]

    score = sum(get_category_score(category, value) for category, value in inputs)
    return round(score, 1)

def get_weight_points(pitcher_era, recent_er, bullpen_era, runs_per_game,
                      temp, wind, hitters_park, line_up, wind_park_factor):
    inputs = [
        ("pitcher_era", pitcher_era),
        ("recent_er", recent_er),
        ("bullpen_era", bullpen_era),
        ("runs_per_game", runs_per_game),
        ("temp", temp),
        ("wind", wind),
        ("hitters_park", hitters_park),
        ("line_up", line_up),
        ("hitters_park_scaled", hitters_park),
        ("line_up_scaled", line_up),
        ("wind_park_factor", wind_park_factor) 
    ]

    return { category: get_category_score(category, value) for category, value in inputs}

def get_team_recent_offense_OLD(team_name):
    tid = statsapi.lookup_team(team_name)[0]['id']
    start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    games = statsapi.schedule(team=tid, start_date=start_date, end_date=datetime.today().strftime('%Y-%m-%d'))
    recent = games[:5]
    return sum(
    int(g['home_score']) if g['home_name'] == team_name else int(g['away_score'])
    for g in recent
) / (len(recent) or 1)


def get_team_recent_offense(team_name):
    tid = statsapi.lookup_team(team_name)[0]['id']
    start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    end_date = datetime.today().strftime('%Y-%m-%d')
    
    games = statsapi.schedule(team=tid, start_date=start_date, end_date=end_date)
    recent = games[:5]

    runs = 0
    total_ab = 0
    total_hits = 0
    total_bb = 0
    total_tb = 0
    total_sf = 0

    for g in recent:
        game_id = g['game_id']
        box = statsapi.boxscore_data(game_id)
        
        # Determine if team is home or away
        team_side = 'home' if box['home']['team'] == tid else 'away'
        hitters = box[team_side]['players']
        for player_id, pdata in hitters.items():
            stats = pdata['stats'].get('batting', {})
            ab = stats.get('atBats', 0)
            h = stats.get('hits', 0)
            bb = stats.get('baseOnBalls', 0)
            sf = stats.get('sacFlies', 0)
            doubles = stats.get('doubles', 0)
            triples = stats.get('triples', 0)
            hr = stats.get('homeRuns', 0)

            singles = h - doubles - triples - hr
            tb = (1 * singles) + (2 * doubles) + (3 * triples) + (4 * hr)

            total_ab += ab
            total_hits += h
            total_bb += bb
            total_tb += tb
            total_sf += sf
        
        runs += int(g['home_score']) if g['home_name'] == team_name else int(g['away_score'])

    num_games = len(recent) or 1
    avg_runs = runs / num_games

    obp = (total_hits + total_bb) / (total_ab + total_bb + total_sf) if (total_ab + total_bb + total_sf) > 0 else 0
    slg = total_tb / total_ab if total_ab > 0 else 0

    # wRC+ approximation placeholder — accurate version requires league avg and park factors
    wrc_plus = round((obp + slg) * 100, 1)

    return {
        'avg_runs': round(avg_runs, 2),
        'OBP': round(obp, 3),
        'SLG': round(slg, 3),
        'WRC': wrc_plus
    }

def get_team_pitching_data(team_name):
    tid = statsapi.lookup_team(team_name)[0]['id']
    url = f"https://statsapi.mlb.com/api/v1/teams/{tid}/stats"
    params = {
        "season": datetime.now().year,
        "stats": "season",
        "group": "pitching"
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    
    data = r.json()
    #print(data)
    return data

def get_bullpen_era(team_name):
    try:
        data = get_team_pitching_data(team_name)

        splits = data["stats"][0]["splits"]
        if not splits:
            if SHOW_ERRORS : print(f"    No pitching splits for team {team_name}")
            return 4.2
        
        bullpen_era = None
        
        for split in splits:
            bullpen_era = float(split.get("stat", {}).get("era", 4.2))
            break
        
        if bullpen_era is None:
            bullpen_era = float(splits[0].get("stat", {}).get("era", 4.2))
        
        return bullpen_era
    except Exception as e:
        if SHOW_ERRORS : print(f"    Error fetching bullpen ERA for {team_name}: {e}")
        return 4.2

def get_weather_for_team(team_name, gt):
    city = app_config['TEAM_TO_CITY'].get(team_name,None)
    if not city:
        if SHOW_ERRORS : print(f"    No city mapping for team {team_name}, using default city 'New York'")
        city = "New York"
    return get_weather(city,gt)


def get_weather(city, game_time):
    weather_key = keys_config['WEATHER_API_KEY']
    weather_url = app_config['WEATHER_API_URL_2']

    # Step 1: Get coordinates for the city
    geo_resp = requests.get(
        f"http://api.openweathermap.org/geo/1.0/direct",
        params={'q': city, 'limit': 1, 'appid': weather_key}
    )
    geo_resp.raise_for_status()
    geo_data = geo_resp.json()

    if not geo_data:
        raise ValueError(f"City '{city}' not found.")

    lat = geo_data[0]['lat']
    lon = geo_data[0]['lon']

    # Step 2: Get hourly forecast
    forecast_resp = requests.get(
        f"{weather_url}/onecall",
        params={
            'lat': lat,
            'lon': lon,
            'appid': weather_key,
            'exclude': 'minutely,daily,alerts,current',
            'units': 'imperial'
        }
    )

    forecast_resp.raise_for_status()
    forecast_data = forecast_resp.json()
    
    # Parse string to datetime
    game_time_dt = dt_parser.parse(game_time)
    # Convert to UTC timestamp
    target_timestamp = int(game_time_dt.astimezone(timezone.utc).timestamp())

    closest_hour = min(
        forecast_data['hourly'],
        key=lambda h: abs(h['dt'] - target_timestamp)
    )

    # Extract desired weather data
    temp = closest_hour['temp']
    wind_speed = closest_hour['wind_speed']
    wind_deg = closest_hour.get('wind_deg', 0)
    humidity = closest_hour['humidity']

    return temp, wind_speed, wind_deg, humidity

def get_games(game_dates):
    if SHOW_PROC_DETAILS : print(f"Getting games for {game_dates}")
    if not game_dates : return

    startDate = game_dates[0]
    endDate = startDate

    if len(game_dates) > 1:
        endDate = game_dates[-1]
    
    if SHOW_PROC_DETAILS : print(f"Date range: {startDate} to {endDate}")
    
    sched = statsapi.schedule(start_date=startDate, end_date=endDate)
    insert_or_update_mlb_games(sched)
    games = []
    for g in sched:
        # Parse and convert game time to Eastern Time
        game_time = dt_parser.isoparse(g['game_datetime']).astimezone(ZoneInfo("America/New_York"))

        # Basic game info
        game = {
            'game_id': g['game_id'],
            'status': g['status'],
            'home': g['home_name'],
            'away': g['away_name'],
            'home_pid': g.get('home_probable_pitcher'),
            'away_pid': g.get('away_probable_pitcher'),
            'venue': g['venue_name'],
            'game_time': game_time.strftime('%Y-%m-%d %I:%M %p %Z'),
        }

        # Include score info if game is final
        if g['status'] == 'Final':
            home_score = g.get('home_score')
            away_score = g.get('away_score')
            total_runs = (home_score or 0) + (away_score or 0)
        else:
            home_score = away_score = total_runs = None

        game.update({
            'home_score': home_score,
            'away_score': away_score,
            'total_runs': total_runs
        })

        games.append(game)

    return games

def get_odds():
    #GEt the API Key
    oddsKey = keys_config['ODDS_API_KEY']
    oddsUrl = app_config['ODDS_API_URL']
    
    resp = requests.get(oddsUrl, params={
        'apiKey': oddsKey, 'regions': 'us',
        'markets': 'totals', 'oddsFormat': 'american'
    })

    resp.raise_for_status()
    return {(g['home_team'], g['away_team']): g for g in resp.json()}

#Pulls only the last 2 games, eR and returns the total count of those runs
def get_recent_er(pitcher_name):
    try:
        pid = get_pitcher_id(pitcher_name)
        default = 4.00,"R"
        if not pid:
            pid = statsapi.lookup_player(pitcher_name)[0]['id']
            if not pid:
                if SHOW_ERRORS: print(f"    No player found with name: {pitcher_name}")
                return default
            insert_pitcher(pid,pitcher_name)

        data = statsapi.get("people", {"personIds": pid, "hydrate": "stats(group=[pitching],type=[gameLog])"})
        pitch_hand = data['people'][0]['pitchHand']['code']

        games = data['people'][0]['stats'][0]['splits'][:2]
        er_list = [int(g['stat'].get('earnedRuns', 0)) for g in games]
        return sum(er_list), pitch_hand
    except Exception as e:
        if SHOW_ERRORS : print(f"    Error fetching recent ER for {pitcher_name}: {e}")
        return default

#Returns ERA, whip, K'sToWalks, HR/9innings for the entire season
def get_pitcher_stats(name):
    try:
        default = 4.00,1.5,2,1.3

        pid = get_pitcher_id(name)

        if not pid:
            lookup = statsapi.lookup_player(name)
            if not lookup:
                if SHOW_ERRORS: print(f"    No player found with name: {name}")
                return default
            pid = lookup[0]['id']
            insert_pitcher(pid,name)
        
        stats = statsapi.player_stat_data(pid, group='pitching', type='season')
        stat_list = stats.get('stats', [])
        
        for stat in stat_list:
            if stat.get('group') == 'pitching' and stat.get('type') == 'season':
                era = stat.get('stats', {}).get('era')
                whip = stat.get('stats',{}).get('whip')
                strikeoutWalkRatio = stat.get('stats',{}).get('strikeoutWalkRatio')
                homeRunsPer9 = stat.get('stats',{}).get('homeRunsPer9')
                if era is not None:
                    era_value = float(era)
                    if era_value == 0: era = 4.00    
                    return float(era), float(whip), float(strikeoutWalkRatio), float(homeRunsPer9)

        if SHOW_ERRORS: print(f"    No ERA stat found for {name}")
        return default

    except Exception as e:
        if SHOW_ERRORS: print(f"    Error getting ERA for {name}: {e}")
        return default

def get_park_factor(venue_name):
    return app_config['PARK_FACTORS'].get(venue_name,1.0)

def get_lineup_factor(team_name):
    return app_config['LINEUP_FACTORS'].get(team_name, 0.75)  # default average

def verdict_based_on_line(predicted_total, total_line):
    diff = predicted_total - total_line
    return diff

def get_lineup_hand_factor(pitcher_hand,opponent):
    if pitcher_hand == 'R':
        factor = app_config['TEAM_PLATOON_SPLITS'].get(opponent, 0.85)['factor_vs_RHP']
        
    else:
        factor = app_config['TEAM_PLATOON_SPLITS'].get(opponent, 0.85)['factor_vs_LHP']

    return factor


def main(model: str, game_dates:str, verbose: bool):
    # Install the cache with a specified name and expiration time (in seconds)
    BOLD= "\033[1m"
    END= "\033[0m"
    global SHOW_PROC_DETAILS
    
    if verbose: SHOW_PROC_DETAILS = True

    requests_cache.install_cache('my_api_cache', expire_after=REQS_CACHE) # Cache for 60 minutes
    #requests_cache.clear()
   
    print(f"{BOLD}Showing info for model {model}{END}")

    create_tables()

    games = get_games(game_dates)
    if SHOW_PROC_DETAILS : print(f"Games length {len(games)}")
    odds_map = get_odds()  #return {(g['home_team'], g['away_team']): g for g in resp.json()}

    print(f"=== {game_dates} Over/Under Predictions/Results === Found {len(games)} Games")
    print(f"Game,Odds,Score,Weight,Prediction,Result,W/L")
    for g in games:
        h, a = g['home'], g['away']
        
        ### IF the game is Over, update the record, if exists and go onto the next game
        if g['status'] == 'Final' :
            
            #returns { total_line, prediction }, Total_line is the odds, and prediction was the Over/Under
            results = get_prediction(g['game_id'], model)
            #Define if the game was Over or Under the odds
            final_runs = g['total_runs'] if g['total_runs'] is not None else ''
            if(results.get('total_line')) :
                final_result = '' if final_runs == '' else ('O' if results['total_line'] < final_runs else 'U')

                #define if this prediction was a win or loss
                if final_result != '':
                    if results['total_line'] == final_runs:
                        wl = 'W'  # Tie on the line is considered a win regardless of prediction
                    else:
                        wl = 'W' if results['prediction'] == final_result else 'L'
                else:
                    wl = ''
                print(f"{BOLD}Results for {h}, {a} final_runs:{final_runs} final_result: {final_result} wl:{wl} home:{g['home_score']} away:{g['away_score']}{END}")
                record = {
                    "final_runs":final_runs,
                    "final_result":final_result,
                    "wl":wl,
                    "completed":1,
                    "home_score":g['home_score'],
                    "away_score":g['away_score']
                }
                close_out_game(record, g['game_id'], model) #, a, h, final_runs, final_result, wl)
            continue;

        #if game is in progress, do nothing
        if g['status'] == 'In Progress' : 
            if SHOW_PROC_DETAILS : print(f"Game is in progress {h}, {a}, Skipping...")
            continue
        if g['status'] == 'Complete' : 
            if SHOW_PROC_DETAILS : print(f"Game is in Complete {h}, {a}, Skipping...")
            continue
        
        oakas = "Oakland Athletics"
        if h == "Athletics" : 
            odds_entry = odds_map.get((oakas, a)) or odds_map.get((a, oakas))
        elif a == "Athletics" : 
            odds_entry = odds_map.get((h, oakas)) or odds_map.get((oakas, h))
        else :
            odds_entry = odds_map.get((h, a)) or odds_map.get((a, h))
        
        game_time = g['game_time']
        # Parse into datetime object
        dt = datetime.strptime(game_time, "%Y-%m-%d %I:%M %p %Z")
        # Format into separate parts
        date_str = dt.strftime("%m/%d/%Y")   # e.g., '07/02/2025'
        time_str = dt.strftime("%I:%M %p")   # e.g., '06:45 PM'

        total_line = 0
        
        if odds_entry :
            try:
                total_line = next(
                    m['outcomes'][0]['point']
                        for bm in odds_entry['bookmakers']
                            if bm['title'] == 'FanDuel' #'Bovada'
                                for m in bm['markets']
                                    if m['key'] == 'totals'
                )
            except StopIteration as e:
                if SHOW_ERRORS : print(f"No totals market for {a} @ {h} {e}")
                continue
        
        #TODO - Use new values for scoring for model C
        #TODO - #Starting pitcher handedness vs lineup	High - Update Database with values
        #Get Pitching stats
        era_h, whip_h, strikeoutWalkRatio_h,homeRunsPer9_h = get_pitcher_stats(g['home_pid'])
        era_a, whip_a, strikeoutWalkRatio_a,homeRunsPer9_a = get_pitcher_stats(g['away_pid'])
        er_h, pitcher_hand_h = get_recent_er(g['home_pid'])
        er_a, pitcher_hand_a = get_recent_er(g['away_pid'])
        bullpen_h = get_bullpen_era(h)
        bullpen_a = get_bullpen_era(a)
        vs_lineup_hand_factor_h = get_lineup_hand_factor(pitcher_hand_h,a)
        vs_lineup_hand_factor_a = get_lineup_hand_factor(pitcher_hand_a,h)

        #Get Batting stats
        #TODO - implment obp, slg, wrc and store in DB
        batting_h = get_team_recent_offense(h)
        batting_a = get_team_recent_offense(a)
        rpg_h = batting_h['avg_runs']
        rpg_a = batting_a['avg_runs']
        #'OBP': round(obp, 3),
        obp_h = batting_h['OBP']
        obp_a = batting_a['OBP']
        #'SLG': round(slg, 3),
        slg_h = batting_h['SLG']
        slg_a = batting_a['SLG']
        #'wRC_approx': wrc_plus - this is an approximate, maybe don't use it until we can get accurate result.
        wrc_h = batting_h['WRC']
        wrc_a = batting_a['WRC']

        line_up_home = get_lineup_factor(g['home'])
        line_up_away = get_lineup_factor(g['away'])


        #Get environmental values to aide in predictions
        temp, wind, wind_dir, humidity = get_weather_for_team(h,game_time)  #  return data['main']['temp'], data['wind']['speed']
        park = get_park_factor(g['venue'])

        parkdirection_factor = 0
        #compute the relative angel based on wind, and park orientation
        #Only compute if it's Model B and others that is not A, original model
        if model != "A" : parkdirection_factor = calc_wind_score(wind_dir, wind, g['venue'], humidity)


        # categorize angle: 0° = blowing along center field, 180° = blowing backhome
        score_h = calc_over_score(era_h, er_h, bullpen_h, rpg_h, temp, wind, park, line_up_home,parkdirection_factor)
        weight_points_h = get_weight_points(era_h, er_h, bullpen_h, rpg_h, temp, wind, park, line_up_home,parkdirection_factor) #use weight_points_h["bullpen_era"]
        score_a = calc_over_score(era_a, er_a, bullpen_a, rpg_a, temp, wind, park, line_up_away,parkdirection_factor)
        weight_points_a = get_weight_points(era_a, er_a, bullpen_a, rpg_a, temp, wind, park, line_up_away,parkdirection_factor)
    
        total_score = round(score_h + score_a,1)

        verdict2 = 0
        if total_line > 0 : verdict2 = round(verdict_based_on_line(total_score, total_line),1)
        
        prediction = ""
        if model == "A" :
            prediction = (
                "O" if verdict2 >= 7.5
                else "U" if verdict2 > 0
                else ""
            )
        else :
            prediction = (
                "O" if verdict2 >= 6.4  #changed 7/7/2025 from 7.5 
                else "U" if verdict2 > 0
                else ""
            )

        #Values - 'Delayed Start:xxxxx', 'Warmup', 'Pre-Game', 'Scheduled', 'In Progress'
        game_status = g['status']
        #print(game_status)

        game_inprogress = 0;
        if game_status == 'In Progress' : game_inprogress = 1

        #Don't update predictions or results if the game is in progress
        if game_inprogress == 0 :
            #final_runs = int(final_runs) if final_runs != '' else None
            insert_or_update_prediction(buildRecord(model, dt, g, a, h, total_line,
                         total_score, verdict2, prediction, 0,
                         '', 0, '', weight_points_h, weight_points_a,
                         g['home_pid'],era_h, 
                         g['away_pid'],era_a,
                         er_h, er_a, 
                         bullpen_h, bullpen_a, 
                         rpg_h, rpg_a, 
                         g['venue'],
                         score_h,
                         score_a,
                         temp,
                         wind, 
                         wind_dir,
                         humidity,
                         parkdirection_factor,
                         line_up_home,
                         line_up_away,
                         app_config['PARK_DIRECTIONS'].get(g['venue'], 0),
                         whip_h, 
                         whip_a, 
                         strikeoutWalkRatio_h,
                         strikeoutWalkRatio_a,
                         homeRunsPer9_h,
                         homeRunsPer9_a,
                         obp_h,
                         obp_a,
                         slg_h,
                         slg_a,
                         wrc_h,
                         wrc_a,
                         pitcher_hand_h,
                         pitcher_hand_a,
                         vs_lineup_hand_factor_h,
                         vs_lineup_hand_factor_a
                         ))
        #When gme is complete, update the recordss.

        #total_line is the odds
        if SHOW_DETAILS :
            print(f"{BOLD}{date_str},{time_str},{g['game_id']},{a} @ {h},{total_line},{total_score},{verdict2},{prediction},,,,{int(weight_points_h['pitcher_era'])},{int(weight_points_a['pitcher_era'])},{int(weight_points_h['recent_er'])},{int(weight_points_a['recent_er'])},{int(weight_points_h['bullpen_era'])},{int(weight_points_a['recent_er'])},{int(weight_points_h['runs_per_game'])},{int(weight_points_a['runs_per_game'])},{int(weight_points_h['temp'])},{int(weight_points_h['wind'])},{int(weight_points_h['hitters_park'])},{weight_points_h['line_up']},{weight_points_a['line_up']},{weight_points_h['hitters_park_scaled']},{weight_points_h['line_up_scaled']},{weight_points_h['wind_park_factor']} {END}")
        else :
            print(f"{BOLD}{date_str},{time_str},{g['game_id']},{a} @ {h},{total_line},{total_score},{verdict2},{prediction}{END}")

REQS_CACHE = 600 #second  60 = 1, 3600 = 6, 36000 = 1 hour
SHOW_DETAILS = False
SHOW_ERRORS = False
SHOW_PROC_DETAILS = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MLB prediction runner')
    parser.add_argument('--date', type=str, help='Date in YYYY-MM-DD format')
    parser.add_argument('--model', type=str, help='Model name (A or B)')
    parser.add_argument('--allModels', action='store_true', help='Run all models')
    parser.add_argument('--todayAndYesterday', action='store_true', help='Run for today and yesterday')
    parser.add_argument('--verbose', action='store_true', help='Show processing details.')
    args = parser.parse_args()
    
    dates = []
    models = ["A", "B"]

    if args.todayAndYesterday:
        today = datetime.today()
        dates = [
            (today - timedelta(days=1)).strftime('%Y-%m-%d'),
            today.strftime('%Y-%m-%d')
        ]
    elif args.date:
        dates = [args.date]
    else:
        # Default to today's date if none provided
        dates = [datetime.today().strftime('%Y-%m-%d')]
   
    if args.allModels:
        for model in models:
            main(model, dates, args.verbose)
    else:
        model = args.model if args.model else "A"  # Default model\
        main(model, dates, args.verbose)
