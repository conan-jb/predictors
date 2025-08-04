from .connection import get_connection

'''
TODO - Table creations
Create a Models Table
'''

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        model_name VARCHAR(100),
        game_id BIGINT,
        game_date TIMESTAMP,
        away_team VARCHAR(50),
        home_team VARCHAR(50),
        total_line DECIMAL(4,2),
        total_score DECIMAL(4,2),
        verdict FLOAT,
        prediction CHAR(1),
        final_runs INT,
        final_result CHAR(1),
        completed BOOLEAN,
        wl CHAR(1),
        home_pitcher_era FLOAT, 
        away_pitcher_era FLOAT,
        home_recent_er FLOAT,
        away_recent_er FLOAT,
        home_bullpen_era FLOAT,
        away_bullpen_era FLOAT,
        home_runs_per_game FLOAT,
        away_runs_per_game FLOAT,
        home_temp INT,
        home_wind INT,
        home_hitters_park INT,
        home_line_up FLOAT,
        away_line_up FLOAT,
        home_hitters_park_scaled FLOAT,
        home_line_up_scaled FLOAT,
        home_wind_park_factor FLOAT,
        home_score INT,
        away_score INT,
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
        park_directions_value Decimal(6,2),
        lineup_factor_home_value Decimal(4,2),
        lineup_factor_away_value Decimal(4,2),
        home_pitcher_whip_value FLOAT,
        away_pitcher_whip_value FLOAT,
        home_pitcher_strikeoutWalkRatio_value FLOAT,
        away_pitcher_strikeoutWalkRatio_value FLOAT,
        home_pitcher_homeRunsPer9_value FLOAT,
        away_pitcher_homeRunsPer9_value FLOAT,
        home_obp_value FLOAT,
        away_obp_value FLOAT,
        home_slg_value FLOAT,
        away_slg_value FLOAT,
        home_wrc_value FLOAT,
        away_wrc_value FLOAT,
        home_pitcher_hand CHAR(1),
        away_pitcher_hand CHAR(1),
        home_pitcherhand_vs_lineup_factor FLOAT,
        away_pitcherhand_vs_lineup_factor FLOAT,
        INDEX idx_mlb_pred_game_id (game_id),
        INDEX idx_mlb_pred_model (model_name)
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mlb_games (
        game_id BIGINT PRIMARY KEY,
        game_datetime DATETIME,
        game_date DATE,
        game_type VARCHAR(10),
        status VARCHAR(50),
        away_name VARCHAR(100),
        home_name VARCHAR(100),
        away_id INT,
        home_id INT,
        doubleheader CHAR(1),
        game_num INT,
        home_probable_pitcher VARCHAR(100),
        away_probable_pitcher VARCHAR(100),
        home_pitcher_note TEXT,
        away_pitcher_note TEXT,
        away_score VARCHAR(10),
        home_score VARCHAR(10),
        current_inning VARCHAR(10),
        inning_state VARCHAR(10),
        venue_id INT,
        venue_name VARCHAR(100),
        national_broadcasts VARCHAR(200),
        series_status VARCHAR(50),
        summary TEXT,
        INDEX idx_mlb_game_date (game_date)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pitchers (
        id INT AUTO_INCREMENT PRIMARY KEY,
        pid INT,
        name VARCHAR(200),
        INDEX idx_pitchers_name (name)
        );  
    """)
    conn.commit()
    conn.close()