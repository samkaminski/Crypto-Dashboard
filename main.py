from fastapi import FastAPI
#imports request library for HTTP requests
import requests
#imports Pythons request logging module to log errors
import logging

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
