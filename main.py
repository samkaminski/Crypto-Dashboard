from fastapi import FastAPI, HTTPException
#imports request library for HTTP requests
import requests
#imports Pythons request logging module to log errors
import logging
from datetime import datetime

# Set up logging to see error messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#create a FastAPI application instance
#Main app object that handles routing and requests
app = FastAPI()

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
    """
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
    
    # Return the list of transformed coins
    # FastAPI automatically serializes Python lists to JSON arrays
    return transformed_coins


@app.get("/api/global")
def get_global_metrics():
    """
    Endpoint that returns global cryptocurrency market metrics.
    Returns total market cap, total 24h volume, and BTC dominance.
    """
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
    
    # Return the response dictionary
    # FastAPI automatically serializes Python dicts to JSON
    return response
