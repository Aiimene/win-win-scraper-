# WinWin.com Article Scraper

A scraper that extracts articles from [winwin.com](https://winwin.com) for a given date and saves them to a CSV file. Available in both **Python** and **Node.js**.

## Requirements

- Google Chrome installed

### Python version
- Python 3.8+
- `pip install selenium webdriver-manager`

### Node.js version
- Node.js 18+
- `npm install`

## Usage

### Python
```bash
# Scrape today's articles
python scraper.py

# Scrape a specific date
python scraper.py --date 2026-04-07
python scraper.py -d 2026-04-06
```

### Node.js
```bash
# Scrape today's articles
node scraper.js

# Scrape a specific date
node scraper.js --date 2026-04-07
node scraper.js -d 2026-04-06
```

The date format is `YYYY-MM-DD`. Defaults to today if not provided.

## Output

Generates `winwin_articles.csv` with the following columns:

| Column      | Description                                |
|-------------|--------------------------------------------|
| title       | Article title                              |
| description | Article summary or body excerpt            |
| image_url   | Main article image URL                     |
| date        | Publication date (Arabic format from site) |
| category    | Sport category (Football, Tennis…)         |

## Categories

The scraper covers these sections:

- **Football** — News, leagues, teams
- **Tennis**
- **Basketball**
- **Motorsport**

## How It Works

1. Launches headless Chrome
2. Discovers articles across all sport categories
3. Scrolls pages to load dynamic content (infinite scroll)
4. Filters articles matching the target date
5. Extracts title, description, image, date, and category from each article
6. Translates Arabic categories to English
7. Saves clean UTF-8 CSV

## Performance

| Version | Speed   | Notes                          |
|---------|---------|--------------------------------|
| Node.js | ~3 min  | Puppeteer, faster Chrome comms |
| Python  | ~30 min | Selenium + WebDriverManager    |

The Node.js version is recommended for faster scraping.
