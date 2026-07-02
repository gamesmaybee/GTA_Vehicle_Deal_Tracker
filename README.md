# GTA Online Car Deals

A dashboard showing this week's discounted vehicles, Luxury Autos, and Premium Deluxe Motorsport listings in GTA Online, with stats, images and deal info pulled from multiple sources.

🌐 **Live site:** [your-username.github.io/GTA_Vehicle_Deal_Tracker](https://your-username.github.io/GTA_Vehicle_Deal_Tracker)

---

## How it works

- `scraper.py` — fetches the latest weekly update article from [RockstarINTEL](https://rockstarintel.com), parses discounted vehicles, Luxury Autos and PDM listings, then pulls images from [gta.wiki](https://gta.wiki) and price/store data from the wiki and Broughy's CSVs
- `broughy.py` — loads Broughy1322's vehicle data CSVs and provides stat lookups (top speed, lap time, drivetrain, seats)
- `data.json` — the scraped data served as a static file
- `index.html` / `style.css` / `app.js` — the frontend, hosted on GitHub Pages

## Updating

GTA Online resets every Thursday. To update the site:

1. Open a terminal with Python available
2. Navigate to the project folder
3. Run `python scraper.py data.json`
4. Commit and push `data.json`

The live site updates within a minute of pushing. A GitHub Actions workflow also runs automatically every Thursday at 10am UTC.

## Local setup

**Requirements:** Python 3.9+

```bash
pip install requests beautifulsoup4
```

Place Broughy1322's CSV files in a `data/` folder (can be found on [this spreadsheet](https://docs.google.com/spreadsheets/d/1nQND3ikiLzS3Ij9kuV-rVkRtoYetb79c52JWyafb4m4/edit?gid=1299124236#gid=1299124236)):
- `data/speed_tiers.csv`
- `data/vehicle_info.csv`
- `data/handling_data.csv`

Then run:
```bash
python scraper.py data.json
python -m http.server 8080
```

Open `http://localhost:8080` in your browser.

## Data sources

- Weekly deals — [RockstarINTEL](https://rockstarintel.com)
- Vehicle images — [gta.wiki](https://gta.wiki)
- Vehicle stats (top speed, lap time, drivetrain, seats) — [GTACars.net](https://gtacars.net) by [Broughy1322](https://www.youtube.com/@Broughy1322)