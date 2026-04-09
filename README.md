# GTA Online Car Deals Dashboard

A live dashboard that scrapes r/gtaonline weekly posts and displays discounted vehicles, Luxury Autos, and Premium Deluxe Motorsport listings with stats and images pulled from the GTA Fandom wiki.

## Files

```
gta-deals/
├── server.py     # Flask API server
├── scraper.py    # Reddit + Fandom wiki scraper
├── index.html    # Frontend
├── style.css     # Styles
├── app.js        # Frontend logic
└── README.md
```

## Setup

### 1. Install dependencies

```bash
pip install flask flask-cors requests beautifulsoup4 --break-system-packages
```

> No Reddit API key needed — uses the public JSON endpoint.

### 2. Run the server

```bash
python server.py
```

The server starts at `http://localhost:5000`.

### 3. Open the frontend

Open `index.html` in your browser. It connects to the local Flask server.

> If you hit CORS issues opening the HTML directly, serve it with:
> ```bash
> python -m http.server 8080
> ```
> Then visit `http://localhost:8080`.

## How it works

### Scraper (`scraper.py`)
1. Searches r/gtaonline for the latest weekly bonuses/discounts post using the public Reddit JSON API
2. Parses the post body using regex and line-by-line parsing to extract:
   - Discounted vehicles (with % off)
   - Law enforcement vehicle discounts
   - Luxury Autos showroom listings
   - Premium Deluxe Motorsport showroom listings
3. For each vehicle, queries the GTA Fandom wiki API for the page, then scrapes:
   - Vehicle image (from the infobox)
   - Stats (top speed, lap time, drive type, etc.)
   - Price
4. Marks vehicles as "Removed" if they appear in the known removed vehicles list

### Server (`server.py`)
- Flask app exposing:
  - `GET /api/deals` — returns cached deal data (refreshes every hour)
  - `POST /api/refresh` — force-clears cache and re-scrapes

### Frontend (`index.html` + `style.css` + `app.js`)
- Fetches data from the local API on load
- Three tab sections: Discounts / Luxury Autos / PDM
- Each vehicle card shows:
  - Vehicle image
  - Name
  - Discount badge (if discounted) + "Removed" badge (if removed from game)
  - Original price + sale price (or normal price)
  - Up to 4 key stats
  - Link to GTA Wiki page
- Refresh button to force re-scrape

## Removed Vehicles

The `REMOVED_VEHICLES` set in `scraper.py` contains known removed vehicles (no longer purchasable in-game). Update this list manually using the [r/gtaonline removed vehicles wiki](https://www.reddit.com/r/gtaonline/wiki/vehicles/removed_vehicles).

## Extending

- To add more vehicle stats, adjust `STAT_PRIORITY` in `app.js`
- To add more sections (e.g. podium vehicle, prize ride), extend `parse_showroom()` calls in `scraper.py` and add a new grid + nav button in `index.html`
- To deploy, replace `const API = "http://localhost:5000/api"` in `app.js` with your server URL
