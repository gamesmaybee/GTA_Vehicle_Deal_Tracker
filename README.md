# GTA Online Car Deals

A dashboard showing this week's discounted vehicles, Luxury Autos, and Premium Deluxe Motorsport listings in GTA Online, with stats and images pulled from [gta.wiki](https://gta.wiki).

## How it works

- `scraper.py` — fetches the weekly sticky post from r/gtaonline, parses vehicles, then pulls images, prices, stats and store info from gta.wiki
- `data.json` — the scraped data served as a static file
- `index.html` / `style.css` / `app.js` — the frontend, hosted on GitHub Pages

## Running locally

**Requirements:** Python 3.9+

```bash
pip install requests beautifulsoup4
python scraper.py data.json
```

Then open `index.html` in your browser. You'll need to serve it locally due to CORS:

```bash
python -m http.server 8080
```

Then visit `http://localhost:8080`.

## Updating the data

Run the scraper to regenerate `data.json` with the latest weekly deals:

```bash
python scraper.py data.json
```

GTA Online resets every Wednesday, so that's when you'd want to re-run it.

## Data sources

- Weekly deals — [r/gtaonline](https://reddit.com/r/gtaonline)
- Vehicle stats & images — [gta.wiki](https://gta.wiki)
- Fallback data — [GTA Fandom Wiki](https://gta.fandom.com)