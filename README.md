# Penny Hunt

A local Flask web app for searching coin rolls. You buy $0.50 rolls (or $25 boxes), flip the coins one at a time, keep or return each one, fill an album, and send coins to PCGS to get their real grade.

## Running it

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000. Your progress is saved in `pennyhunt.db`. Delete that file to start over with $50.00.

## Files

| File | What it does |
|---|---|
| `config.py` | Every number you can tune: prices, odds, grading fees, key dates |
| `distribution.py` | Decides which coin you get (mintage weight, wheat rerolls, varieties, specials, grade) |
| `grading.py` | The PCGS grade list, grade labels, and your fuzzy grade estimate |
| `catalog.py` | Loads the CSV files |
| `db.py` | The SQLite save file, plus the logic that picks book coins vs jar coins |
| `app.py` | Flask routes (the web pages and actions) |
| `templates/` | HTML pages (Jinja) |
| `static/open.js` | Coin flipping and the keep/return buttons |
| `static/style.css` | All styling |
| `data/pennyfigures.csv` | Your original file, extended through 2025 (IDs 278-285) |
| `data/varieties.csv` | Common varieties that split a date (1960 and 1970-S small/large date, 1982 copper/zinc) |
| `data/specials.csv` | The rare "special bucket": proofs, major errors, 2026 collector-only cents |

## Fixes from the C++ version

- Wheat cents that survived the reroll are now counted. In the old code they never were.
- Era rules use the year, not the ID, so 1940-P now gets the 80% rate.
- Grades are clamped to 1-70 and snapped to real PCGS grades. Each coin's grade is saved.
- Blank lines in the CSV no longer crash the loader.

## Placeholder numbers to replace

- Most proof weights in `specials.csv` are a placeholder value of 30. Only 2022-2025 use real mintages.
- All error-coin weights, and the `share` values in `varieties.csv`, are rough starting guesses.
- Weights in `specials.csv` only compete with each other. How often the special bucket triggers is set by `SPECIAL_CHANCE` in `config.py`.
