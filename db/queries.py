from .connection import get_connection

def get_prediction(gameId, modelName):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT total_line, prediction FROM predictions WHERE game_id = %s AND model_name = %s
    """, (gameId, modelName))
    existing = cursor.fetchone()
    conn.close()
    prediction = {}

    if existing:
        return {
            'total_line': existing['total_line'],
            'prediction': existing['prediction']
        }

    return {}

def get_pitcher_id(name):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT pid FROM pitchers WHERE name = %s
    """, (name,))
    pitcher = cursor.fetchone()
    conn.close()

    return pitcher['pid'] if pitcher else None


