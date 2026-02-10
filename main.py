from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
# Standard library: SQLite for persistent storage (no external DB server)
import sqlite3
# pathlib gives us a path to the project directory so data.db lives next to main.py
from pathlib import Path
#imports request library for HTTP requests
import requests
#imports Pythons request logging module to log errors
import logging
from datetime import datetime
import time

# Set up logging to see error messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#create a FastAPI application instance
#Main app object that handles routing and requests
app = FastAPI()

# Configure CORS (Cross-Origin Resource Sharing) middleware
# This allows the frontend (running on a different port) to make requests to the backend
# Without this, browsers block requests between different origins (different ports = different origins)
# Multiple origins: localhost (hostname), 127.0.0.1 (IPv4), [::] (IPv6 - e.g. python -m http.server 8080)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://[::]:8080",
    ],
    allow_credentials=True,  # Allow cookies/credentials to be sent
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Path to the SQLite database file in the project directory (next to main.py).
# Path(__file__).resolve().parent is the folder containing main.py; .parent avoids path being the file itself.
DB_PATH = Path(__file__).resolve().parent / "data.db"

# Cache TTL (Time To Live) in seconds. Same concept as before: data older than this is "stale".
# 5 minutes = 300 seconds. We compare stored timestamp to current time in the database layer.
CACHE_TTL = 300


def get_connection():
    """
    Opens a connection to the SQLite database. Each call creates a new connection;
    SQLite handles one writer at a time, and we close after each use (no long-lived connection).
    """
    # sqlite3.connect() opens the file at DB_PATH; creates the file if it does not exist.
    return sqlite3.connect(DB_PATH)


def init_db():
    """
    Creates the database file and tables if they do not exist. Safe to call on every startup.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        # global_metrics: one row for market-wide data. We use id=1 as a single row we overwrite.
        # updated_at is stored as Unix timestamp (REAL) so we can do TTL: (now - updated_at) < CACHE_TTL.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS global_metrics (
                id INTEGER PRIMARY KEY,
                total_market_cap_usd REAL NOT NULL,
                total_volume_24h_usd REAL NOT NULL,
                btc_dominance_percent REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        # coins: one row per coin (top 5). id is the coin id from CoinGecko (e.g. "bitcoin").
        # updated_at is the same for all rows when we do a batch refresh; we use it for TTL.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS coins (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price_usd REAL,
                change_24h REAL,
                volume_24h_usd REAL,
                updated_at REAL NOT NULL
            )
        """)
        # commit() writes the CREATE TABLE statements to disk.
        conn.commit()
    finally:
        conn.close()


# Ensure database and tables exist when the app module loads (e.g. on uvicorn start).
init_db()

#Register a GET route at / (root path)
@app.get("/")
def read_root():
    return {"message": "Hello World! FastAPI is working."}


@app.get("/health")
def health_check():
    return {"status": "ok"}

#function to fetch bitcoin price
def fetch_bitcoin_price():
    """
    Fetches Bitcoin's current price in USD from CoinGecko API.
    
    Returns:
        dict: Contains 'bitcoin' key with price data, or None if error occurs
    """
    # CoinGecko API endpoint for simple price lookup
    # ids=bitcoin means we want Bitcoin's data
    # vs_currencies=usd means we want the price in US Dollars
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
    
    try:
        # Make HTTP GET request to CoinGecko API
        # timeout=10 means the request will fail after 10 seconds if no response
        response = requests.get(url, timeout=10)
        
        # Check if the HTTP response status code is 200 (success)
        # If not 200, something went wrong with the API request
        if response.status_code != 200:
            logger.error(f"CoinGecko API returned status code {response.status_code}")
            return None
        
        # Parse the JSON response into a Python dictionary
        # CoinGecko returns: {"bitcoin": {"usd": 45000.50}}
        data = response.json()
        
        # Return the data dictionary
        return data
        
    except requests.exceptions.RequestException as e:
        # This catches network errors, timeouts, connection issues, etc.
        # requests.exceptions.RequestException is the base class for all request errors
        logger.error(f"Error fetching Bitcoin price: {e}")
        return None


def fetch_multiple_coins():
    """
    Fetches market data for multiple cryptocurrencies from CoinGecko API.
    
    Returns:
        list: List of coin data dictionaries, or None if error occurs
    """
    # CoinGecko API endpoint for market data
    # /coins/markets returns market data for multiple coins in one call
    # vs_currency=usd means all prices are in US Dollars
    # ids=bitcoin,ethereum,solana,cardano,ripple specifies which coins to fetch
    # order=market_cap_desc orders by market cap (descending)
    # per_page=5 limits results to 5 coins
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin,ethereum,solana,cardano,ripple&order=market_cap_desc&per_page=5"
    
    try:
        # Make HTTP GET request to CoinGecko API
        # timeout=10 means the request will fail after 10 seconds if no response
        response = requests.get(url, timeout=10)
        
        # Check if the HTTP response status code is 200 (success)
        # If not 200, something went wrong with the API request
        if response.status_code != 200:
            logger.error(f"CoinGecko API returned status code {response.status_code}")
            return None
        
        # Parse the JSON response into a Python list
        # CoinGecko returns an array of coin objects
        data = response.json()
        
        # Return the data list
        return data
        
    except requests.exceptions.RequestException as e:
        # This catches network errors, timeouts, connection issues, etc.
        # requests.exceptions.RequestException is the base class for all request errors
        logger.error(f"Error fetching multiple coins: {e}")
        return None


def fetch_global_metrics():
    """
    Fetches global cryptocurrency market metrics from CoinGecko API.
    
    Returns:
        dict: Global market data dictionary, or None if error occurs
    """
    # CoinGecko API endpoint for global market data
    # /global returns aggregate market statistics for all cryptocurrencies
    url = "https://api.coingecko.com/api/v3/global"
    
    try:
        # Make HTTP GET request to CoinGecko API
        # timeout=10 means the request will fail after 10 seconds if no response
        response = requests.get(url, timeout=10)
        
        # Check if the HTTP response status code is 200 (success)
        # If not 200, something went wrong with the API request
        if response.status_code != 200:
            logger.error(f"CoinGecko API returned status code {response.status_code}")
            return None
        
        # Parse the JSON response into a Python dictionary
        # CoinGecko returns: {"data": {"total_market_cap": {...}, "total_volume": {...}, ...}}
        data = response.json()
        
        # Return the data dictionary
        return data
        
    except requests.exceptions.RequestException as e:
        # This catches network errors, timeouts, connection issues, etc.
        # requests.exceptions.RequestException is the base class for all request errors
        logger.error(f"Error fetching global metrics: {e}")
        return None


def is_cache_valid(cache_key):
    """
    Checks if stored data in SQLite is still within TTL (not expired).
    For "global" we look at the single row in global_metrics; for "coins" we check any row in coins
    (all coin rows are updated together, so one timestamp represents the whole set).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        now = time.time()
        if cache_key == "global":
            # Select the single global row (id=1). If no row, rowcount/result is empty.
            cur.execute(
                "SELECT updated_at FROM global_metrics WHERE id = 1"
            )
            row = cur.fetchone()
            if row is None:
                return False
            updated_at = row[0]
        else:
            # cache_key == "coins": we have 5 rows with same updated_at; any one is enough.
            cur.execute(
                "SELECT updated_at FROM coins LIMIT 1"
            )
            row = cur.fetchone()
            if row is None:
                return False
            updated_at = row[0]
        # TTL check: data is valid only if (now - updated_at) is less than CACHE_TTL.
        cache_age = now - updated_at
        return cache_age < CACHE_TTL
    finally:
        conn.close()


def get_cached_data(cache_key):
    """
    Reads data from SQLite and returns it in the same shape the endpoints expect
    (dict for global, list of dicts for coins). Returns None if no data.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        if cache_key == "global":
            cur.execute(
                "SELECT total_market_cap_usd, total_volume_24h_usd, btc_dominance_percent FROM global_metrics WHERE id = 1"
            )
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "total_market_cap_usd": row[0],
                "total_volume_24h_usd": row[1],
                "btc_dominance_percent": row[2],
            }
        else:
            # cache_key == "coins": return all rows as list of dicts, same order as API (we can ORDER BY id for stability).
            cur.execute(
                "SELECT id, name, price_usd, change_24h, volume_24h_usd FROM coins ORDER BY id"
            )
            rows = cur.fetchall()
            if not rows:
                return None
            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "price_usd": r[2],
                    "change_24h": r[3],
                    "volume_24h_usd": r[4],
                }
                for r in rows
            ]
    finally:
        conn.close()


def set_cached_data(cache_key, data):
    """
    Writes data into SQLite with current timestamp. Replaces previous data so we always
    have at most one global row and the current set of coin rows.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        now = time.time()
        if cache_key == "global":
            # REPLACE = insert or overwrite row with id=1 (SQLite REPLACE semantics).
            cur.execute(
                """REPLACE INTO global_metrics (id, total_market_cap_usd, total_volume_24h_usd, btc_dominance_percent, updated_at)
                   VALUES (1, ?, ?, ?, ?)""",
                (data["total_market_cap_usd"], data["total_volume_24h_usd"], data["btc_dominance_percent"], now),
            )
        else:
            # coins: clear old rows then insert current list so we don't keep stale coins.
            cur.execute("DELETE FROM coins")
            for coin in data:
                cur.execute(
                    """INSERT INTO coins (id, name, price_usd, change_24h, volume_24h_usd, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        coin["id"],
                        coin["name"],
                        coin["price_usd"],
                        coin["change_24h"],
                        coin["volume_24h_usd"],
                        now,
                    ),
                )
        conn.commit()
    finally:
        conn.close()


def get_cache_timestamp(cache_key):
    """
    Returns the updated_at (Unix timestamp) for the given key from SQLite, or None.
    Used by get_summary() to build meta.last_updated from stored data.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        if cache_key == "global":
            cur.execute("SELECT updated_at FROM global_metrics WHERE id = 1")
        else:
            cur.execute("SELECT updated_at FROM coins LIMIT 1")
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


@app.get("/bitcoin-price")
def get_bitcoin_price():
    """
    Endpoint that returns Bitcoin's current price from CoinGecko.
    """
    # Call our function to fetch the price
    price_data = fetch_bitcoin_price()
    
    # If fetch_bitcoin_price() returned None, there was an error
    if price_data is None:
        return {"error": "Failed to fetch Bitcoin price from CoinGecko"}
    
    # Return the price data (which is already a dictionary)
    return price_data


@app.get("/api/coins/bitcoin")
def get_bitcoin():
    """
    Endpoint that returns Bitcoin's current price with formatted response.
    This endpoint is designed for external clients (e.g., frontend).
    """
    # Call the existing fetch function to get Bitcoin price from CoinGecko
    price_data = fetch_bitcoin_price()
    
    # If fetch_bitcoin_price() returned None, the API call failed
    if price_data is None:
        # Raise HTTPException with status code 502 (Bad Gateway)
        # This indicates the server received an invalid response from upstream
        # detail parameter provides the error message to the client
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch Bitcoin price from CoinGecko API"
        )
    
    # Extract the price from the CoinGecko response
    # price_data structure: {"bitcoin": {"usd": 45000.50}}
    bitcoin_data = price_data.get("bitcoin", {})
    price_usd = bitcoin_data.get("usd")
    
    # If price is missing (shouldn't happen, but defensive programming)
    if price_usd is None:
        raise HTTPException(
            status_code=502,
            detail="Invalid data received from CoinGecko API"
        )
    
    # Get current timestamp in ISO format
    # datetime.now() gets current time, isoformat() converts to string like "2025-01-15T10:30:45"
    timestamp = datetime.now().isoformat()
    
    # Build the response dictionary with all required fields
    # FastAPI will automatically convert this Python dict to JSON
    response = {
        "name": "Bitcoin",
        "price_usd": price_usd,
        "timestamp": timestamp,
        "note": "Live data from CoinGecko"
    }
    
    # Return the response dictionary
    # FastAPI automatically serializes Python dicts to JSON
    return response


@app.get("/api/coins")
def get_coins():
    """
    Endpoint that returns market data for multiple cryptocurrencies.
    Returns a list of top 5 coins with price, 24h change, and volume.
    Uses SQLite for storage; data persists across restarts. TTL limits freshness.
    """
    cache_key = "coins"
    
    # Check if we have valid cached data
    if is_cache_valid(cache_key):
        # Cache hit - return cached data
        cached_data = get_cached_data(cache_key)
        logger.info(f"Cache HIT for {cache_key} - returning cached data")
        return cached_data
    
    # Cache miss or expired - fetch fresh data from CoinGecko
    logger.info(f"Cache MISS for {cache_key} - fetching from CoinGecko")
    
    # Call the function to fetch multiple coins from CoinGecko
    coins_data = fetch_multiple_coins()
    
    # If fetch_multiple_coins() returned None, the API call failed
    if coins_data is None:
        # Raise HTTPException with status code 502 (Bad Gateway)
        # This indicates the server received an invalid response from upstream
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch coin data from CoinGecko API"
        )
    
    # Transform the CoinGecko response into our clean format
    # CoinGecko returns an array, so we iterate through each coin
    transformed_coins = []
    
    for coin in coins_data:
        # Extract and transform each field from CoinGecko's format to our format
        # CoinGecko uses different field names, so we map them
        
        # coin.get() safely retrieves values, with None as default if missing
        coin_id = coin.get("id")  # e.g., "bitcoin"
        coin_name = coin.get("name")  # e.g., "Bitcoin"
        price_usd = coin.get("current_price")  # e.g., 45000.50
        change_24h = coin.get("price_change_percentage_24h")  # e.g., 2.5 (percentage)
        volume_24h_usd = coin.get("total_volume")  # e.g., 25000000000 (in USD)
        
        # Build a clean coin object with our standardized field names
        transformed_coin = {
            "id": coin_id,
            "name": coin_name,
            "price_usd": price_usd,
            "change_24h": change_24h,
            "volume_24h_usd": volume_24h_usd
        }
        
        # Add this coin to our result list
        transformed_coins.append(transformed_coin)
    
    # Store the transformed data in cache for future requests
    set_cached_data(cache_key, transformed_coins)
    logger.info(f"Cached data for {cache_key} with TTL of {CACHE_TTL} seconds")
    
    # Return the list of transformed coins
    # FastAPI automatically serializes Python lists to JSON arrays
    return transformed_coins


@app.get("/api/global")
def get_global_metrics():
    """
    Endpoint that returns global cryptocurrency market metrics.
    Returns total market cap, total 24h volume, and BTC dominance.
    Uses SQLite for storage; data persists across restarts. TTL limits freshness.
    """
    cache_key = "global"
    
    # Check if we have valid cached data
    if is_cache_valid(cache_key):
        # Cache hit - return cached data
        cached_data = get_cached_data(cache_key)
        logger.info(f"Cache HIT for {cache_key} - returning cached data")
        return cached_data
    
    # Cache miss or expired - fetch fresh data from CoinGecko
    logger.info(f"Cache MISS for {cache_key} - fetching from CoinGecko")
    
    # Call the function to fetch global metrics from CoinGecko
    global_data = fetch_global_metrics()
    
    # If fetch_global_metrics() returned None, the API call failed
    if global_data is None:
        # Raise HTTPException with status code 502 (Bad Gateway)
        # This indicates the server received an invalid response from upstream
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch global metrics from CoinGecko API"
        )
    
    # Extract the nested data object from CoinGecko's response
    # CoinGecko wraps everything in a "data" key
    data = global_data.get("data", {})
    
    # Extract total market cap in USD
    # Structure: data.total_market_cap.usd
    total_market_cap = data.get("total_market_cap", {})
    total_market_cap_usd = total_market_cap.get("usd")
    
    # Extract total 24h volume in USD
    # Structure: data.total_volume.usd
    total_volume = data.get("total_volume", {})
    total_volume_24h_usd = total_volume.get("usd")
    
    # Extract BTC dominance percentage
    # Structure: data.market_cap_percentage.btc
    market_cap_percentage = data.get("market_cap_percentage", {})
    btc_dominance_percent = market_cap_percentage.get("btc")
    
    # Check if any required fields are missing
    if total_market_cap_usd is None or total_volume_24h_usd is None or btc_dominance_percent is None:
        raise HTTPException(
            status_code=502,
            detail="Invalid data received from CoinGecko API"
        )
    
    # Build a clean response object with standardized field names
    response = {
        "total_market_cap_usd": total_market_cap_usd,
        "total_volume_24h_usd": total_volume_24h_usd,
        "btc_dominance_percent": btc_dominance_percent
    }
    
    # Store the response in cache for future requests
    set_cached_data(cache_key, response)
    logger.info(f"Cached data for {cache_key} with TTL of {CACHE_TTL} seconds")
    
    # Return the response dictionary
    # FastAPI automatically serializes Python dicts to JSON
    return response


@app.get("/api/summary")
def get_summary():
    """
    Combined endpoint that returns global metrics and coin list in one response.
    Uses SQLite for storage; data persists across server restarts.
    """
    # Check if both datasets are within TTL (from SQLite), so we can set meta.cached.
    cached = is_cache_valid("coins") and is_cache_valid("global")

    # get_global_metrics() and get_coins() read from DB when valid, else fetch and write to DB.
    global_data = get_global_metrics()
    coins_data = get_coins()

    # last_updated = oldest of the two stored timestamps (from SQLite), as ISO string.
    coins_ts = get_cache_timestamp("coins") or 0
    global_ts = get_cache_timestamp("global") or 0
    last_updated_ts = min(coins_ts, global_ts)
    last_updated = datetime.fromtimestamp(last_updated_ts).isoformat() if last_updated_ts else None

    return {
        "global": global_data,
        "coins": coins_data,
        "meta": {
            "cached": cached,
            "last_updated": last_updated,
            "ttl_seconds": CACHE_TTL,
        },
    }
