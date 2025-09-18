import os

# Update these for your MySQL setup
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "1234"),
    "database": os.environ.get("DB_NAME", "fish_market_db"),
    "port": int(os.environ.get("DB_PORT", "3306")),
}

SECRET_KEY = os.environ.get("SECRET_KEY", "112255")
