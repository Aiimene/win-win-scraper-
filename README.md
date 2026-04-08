# WinWin.com Article Scraper

A Python scraper that extracts articles from [winwin.com](https://winwin.com) for a given date and saves them to a CSV file.

## Requirements

- Python 3.8+
- Google Chrome installed

## Installation

```bash
pip install selenium webdriver-manager
```

## Usage

```bash
# Scrape today's articles
python scraper.py

# Scrape a specific date
python scraper.py --date 2026-04-07
python scraper.py -d 2026-04-06
```

The date format is `YYYY-MM-DD`.

## Output

The scraper generates `winwin_articles.csv` with the following columns:

| Column      | Description                        |
|-------------|------------------------------------|
| title       | Article title                      |
| description | Article summary or body excerpt    |
| image_url   | Main article image URL             |
| category    | Sport category (Football, Tennis…) |

## Categories

The scraper covers these sections:

- **Football** — News, leagues, teams
- **Tennis**
- **Basketball**
- **Motorsport**

## How It Works

1. Launches headless Chrome
2. Discovers articles across all categories
3. Scrolls pages to load dynamic content (infinite scroll)
4. Filters articles matching the target date
5. Extracts title, description, image, and category from each article
6. Saves clean UTF-8 CSV
