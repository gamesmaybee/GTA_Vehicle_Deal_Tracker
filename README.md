# GTA Online Car Deals

A dashboard showing this week's discounted vehicles, Luxury Autos, and Premium Deluxe Motorsport listings in GTA Online, with stats and images pulled from [gta.wiki](https://gta.wiki).

🌐 **Live site:** [your-username.github.io/GTA_Vehicle_Deal_Tracker](https://gamesmaybee.github.io/GTA_Vehicle_Deal_Tracker/)

---

## How it works

- `scraper.py` — fetches the latest weekly update article from [RockstarINTEL](https://rockstarintel.com), parses discounted vehicles, Luxury Autos and PDM listings, then pulls images, prices, stats and store info from [gta.wiki](https://gta.wiki)
- `data.json` — the scraped data served as a static file
- `index.html` / `style.css` / `app.js` — the frontend, hosted on GitHub Pages

## Updating

GTA Online resets every Wednesday. To update the site:

1. Open a terminal with Python available
2. Navigate to the project folder
3. Run `python scraper.py data.json`
4. Commit and push `data.json`

The live site updates within a minute of pushing.

## Local setup

**Requirements:** Python 3.9+

```bash
pip install requests beautifulsoup4
python scraper.py data.json
python -m http.server 8080
```

Then open `http://localhost:8080` in your browser.

## Data sources

- Weekly deals — [RockstarINTEL](https://rockstarintel.com)
- Vehicle stats & images — [gta.wiki](https://gta.wiki)
- Fallback data — [GTA Fandom Wiki](https://gta.fandom.com)