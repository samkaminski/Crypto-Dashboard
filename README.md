# Crypto Market Dashboard

A learning-focused project to build a cryptocurrency market dashboard using Python and FastAPI. The project is being developed incrementally through small vertical slices, with each slice adding one piece of functionality end-to-end.

## Tech Stack

- **Backend**: Python 3.x with FastAPI
- **Data Source**: CoinGecko API (public, no API key required)
- **Server**: Uvicorn ASGI server

## Current Status

Early development phase. Currently implemented:

- Basic FastAPI server with health check endpoint
- Bitcoin price fetching from CoinGecko API
- Error handling for API requests

This is a work in progress. The project follows a slice-by-slice approach where each slice produces something runnable and testable.

## Running Locally

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the server:**
   ```bash
   uvicorn main:app --reload
   ```

3. **Test the endpoints:**
   - Root: `http://localhost:8000/`
   - Health: `http://localhost:8000/health`
   - Bitcoin price: `http://localhost:8000/bitcoin-price`
   - API docs: `http://localhost:8000/docs`

## Project Structure

- `main.py` - FastAPI application and endpoints
- `requirements.txt` - Python dependencies
- `slices.md` - Detailed breakdown of planned vertical slices
