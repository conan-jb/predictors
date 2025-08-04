from .connection import get_connection
from datetime import datetime

def preprocess_games(raw_games):
    processed = []
    for g in raw_games:
        game = g.copy()  # Don’t modify the original if re-used
        # Convert ISO 8601 string to datetime object
        game["game_datetime"] = datetime.strptime(game["game_datetime"], "%Y-%m-%dT%H:%M:%SZ")

        # Take the first broadcast name if available
        broadcasts = g.get("national_broadcasts", [])
        game["national_broadcasts"] = broadcasts[0] if broadcasts else ""

        processed.append(game)
    return processed

def insert_pitcher(pid, name):
    conn = get_connection()
    cursor = conn.cursor(buffered=True)  
    
    insert_sql = f"""
        INSERT INTO pitchers (pid,name) VALUES (%s,%s)
    """
    cursor.execute(insert_sql,(pid,name))

    conn.commit()
    conn.close()

def insert_or_update_mlb_games(games):
    if not games:
        return
    
    #Convert the ISO timestamp to datetime object and reduce broadcasts to a single object
    games = preprocess_games(games)
    
    conn = get_connection()
    cursor = conn.cursor(buffered=True)  
    insert_sql = """
    INSERT INTO mlb_games (
        game_id, game_datetime, game_date, game_type, status,
        away_name, home_name, away_id, home_id, doubleheader, game_num,
        home_probable_pitcher, away_probable_pitcher,
        home_pitcher_note, away_pitcher_note,
        away_score, home_score,
        current_inning, inning_state,
        venue_id, venue_name, national_broadcasts,
        series_status, summary
    )
    VALUES (
        %(game_id)s, %(game_datetime)s, %(game_date)s, %(game_type)s, %(status)s,
        %(away_name)s, %(home_name)s, %(away_id)s, %(home_id)s, %(doubleheader)s, %(game_num)s,
        %(home_probable_pitcher)s, %(away_probable_pitcher)s,
        %(home_pitcher_note)s, %(away_pitcher_note)s,
        %(away_score)s, %(home_score)s,
        %(current_inning)s, %(inning_state)s,
        %(venue_id)s, %(venue_name)s, %(national_broadcasts)s,
        %(series_status)s, %(summary)s
    )
    ON DUPLICATE KEY UPDATE
        game_datetime = VALUES(game_datetime),
        status = VALUES(status),
        away_score = VALUES(away_score),
        home_score = VALUES(home_score),
        current_inning = VALUES(current_inning),
        inning_state = VALUES(inning_state),
        home_probable_pitcher = VALUES(home_probable_pitcher),
        away_probable_pitcher = VALUES(away_probable_pitcher),
        summary = VALUES(summary)
    """
    cursor.executemany(insert_sql, games)
    conn.commit()
    conn.close()

def close_out_game(record, gameId, model_name) :
    conn = get_connection()
    cursor = conn.cursor(buffered=True)    
    # Update existing record
    set_clause = ", ".join(f"{k} = %s" for k in record.keys())
    values = list(record.values()) + [gameId, model_name]
    update_sql = f"""
        UPDATE predictions SET {set_clause}
        WHERE game_id = %s AND model_name = %s
    """
    cursor.execute(update_sql, values)
    #print(f"Updated prediction ID - Game Over {gameId}")
    conn.commit()
    conn.close()

#def insert_or_update_prediction(model_name, gamedate, g, a, h, total_line,
#                          total_score, verdict2, prediction, final_runs,
#                          final_result, game_complete, wl, weight_points_h, weight_points_a, home_pitcher,home_pitcher_era_value, away_pitcher,away_pitcher_era_value,
#                           home_recent_er_value,  away_recent_er_value, home_bullpen_era_value, away_bullpen_era_value, home_runs_per_game_value, away_runs_per_game_value, park):
def insert_or_update_prediction(record):
    conn = get_connection()
    cursor = conn.cursor(buffered=True)

    '''
            home_pitcher VARCHAR(125),
        home_pitcher_era_value FLOAT,
        away_pitcher VARCHAR(125),
        away_pitcher_era_value FLOAT,
        home_recent_er_value FLOAT,
        away_recent_er_value FLOAT,
        home_bullpen_era_value FLOAT,
        away_bullpen_era_value FLOAT,
        home_runs_per_game_value FLOAT,
        away_runs_per_game_value FLOAT,
        park VARCHAR(125),  
        pred_total_score_home DECIMAL(4,2),
        pred_total_score_away DECIMAL(4,2),
        temp_value INT,
        wind_value INT,
        wind_dir_value INT,
        humdity_value INT,
        park_factor_value Decimal(4,2),
        lineup_factor_home_value Decimal(4,2),
        lineup_factor_away_value Decimal(4,2),
        park_directions_value Decimal(4,2),
    '''

    #record = buildRecord(model_name, gamedate, g, a, h, total_line,
    #                      total_score, verdict2, prediction, final_runs,
    #                      final_result, game_complete, wl, weight_points_h, weight_points_a, home_pitcher,home_pitcher_era_value, away_pitcher,away_pitcher_era_value,
    #                       home_recent_er_value,  away_recent_er_value, home_bullpen_era_value, away_bullpen_era_value, home_runs_per_game_value, away_runs_per_game_value, park)
    # Check for existing record
    cursor.execute("""
        SELECT id FROM predictions WHERE game_id = %s AND model_name = %s
    """, (record['game_id'], record['model_name']))
    existing = cursor.fetchone()

    if existing:
        # Update existing record
        set_clause = ", ".join(f"{k} = %s" for k in record.keys())
        #values = list(record.values()) + [g['game_id'], model_name]
        values = list(record.values()) + [record['game_id'], record['model_name']]

        update_sql = f"""
            UPDATE predictions SET {set_clause}
            WHERE game_id = %s AND model_name = %s
        """
        cursor.execute(update_sql, values)
        #print(f"Updated prediction ID {existing[0]}")
    else:
        # Insert new record
        columns = ", ".join(record.keys())
        placeholders = ", ".join(["%s"] * len(record))
        insert_sql = f"""
            INSERT INTO predictions ({columns}) VALUES ({placeholders})
        """
        cursor.execute(insert_sql, list(record.values()))
        #print(f"Inserted new prediction ID {cursor.lastrowid}")

    conn.commit()
    conn.close()

def buildRecord(model_name, gamedate, g, a, h, total_line,
                          total_score, verdict2, prediction, final_runs,
                          final_result,game_complete, wl, weight_points_h, weight_points_a, home_pitcher,home_pitcher_era_value, away_pitcher,away_pitcher_era_value,
                           home_recent_er_value,  away_recent_er_value, home_bullpen_era_value, away_bullpen_era_value, home_runs_per_game_value, away_runs_per_game_value, park,
                        pred_total_score_home,
        pred_total_score_away,
        temp_value,
        wind_value,
        wind_dir_value,
        humdity_value,
        park_factor_value,
        lineup_factor_home_value,
        lineup_factor_away_value,
        park_directions_value,                         
        whip_h_value, 
        whip_a_value, 
        strikeoutWalkRatio_h_value,
        strikeoutWalkRatio_a_value,
        homeRunsPer9_h_value,
        homeRunsPer9_a_value,
        obp_h_value,
        obp_a_value,
        slg_h_value,
        slg_a_value,
        wrc_h_value,
        wrc_a_value,
        pitcher_hand_h,
        pitcher_hand_a,
        vs_lineup_hand_factor_h,
        vs_lineup_hand_factor_a):
    
    record = {
        "model_name": model_name,
        "game_id": g['game_id'],
        "game_date":gamedate,
        "away_team": a,
        "home_team": h,
        "total_line": total_line,
        "total_score": total_score,
        "verdict": verdict2,
        "prediction": prediction,
        "final_runs": final_runs,
        "final_result": final_result,
        "completed": game_complete,
        "wl": wl,
        "home_pitcher_era": weight_points_h.get('pitcher_era'),
        "away_pitcher_era": weight_points_a.get('pitcher_era'),
        "home_recent_er": weight_points_h.get('recent_er'),
        "away_recent_er": weight_points_a.get('recent_er'),
        "home_bullpen_era": weight_points_h.get('bullpen_era'),
        "away_bullpen_era": weight_points_a.get('bullpen_era'),
        "home_runs_per_game": weight_points_h.get('runs_per_game'),
        "away_runs_per_game": weight_points_a.get('runs_per_game'),
        "home_temp": weight_points_h.get('temp'),
        "home_wind": weight_points_h.get('wind'),
        "home_hitters_park": weight_points_h.get('hitters_park'),
        "home_line_up": weight_points_h.get('line_up'),
        "away_line_up": weight_points_a.get('line_up'),
        "home_hitters_park_scaled": weight_points_h.get('hitters_park_scaled'),
        "home_line_up_scaled": weight_points_h.get('line_up_scaled'),
        "home_wind_park_factor": weight_points_h.get('wind_park_factor'),
        "prediction_date": datetime.now(),
        "home_pitcher":home_pitcher,
        "home_pitcher_era_value":home_pitcher_era_value, 
        "away_pitcher":away_pitcher,
        "away_pitcher_era_value":away_pitcher_era_value,
        "home_recent_er_value":home_recent_er_value,
        "away_recent_er_value":away_recent_er_value,
        "home_bullpen_era_value":home_bullpen_era_value,
        "away_bullpen_era_value":away_bullpen_era_value,
        "home_runs_per_game_value":home_runs_per_game_value,
        "away_runs_per_game_value":away_runs_per_game_value,
        "park":park,
        "pred_total_score_home":pred_total_score_home,
        "pred_total_score_away":pred_total_score_away,
        "temp_value":temp_value,
        "wind_value":wind_value,
        "wind_dir_value":wind_dir_value,
        "humdity_value":humdity_value,
        "park_factor_value":park_factor_value,
        "lineup_factor_home_value":lineup_factor_home_value,
        "lineup_factor_away_value":lineup_factor_away_value,
        "park_directions_value":park_directions_value,
        "home_pitcher_whip_value":whip_h_value,
        "away_pitcher_whip_value":whip_a_value,
        "home_pitcher_strikeoutWalkRatio_value":strikeoutWalkRatio_h_value,
        "away_pitcher_strikeoutWalkRatio_value":strikeoutWalkRatio_a_value,
        "home_pitcher_homeRunsPer9_value":homeRunsPer9_h_value,
        "away_pitcher_homeRunsPer9_value":homeRunsPer9_a_value,
        "home_obp_value":obp_h_value,
        "away_obp_value":obp_a_value,
        "home_slg_value":slg_h_value,
        "away_slg_value":slg_a_value,
        "home_wrc_value":wrc_h_value,
        "away_wrc_value":wrc_a_value,
        "home_pitcher_hand":pitcher_hand_h,
        "away_pitcher_hand":pitcher_hand_a,
        "home_pitcherhand_vs_lineup_factor": vs_lineup_hand_factor_h,
        "away_pitcherhand_vs_lineup_factor": vs_lineup_hand_factor_a
        }
    return record