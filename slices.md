# Crypto Market Dashboard - Vertical Slices

## Slice 1: Hello World FastAPI Server
**Goal:** Set up a minimal FastAPI server that responds to HTTP requests, proving the backend foundation works.

**What can be tested:**
- Start the server locally
- Visit `http://localhost:8000` and see a response
- Visit `http://localhost:8000/docs` and see the auto-generated API docs
- Make a GET request to a test endpoint (e.g., `/health`) and receive a JSON response

**System parts touched:**
- Backend (FastAPI setup, basic routing)

**Deliverable:** A single Python file with FastAPI that runs and serves a simple endpoint.

---

## Slice 2: Fetch Single Coin Price from CoinGecko
**Goal:** Create a backend function that calls CoinGecko API to fetch Bitcoin's current price, demonstrating we can retrieve external data.

**What can be tested:**
- Run a Python script or call an endpoint that fetches Bitcoin price from CoinGecko
- Print/log the price data to verify the API call works
- Handle basic errors (network failure, API down)

**System parts touched:**
- Backend (HTTP client, external API integration)

**Deliverable:** A function that makes a request to CoinGecko and returns Bitcoin's current price as JSON.

---

## Slice 3: FastAPI Endpoint Returns Coin Price
**Goal:** Expose the CoinGecko fetch as a FastAPI endpoint so the frontend can call it.

**What can be tested:**
- Start FastAPI server
- Call `GET /api/coins/bitcoin` and receive Bitcoin price data
- Verify the response is valid JSON with expected fields (price, name, etc.)

**System parts touched:**
- Backend (API endpoint, integration with external API)

**Deliverable:** A working endpoint that returns live Bitcoin price data from CoinGecko.

---

## Slice 4: Static HTML Page Displays Bitcoin Price
**Goal:** Create a simple HTML page that fetches and displays Bitcoin price from the FastAPI backend.

**What can be tested:**
- Open HTML file in browser
- Page loads and makes a fetch request to the FastAPI endpoint
- Bitcoin price appears on the page
- Can manually refresh to see updated price

**System parts touched:**
- Frontend (HTML, JavaScript fetch, basic DOM manipulation)
- Integration between frontend and backend

**Deliverable:** A single HTML file that shows Bitcoin's current price fetched from the backend.

---

## Slice 5: Fetch Multiple Coins (Top 5)
**Goal:** Extend the backend to fetch prices for multiple coins (e.g., top 5 by market cap) in a single API call.

**What can be tested:**
- Call an endpoint (e.g., `GET /api/coins`) and receive an array of 5 coins with their prices
- Verify each coin has required fields (id, name, price, 24h_change, volume)
- Test with different coin lists

**System parts touched:**
- Backend (API endpoint, data transformation)

**Deliverable:** An endpoint that returns an array of top 5 coins with their market data.

---

## Slice 6: Frontend Table Displays Multiple Coins
**Goal:** Update the HTML page to display multiple coins in a table format with columns for price, change, volume.

**What can be tested:**
- Open the page and see a table with 5 coins
- Each row shows: coin name, price, 24h change (with color coding), volume
- Data updates when manually refreshed
- Table is readable and formatted

**System parts touched:**
- Frontend (HTML table, JavaScript rendering, data formatting)

**Deliverable:** A dashboard page showing a table of top 5 coins with their key metrics.

---

## Slice 7: Fetch Global Market Metrics
**Goal:** Add backend functionality to fetch global market data (total market cap, total volume) from CoinGecko.

**What can be tested:**
- Call an endpoint (e.g., `GET /api/global`) and receive global market stats
- Verify fields: total_market_cap, total_volume, btc_dominance
- Test error handling if API fails

**System parts touched:**
- Backend (new endpoint, API integration)

**Deliverable:** An endpoint returning global cryptocurrency market metrics.

---

## Slice 8: Frontend Shows Global Summary
**Goal:** Add a header section to the dashboard displaying global market metrics above the coin table.

**What can be tested:**
- Page shows global metrics at the top (market cap, volume, BTC dominance)
- Metrics are formatted with proper currency symbols and abbreviations (e.g., $1.2T)
- Layout is clear and readable

**System parts touched:**
- Frontend (UI layout, data display)

**Deliverable:** Dashboard with global summary header and coin table below.

---

## Slice 9: In-Memory Cache for Backend Data
**Goal:** Implement a simple in-memory cache in FastAPI so we don't hit CoinGecko on every request.

**What can be tested:**
- Make multiple requests to the same endpoint quickly
- Verify only the first request hits CoinGecko API (check logs)
- Subsequent requests return cached data
- Cache expires after a set time (e.g., 5 minutes)

**System parts touched:**
- Backend (caching logic, state management)

**Deliverable:** Backend with in-memory cache that reduces external API calls.

---

## Slice 10: Combined Summary Endpoint
**Goal:** Create a single `/api/summary` endpoint that returns both global metrics and coin list in one response.

**What can be tested:**
- Call `GET /api/summary` and receive both global stats and coin array
- Response structure is clean and well-organized
- Frontend can use this single endpoint instead of multiple calls

**System parts touched:**
- Backend (API design, data aggregation)

**Deliverable:** A unified endpoint that returns all dashboard data in one request.

---

## Slice 11: Frontend Auto-Refresh
**Goal:** Add automatic polling to the frontend so it refreshes data every 2 minutes without user action.

**What can be tested:**
- Open the dashboard and wait 2 minutes
- Data updates automatically without page reload
- Last updated timestamp changes
- No flickering or jarring updates (smooth transition)

**System parts touched:**
- Frontend (JavaScript polling, state updates)

**Deliverable:** Dashboard that automatically refreshes data on a timer.

---


Note: Slice 12 and 13 are Promotable later if needed

## Slice 12: Simple Database Storage (SQLite)
**Goal:** Replace in-memory cache with SQLite database to persist data between server restarts.

**What can be tested:**
- Backend stores coin data in SQLite on fetch
- Restart server and verify data is still available (from DB, not fresh API call)
- Database file exists and contains expected tables/records
- API endpoints read from database

**System parts touched:**
- Backend (database integration, data persistence)

**Deliverable:** Backend that stores and retrieves data from SQLite database.

---

## Slice 13: Background Task Updates Database
**Goal:** Implement a background task in FastAPI that periodically fetches fresh data from CoinGecko and updates the database.

**What can be tested:**
- Start server and wait for scheduled update (e.g., every 5 minutes)
- Verify database is updated with fresh timestamps
- Check logs to confirm background task runs
- Data in API responses reflects the latest update

**System parts touched:**
- Backend (background tasks, scheduling, database updates)

**Deliverable:** Automated data updates running in the background.

---

## Slice 14: Fetch Historical Price Data
**Goal:** Add functionality to fetch 30 days of historical price data for a coin from CoinGecko.

**What can be tested:**
- Call an endpoint or function with a coin ID
- Receive an array of historical prices (date, price pairs)
- Verify data spans approximately 30 days
- Data is in a usable format (JSON)

**System parts touched:**
- Backend (API integration, historical data handling)

**Deliverable:** Function/endpoint that returns 30 days of price history for a coin.

---

## Slice 15: Calculate 30-Day Volatility
**Goal:** Implement volatility calculation (standard deviation of daily returns) using the historical price data.

**What can be tested:**
- Pass historical price data to volatility function
- Receive a volatility percentage (e.g., 5.2%)
- Verify calculation is correct with known test data
- Handle edge cases (insufficient data, etc.)

**System parts touched:**
- Backend (data processing, mathematical calculation)

**Deliverable:** A function that calculates and returns 30-day volatility for a coin.

---

## Slice 16: Store and Serve Volatility in Summary
**Goal:** Integrate volatility calculation into the data pipeline: compute it during updates and include it in the summary endpoint.

**What can be tested:**
- Call `/api/summary` and see volatility_30d field for each coin
- Volatility values are reasonable (positive percentages)
- Values update when historical data refreshes
- Database stores volatility values

**System parts touched:**
- Backend (data pipeline, API response)

**Deliverable:** Summary endpoint includes volatility metrics for each coin.

---

## Slice 17: Frontend Displays Volatility
**Goal:** Add a volatility column to the coin table in the frontend.

**What can be tested:**
- Dashboard table shows a "30d Volatility" column
- Each coin displays its volatility percentage
- Column is properly formatted and aligned
- Data comes from the API response

**System parts touched:**
- Frontend (table rendering, data display)

**Deliverable:** Dashboard table includes volatility column.

---

## Slice 18: Calculate Correlation Between Two Coins
**Goal:** Implement a function that calculates Pearson correlation coefficient between two coins using their historical price data.

**What can be tested:**
- Pass historical data for two coins (e.g., BTC and ETH)
- Receive a correlation value between -1 and 1
- Verify calculation with known test data
- Handle cases where data is insufficient

**System parts touched:**
- Backend (data processing, statistical calculation)

**Deliverable:** A function that calculates correlation between two coin price series.

---

## Slice 19: Compute and Store Key Correlations
**Goal:** During background updates, calculate correlations (e.g., each top coin vs Bitcoin) and store them.

**What can be tested:**
- After background update runs, check database/logs for correlation values
- Correlations are computed for expected pairs (e.g., BTC-ETH, BTC-SOL)
- Values are stored and accessible
- Correlations update when historical data refreshes

**System parts touched:**
- Backend (background processing, data storage)

**Deliverable:** System that computes and stores correlation metrics automatically.

---

## Slice 20: Correlation Endpoint
**Goal:** Create an endpoint that returns correlation data (e.g., `GET /api/correlations`).

**What can be tested:**
- Call the endpoint and receive correlation data
- Response includes pairs and their correlation values
- Data format is clear and usable by frontend
- Values are current (from latest computation)

**System parts touched:**
- Backend (API endpoint)

**Deliverable:** Endpoint returning correlation matrix or list of correlations.

---

## Slice 21: Frontend Displays Correlations
**Goal:** Add a correlation section to the dashboard showing key correlations (e.g., BTC vs other coins).

**What can be tested:**
- Dashboard shows a correlation section (table or list)
- Displays correlations like "BTC-ETH: 0.85"
- Section updates with auto-refresh
- Formatting is clear and readable

**System parts touched:**
- Frontend (UI component, data rendering)

**Deliverable:** Dashboard includes a correlation display section.

---

## Slice 22: Error Handling in Backend
**Goal:** Add proper error handling for API failures, network issues, and invalid data.

**What can be tested:**
- Simulate CoinGecko API failure (wrong URL, network down)
- Backend returns appropriate error response (not crashes)
- Logs show error details
- Frontend receives error status and can handle it
- Database retains last known good data

**System parts touched:**
- Backend (error handling, resilience)

**Deliverable:** Robust backend that handles failures gracefully.

---

## Slice 23: Frontend Error Handling and Loading States
**Goal:** Add loading indicators and error messages to the frontend for better UX.

**What can be tested:**
- Show loading spinner while fetching data
- Display error message if API call fails
- Show "data stale" warning if last update is too old
- UI remains functional even when backend is down

**System parts touched:**
- Frontend (UX, error handling, state management)

**Deliverable:** Frontend with proper loading and error states.

---

## Slice 24: Responsive Design and Styling
**Goal:** Make the dashboard look clean and work well on mobile devices.

**What can be tested:**
- Dashboard looks polished with proper styling
- Table is readable with good contrast and spacing
- Page works on mobile (table scrolls or stacks appropriately)
- Numbers are formatted nicely (commas, abbreviations)
- Color coding for positive/negative changes works

**System parts touched:**
- Frontend (CSS, responsive design, formatting)

**Deliverable:** Polished, mobile-friendly dashboard UI.

---

## Slice 25: Last Updated Timestamp Display
**Goal:** Show when data was last updated in the UI and include it in API responses.

**What can be tested:**
- Dashboard displays "Last updated: [timestamp]"
- Timestamp updates when new data arrives
- Format is human-readable (e.g., "2 minutes ago")
- API responses include last_updated field

**System parts touched:**
- Backend (timestamp tracking)
- Frontend (timestamp display, formatting)

**Deliverable:** Clear indication of data freshness in the UI.

---

## Summary

These 25 slices progress from the absolute basics (hello world server) to a complete MVP with:
- Automated data fetching and updates
- Multiple coins with prices, volumes, changes
- Global market metrics
- Volatility calculations
- Correlation metrics
- Polished, responsive UI
- Error handling and resilience

Each slice is:
- **Runnable/testable immediately** - you can verify it works right away
- **One clear functionality** - each adds a specific feature end-to-end
- **Small enough for one session** - focused and achievable
- **No premature abstractions** - build what's needed, when it's needed

The order ensures you always have something working, and each step builds naturally on the previous one.
