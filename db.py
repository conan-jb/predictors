import mysql.connector
from config import db_config

def test_connection():
    conn = mysql.connector.connect(**db_config)
    print("Connected!" if conn.is_connected() else "Failed to connect.")
    conn.close()

def create_tables():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        model_name VARCHAR(100),
        game_id BIGINT,
        game_date DATE,
        game_time TIME,
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
        INDEX idx_predictions_gameid (game_id),
        home_score INT, 
        away_score INT
    )
    """)
    
    conn.commit()
    conn.close()