# cartracker

Local price tracker and "should I buy this?" tool for used vehicles of a single
model (default config: Toyota Tacoma). It stores listings in SQLite, fits two
price models (linear regression + gradient boosting) on year / mileage / trim /
drivetrain / cab style / engine, and runs a Streamlit dashboard so you can
compare a prospective purchase against the predicted price.

The parser is tuned to a specific used-vehicle marketplace's page shape (it
looks for inline JSON arrays of listing objects with `vin`, `basePrice`,
`stockNumber`, etc. fields). It works on saved HTML pages or HAR network
exports — not by hitting the site directly.

## Setup (macOS / Linux)

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Setup (Windows)

1. Install Python 3.11+ from https://www.python.org/downloads/. **Check
   "Add python.exe to PATH"** in the installer.
2. Copy this project folder to the Windows machine (zip + extract,
   `git clone`, OneDrive — whatever's easiest).
3. Double-click `setup.bat`. It creates `.venv\` and installs all dependencies.
4. Drop your saved listing `.har` (or `.html` / `.json`) files into `data\raw\`.
5. Double-click `ingest.bat` — wipes any existing database and reloads from
   `data\raw\`. Run this whenever you save more listing data.
6. Double-click `run.bat` — launches the dashboard at http://localhost:8501.
   (`run.bat` will auto-run ingest if no database exists yet.)

The same `.bat` files work from `cmd.exe` or PowerShell if you prefer the terminal.

## Quick start (synthetic data)

```sh
python ingest.py seed          # writes 200 synthetic Tacoma listings
streamlit run app.py
```

The synthetic generator is just so the dashboard has something to show on
day one. Replace it with real listings as soon as you can.

## Loading real listings

This tool intentionally takes a manual-save approach — it parses pages or
network captures you save yourself, rather than hitting the source site
directly. There are two equally good capture paths.

**Path A — save the HTML page (simple, ~24 listings per save).**

1. In your browser, open the source site's search results page filtered for
   the model and area you care about.
2. ⌘S (Cmd+S) → choose **Page Source** (not Web Archive). Save into `data/raw/`.
3. Repeat for additional searches (different price bands, different cities)
   so the dataset has variety.

**Path B — export a HAR after scrolling (richer, hundreds of listings per save).**

1. Open the search results page. Open your browser's developer tools
   (Web Inspector / DevTools) → **Network** tab. Filter for `Fetch / XHR`.
2. Reload the page, then scroll the results until you've loaded as many
   listings as you want.
3. Right-click in the request list → **Export HAR** (or use the export icon
   in the Network toolbar). Save into `data/raw/`.

Then ingest:

```sh
python ingest.py html data/raw
```

The parser walks each file looking for inline JSON arrays of listing objects
and extracts them by VIN. Re-running is idempotent — listings are upserted by
VIN, so prices update if you re-save the same page later.

After ingest, reload the Streamlit app (use the "Reload from DB" button in the
sidebar, or just rerun the page). Models retrain automatically.

## Using the dashboard

- **Data** — distribution of price vs mileage and price vs year × trim, plus
  the raw table. Click a dot on the scatter to get a link to the original
  listing.
- **Model** — cross-validated MAE/R² for both models, linear coefficients
  (interpretable: $/mile, $/year, trim premiums), and GBM feature importances.
- **Score a listing** — enter a vehicle's year, mileage, trim, etc. and an
  asking price. The app reports the linear and GBM predictions, the delta vs
  asking, and the closest comps in the database (each with a link to the
  original listing).

A "below predicted" verdict is a hint, not a green light — verify accident
history, service records, tire condition, and frame in person.

## Layout

```
cartracker/
├── app.py                  # Streamlit dashboard
├── ingest.py               # CLI: seed | html
├── requirements.txt
├── setup.bat / ingest.bat / run.bat   # Windows installer scripts
├── cartracker/
│   ├── db.py               # SQLite schema + upsert
│   ├── parse.py            # Saved listing pages → vehicle records
│   ├── seed.py             # Synthetic Tacoma generator
│   └── model.py            # Linear + GBM training, prediction
└── data/
    ├── cars.db             # Created on first ingest
    └── raw/                # Drop saved listing files here (gitignored)
```

## Switching to a different model (e.g. 4Runner)

Two things to change:

- `app.py` — set `MODEL_FILTER` to the new model name.
- `cartracker/seed.py` — adjust trims, drivetrains, MSRP base prices.

The DB schema and parser are model-agnostic.

## Notes on data sources

The parser is designed for a specific used-vehicle marketplace's page layout
(field names like `stockNumber`, `basePrice`, `engineSize`, etc.). Adapting it
to a different site means rewriting `cartracker/parse.py`'s `_normalize` and
`_looks_like_vehicle` helpers; the DB schema, model code, and Streamlit
dashboard don't need to change.

This tool is for personal purchase-decision support. Respect the terms of
service of any site you save pages from, and don't redistribute saved
listing data.
