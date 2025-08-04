# config.py
import json

with open("config.json", "r") as f:
    config = json.load(f)

# Optional: expose parts for easy access
#root user is root/2hornets
db_config = config["database"]

app_config = config["app"]
keys_config = config["keys"]