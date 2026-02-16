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
# Run the periodic update loop in a separate thread so it does not block request handling.
import threading
# For volatility: standard deviation of daily returns (no numpy/pandas).
import statistics

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

# How often the background task fetches from CoinGecko and writes to SQLite (seconds).
# Keeps the database fresh so API endpoints usually serve from DB without refetching.
BACKGROUND_UPDATE_INTERVAL_SECONDS = 300


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
        # volatility_30d: precomputed 30-day volatility (std dev of daily returns), stored as percentage (REAL).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS coins (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price_usd REAL,
                change_24h REAL,
                volume_24h_usd REAL,
                volatility_30d REAL,
                updated_at REAL NOT NULL
            )
        """)
        # Migration: add volatility_30d if table already existed without it.
        # SQLite does not support IF NOT EXISTS for columns; we check PRAGMA table_info and ALTER only when missing.
        cur.execute("PRAGMA table_info(coins)")
        columns = [row[1] for row in cur.fetchall()]
        if "volatility_30d" not in columns:
            cur.execute("ALTER TABLE coins ADD COLUMN volatility_30d REAL")
        # historical_prices: 30-day price history per coin. Populated by background task for correlation/volatility.
        # coin_id + date form logical uniqueness; we DELETE then INSERT to refresh (no unbounded growth).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS historical_prices (
                id INTEGER PRIMARY KEY,
                coin_id TEXT NOT NULL,
                date TEXT NOT NULL,
                price_usd REAL NOT NULL
            )
        """)
        # commit() writes the CREATE TABLE and any ALTER TABLE to disk.
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


def fetch_coin_history(coin_id):
    """
    Fetches ~30 days of historical price data for a coin from CoinGecko's market_chart endpoint.

    CoinGecko endpoint: GET /coins/{id}/market_chart?vs_currency=usd&days=30
    - {id}: the coin ID (e.g. bitcoin, ethereum)
    - vs_currency=usd: prices in USD
    - days=30: last 30 days

    Raw response shape:
    {
      "prices": [[1704067200000, 42000.50], [1704153600000, 42510.75], ...],
      "market_caps": [[ts, cap], ...],
      "total_volumes": [[ts, vol], ...]
    }
    Each "prices" element is [timestamp_ms, price] where timestamp is Unix milliseconds.

    Returns:
        list: List of [timestamp_ms, price] pairs, or None on error
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart?vs_currency=usd&days=30"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logger.error(f"CoinGecko API returned status code {response.status_code} for coin_id={coin_id}")
            return None
        data = response.json()
        prices = data.get("prices")
        if not prices or not isinstance(prices, list):
            logger.error(f"CoinGecko returned no prices for coin_id={coin_id}")
            return None
        return prices
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching history for {coin_id}: {e}")
        return None


def _build_history_response(prices_raw):
    """
    Converts raw prices [[timestamp_ms, price], ...] into our API format.
    - timestamp_ms: Unix time in milliseconds; divide by 1000 for seconds, then use datetime.
    - price: ensure float for JSON.
    Returns sorted list of {"date": "YYYY-MM-DD", "price_usd": float}.
    """
    if not prices_raw:
        return []
    result = []
    for item in prices_raw:
        ts_ms = item[0]
        price = item[1]
        # Convert ms -> seconds for datetime. Use UTC to match typical financial data.
        dt = datetime.utcfromtimestamp(ts_ms / 1000)
        date_str = dt.strftime("%Y-%m-%d")
        result.append({"date": date_str, "price_usd": float(price)})
    # Sort by date (string sort works for YYYY-MM-DD)
    result.sort(key=lambda x: x["date"])
    return result


def calculate_volatility(history):
    """
    Computes 30-day volatility from a list of {date, price_usd} objects.

    Daily return: r_t = (price_today / price_yesterday) - 1
    - Measures percentage change from one day to the next.
    - Volatility = standard deviation of these daily returns (how much returns vary day-to-day).

    Uses sample standard deviation (statistics.stdev): we have a sample of historical returns,
    not the full population, so divide by (n-1) for an unbiased estimate.

    Returns:
        float: Volatility as a percentage (e.g. 5.20 for 5.20%), or None if cannot compute.
    """
    if not history or len(history) < 2:
        return None
    returns = []
    for i in range(1, len(history)):
        prev = history[i - 1].get("price_usd")
        curr = history[i].get("price_usd")
        if prev is None or curr is None:
            continue
        try:
            prev_f = float(prev)
            curr_f = float(curr)
        except (TypeError, ValueError):
            continue
        if prev_f <= 0:
            continue
        daily_return = (curr_f / prev_f) - 1
        returns.append(daily_return)
    if len(returns) < 2:
        return None
    vol_decimal = statistics.stdev(returns)
    return round(vol_decimal * 100, 2)


# Verification (run manually): python -c "
# from main import calculate_volatility
# # Prices 100, 102, 101 -> returns [0.02, -0.0098] -> stdev ~2.09%
# h = [{'date':'a','price_usd':100},{'date':'b','price_usd':102},{'date':'c','price_usd':101}]
# print(calculate_volatility(h))  # expect ~2.09
# "


def calculate_correlation(series_a, series_b):
    """
    Pearson correlation between two aligned price series. Uses daily returns, not raw prices.

    Why returns: Raw prices are non-stationary (both coins trend up over time). Correlation of
    prices would be high even if they move independently. Returns measure day-to-day % change;
    correlation of returns answers "when A goes up 1%, does B tend to go up too?"

    Formula: r = Cov(X,Y) / (sigma_X * sigma_Y)
    Expanded: r = sum((x_i - x_mean)(y_i - y_mean)) / sqrt(sum((x_i - x_mean)^2) * sum((y_i - y_mean)^2))
    Result is between -1 (perfect inverse) and 1 (perfect positive). 0 = no linear relationship.

    Steps:
    1. Compute daily returns for each series.
    2. Mean of each return series.
    3. Numerator: sum of (x_i - mean_x) * (y_i - mean_y).
    4. Denominator: sqrt(sum (x_i - mean_x)^2 * sum (y_i - mean_y)^2).
    5. r = numerator / denominator (return 0.0 if denominator is 0).
    """
    if not series_a or not series_b or len(series_a) != len(series_b):
        return None
    n = len(series_a)
    if n < 2:
        return None
    returns_a = []
    returns_b = []
    for i in range(1, n):
        prev_a = series_a[i - 1]
        curr_a = series_a[i]
        prev_b = series_b[i - 1]
        curr_b = series_b[i]
        if prev_a is None or prev_b is None or prev_a <= 0 or prev_b <= 0:
            continue
        try:
            ra = (float(curr_a) / float(prev_a)) - 1
            rb = (float(curr_b) / float(prev_b)) - 1
        except (TypeError, ValueError):
            continue
        returns_a.append(ra)
        returns_b.append(rb)
    if len(returns_a) < 2:
        return None
    mean_a = sum(returns_a) / len(returns_a)
    mean_b = sum(returns_b) / len(returns_b)
    num = sum((a - mean_a) * (b - mean_b) for a, b in zip(returns_a, returns_b))
    var_a = sum((a - mean_a) ** 2 for a in returns_a)
    var_b = sum((b - mean_b) ** 2 for b in returns_b)
    denom = (var_a * var_b) ** 0.5
    if denom <= 0:
        return 0.0
    r = num / denom
    r = max(-1.0, min(1.0, r))
    return round(r, 4)


# Correlation verification: python -c "
# from main import calculate_correlation
# # [1,2,3] and [2,4,6]: returns both [1, 0.5] -> perfectly correlated
# print(calculate_correlation([1,2,3], [2,4,6]))  # expect 1.0
# "


def _align_histories_by_date(history_a, history_b):
    """
    Aligns two history lists by date. Returns (series_a, series_b) of aligned prices,
    or ([], []) if insufficient overlap. Only dates present in BOTH series are used.
    """
    if not history_a or not history_b:
        return [], []
    dict_a = {h["date"]: h.get("price_usd") for h in history_a}
    dict_b = {h["date"]: h.get("price_usd") for h in history_b}
    common = sorted(set(dict_a.keys()) & set(dict_b.keys()))
    series_a = [dict_a[d] for d in common]
    series_b = [dict_b[d] for d in common]
    return series_a, series_b


def _build_global_response(global_data_raw):
    """
    Converts raw CoinGecko /global response into our API shape.
    Returns a dict with total_market_cap_usd, total_volume_24h_usd, btc_dominance_percent, or None if invalid.
    Shared by get_global_metrics (on cache miss) and the background update cycle.
    """
    if global_data_raw is None:
        return None
    data = global_data_raw.get("data", {})
    total_market_cap = data.get("total_market_cap", {})
    total_market_cap_usd = total_market_cap.get("usd")
    total_volume = data.get("total_volume", {})
    total_volume_24h_usd = total_volume.get("usd")
    market_cap_percentage = data.get("market_cap_percentage", {})
    btc_dominance_percent = market_cap_percentage.get("btc")
    if total_market_cap_usd is None or total_volume_24h_usd is None or btc_dominance_percent is None:
        return None
    return {
        "total_market_cap_usd": total_market_cap_usd,
        "total_volume_24h_usd": total_volume_24h_usd,
        "btc_dominance_percent": btc_dominance_percent,
    }


def _build_coins_list(coins_data_raw):
    """
    Converts raw CoinGecko /coins/markets response into our API shape (list of dicts).
    Returns the list or None if invalid. Shared by get_coins (on cache miss) and the background update cycle.
    """
    if coins_data_raw is None or not isinstance(coins_data_raw, list):
        return None
    transformed = []
    for coin in coins_data_raw:
        transformed.append({
            "id": coin.get("id"),
            "name": coin.get("name"),
            "price_usd": coin.get("current_price"),
            "change_24h": coin.get("price_change_percentage_24h"),
            "volume_24h_usd": coin.get("total_volume"),
        })
    return transformed if transformed else None


def _enrich_coins_with_volatility(coins_list):
    """
    Adds volatility_30d to each coin by fetching 30-day history and computing volatility.
    Also stores history in historical_prices so the correlation endpoint can read from DB.
    Reuses fetch_coin_history, _build_history_response, and calculate_volatility.
    If volatility cannot be computed for a coin, sets volatility_30d to None (stored as NULL in DB).
    Errors in one coin do not abort the rest; each coin is tried independently.
    """
    if not coins_list:
        return coins_list
    result = []
    for coin in coins_list:
        c = dict(coin)
        vol = None
        try:
            coin_id = c.get("id")
            if coin_id:
                prices_raw = fetch_coin_history(coin_id)
                history = _build_history_response(prices_raw) if prices_raw else []
                store_historical_prices(coin_id, history)
                vol = calculate_volatility(history)
        except Exception as e:
            logger.warning("Could not compute volatility for %s: %s", c.get("id"), e)
        c["volatility_30d"] = vol
        result.append(c)
    return result


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
            # cache_key == "coins": return all rows as list of dicts, same order as API (ORDER BY id for stability).
            # volatility_30d comes from DB (precomputed during background update).
            cur.execute(
                "SELECT id, name, price_usd, change_24h, volume_24h_usd, volatility_30d FROM coins ORDER BY id"
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
                    "volatility_30d": r[5],
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
                vol = coin.get("volatility_30d")
                cur.execute(
                    """INSERT INTO coins (id, name, price_usd, change_24h, volume_24h_usd, volatility_30d, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        coin["id"],
                        coin["name"],
                        coin["price_usd"],
                        coin["change_24h"],
                        coin["volume_24h_usd"],
                        vol,
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


def store_historical_prices(coin_id, history):
    """
    Writes 30-day price history to historical_prices. Replaces existing rows for this coin.
    DELETE then INSERT avoids duplicates and keeps the table bounded (we only store ~30 rows per coin).
    """
    if not coin_id or not history:
        return
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM historical_prices WHERE coin_id = ?", (coin_id,))
        for h in history:
            date_val = h.get("date")
            price_val = h.get("price_usd")
            if date_val is not None and price_val is not None:
                cur.execute(
                    "INSERT INTO historical_prices (coin_id, date, price_usd) VALUES (?, ?, ?)",
                    (coin_id, date_val, float(price_val)),
                )
        conn.commit()
    finally:
        conn.close()


def get_historical_prices_from_db(coin_id):
    """
    Reads 30-day price history from SQLite. Returns list of {date, price_usd} or empty list.
    Used by correlation endpoint so it does not call CoinGecko.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT date, price_usd FROM historical_prices WHERE coin_id = ? ORDER BY date",
            (coin_id,),
        )
        rows = cur.fetchall()
        return [{"date": r[0], "price_usd": r[1]} for r in rows]
    finally:
        conn.close()


def run_one_update_cycle():
    """
    Fetches global and coin data from CoinGecko, then writes both to SQLite.
    Used by the background thread so the DB stays fresh without blocking requests.
    Logs when each database write happens. Exceptions are logged and not re-raised.
    """
    logger.info("Running background update cycle")
    # Fetch and write global metrics.
    global_data_raw = fetch_global_metrics()
    global_response = _build_global_response(global_data_raw)
    if global_response is not None:
        set_cached_data("global", global_response)
        logger.info("Database updated: global")
    else:
        logger.warning("Background update: global fetch or build failed, skipping global write")
    # Fetch and write coins (including volatility computed from 30-day history).
    coins_data_raw = fetch_multiple_coins()
    coins_list = _build_coins_list(coins_data_raw)
    if coins_list is not None:
        coins_list = _enrich_coins_with_volatility(coins_list)
        set_cached_data("coins", coins_list)
        logger.info("Database updated: coins")
    else:
        logger.warning("Background update: coins fetch or build failed, skipping coins write")


def background_update_loop():
    """
    Infinite loop that runs run_one_update_cycle() every BACKGROUND_UPDATE_INTERVAL_SECONDS.
    Runs in a daemon thread so it does not block the main thread (request handling).
    time.sleep() blocks only this thread; the main thread continues serving requests.
    """
    logger.info("Background update task started (interval=%s seconds)", BACKGROUND_UPDATE_INTERVAL_SECONDS)
    while True:
        try:
            run_one_update_cycle()
        except Exception as e:
            logger.exception("Background update cycle failed: %s", e)
        time.sleep(BACKGROUND_UPDATE_INTERVAL_SECONDS)


@app.on_event("startup")
def start_background_updater():
    """
    FastAPI startup event: runs once when the app is ready. We start the background
    update loop in a daemon thread so it runs alongside the main thread that handles HTTP.
    daemon=True means the thread will not keep the process alive if the main thread exits.
    """
    thread = threading.Thread(target=background_update_loop, daemon=True)
    thread.start()
    logger.info("Background update task registered; thread started")


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
    
    # Cache miss or expired - fetch fresh data from CoinGecko and compute volatility
    logger.info(f"Cache MISS for {cache_key} - fetching from CoinGecko")
    
    coins_data_raw = fetch_multiple_coins()
    transformed_coins = _build_coins_list(coins_data_raw)
    if transformed_coins is None:
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch coin data from CoinGecko API"
        )
    transformed_coins = _enrich_coins_with_volatility(transformed_coins)
    set_cached_data(cache_key, transformed_coins)
    logger.info(f"Cached data for {cache_key} with TTL of {CACHE_TTL} seconds")
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
    
    global_data_raw = fetch_global_metrics()
    response = _build_global_response(global_data_raw)
    if response is None:
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch global metrics from CoinGecko API"
        )
    set_cached_data(cache_key, response)
    logger.info(f"Cached data for {cache_key} with TTL of {CACHE_TTL} seconds")
    return response


@app.get("/api/history/{coin_id}")
def get_coin_history(coin_id: str):
    """
    Returns ~30 days of historical price data for a coin. Fetch-only (no SQLite storage).
    """
    if not coin_id or not coin_id.strip():
        raise HTTPException(status_code=404, detail="Invalid coin ID")
    coin_id = coin_id.strip().lower()
    prices_raw = fetch_coin_history(coin_id)
    if prices_raw is None:
        raise HTTPException(status_code=502, detail="Failed to fetch historical data from CoinGecko")
    history = _build_history_response(prices_raw)
    if not history:
        raise HTTPException(status_code=404, detail=f"No history found for coin: {coin_id}")
    return history


@app.get("/api/volatility/{coin_id}")
def get_coin_volatility(coin_id: str):
    """
    Returns 30-day volatility (std dev of daily returns) for a coin. Calculation on demand, no SQLite storage.
    """
    if not coin_id or not coin_id.strip():
        raise HTTPException(status_code=400, detail="Invalid coin ID")
    coin_id = coin_id.strip().lower()
    prices_raw = fetch_coin_history(coin_id)
    if prices_raw is None:
        raise HTTPException(status_code=502, detail="Failed to fetch historical data from CoinGecko")
    history = _build_history_response(prices_raw)
    if len(history) < 2:
        raise HTTPException(status_code=400, detail="At least 2 price points required to compute volatility")
    vol = calculate_volatility(history)
    if vol is None:
        raise HTTPException(status_code=400, detail="Could not compute volatility (insufficient valid returns)")
    return {"coin": coin_id, "volatility_30d": vol}


@app.get("/api/correlation/{coin_a}/{coin_b}")
def get_correlation(coin_a: str, coin_b: str):
    """
    Returns 30-day Pearson correlation between two coins. Reads from SQLite; does NOT call CoinGecko.
    Historical data is populated by the background task. Avoids 429 rate limits and works when CoinGecko is down.
    """
    if not coin_a or not coin_a.strip() or not coin_b or not coin_b.strip():
        raise HTTPException(status_code=400, detail="Invalid coin ID")
    coin_a = coin_a.strip().lower()
    coin_b = coin_b.strip().lower()
    history_a = get_historical_prices_from_db(coin_a)
    history_b = get_historical_prices_from_db(coin_b)
    if not history_a:
        raise HTTPException(status_code=400, detail=f"No historical data for coin: {coin_a}")
    if not history_b:
        raise HTTPException(status_code=400, detail=f"No historical data for coin: {coin_b}")
    series_a, series_b = _align_histories_by_date(history_a, history_b)
    if len(series_a) < 3 or len(series_b) < 3:
        raise HTTPException(
            status_code=400,
            detail="Insufficient overlapping data (need at least 3 aligned days)",
        )
    corr = calculate_correlation(series_a, series_b)
    if corr is None:
        raise HTTPException(
            status_code=400,
            detail="Could not compute correlation (insufficient valid returns)",
        )
    return {"coin_a": coin_a, "coin_b": coin_b, "correlation_30d": corr}


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
