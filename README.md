# nq7vmk

Pilot web app for a UK energy-utility day-ahead desk: **which national wind forecast was actually available at the GB 09:20 auction gate**, and **how accurate that vintage was** versus metered outturn.

Scope is January 2026 delivery, national wind only, from Elexon BMRS:

- Actuals: [FUELHH stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream), `fuelType=WIND`
- Forecasts: [WINDFOR stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream)

## Live app

- Production: https://nq7vmk.vercel.app
- Inspect: https://vercel.com/self-c154/nq7vmk

## What the product does

GB 60-minute day-ahead (EPEX) closes at **09:20 UK clock time on D-1**. NESO/Elexon refresh WINDFOR several times per day. Using the “latest” forecast after that gate would show the desk information it did not have when bidding.

For each January 2026 delivery day the app:

1. Takes every WINDFOR publish covering that day.
2. Keeps only publishes **strictly before 09:20 Europe/London on D-1**.
3. Uses the latest remaining vintage as the decision forecast.
4. Aligns it to FUELHH WIND by averaging the two 30-minute outturn periods in each hour.
5. Reports MAE, RMSE, bias, MAPE, P50/P90 |error|, energy gap (GWh), hit-rates within ±500 / ±1,000 MW, error by hour, by day, and by actual wind tercile.

**Error sign:** `forecast − actual`. Positive bias means wind was over-forecast, so buying the residual 1:1 against the raw forecast would leave the book short of wind.

Persistent bias can mix meteorological error with any coverage difference between WINDFOR (ESO-visible metered wind) and FUELHH WIND (BM fuel-type outturn). The app does not silently “correct” that; it shows the series the desk would actually observe on BMRS.

## Repository layout

```
backend/
  app/
    main.py           FastAPI routes
    elexon.py         BMRS HTTP client
    processing.py     Gate cutoff, vintage pick, hourly alignment
    metrics.py        Accuracy stats and trading notes
    store.py          Cache load + decision/overview payloads
    ingest.py         Rebuild backend/data/processed.json from Elexon
    config.py         January 2026 window and 09:20 gate
  data/processed.json Frozen January 2026 extract (runtime does not call Elexon)
  tests/              Vintage and metric unit tests
frontend/             React + TypeScript (Vite) desk UI
docker/Dockerfile     Production image: builds UI, serves it from FastAPI
docker-compose.yml
vercel.json
```

## How to start

### Docker (recommended)

```bash
docker compose up --build
```

Open http://localhost:8000

### Local (two processes)

Python 3.10+ and Node 20+.

```bash
# terminal 1 — API
cd backend
python -m pip install -r requirements.txt
python -m pytest -q
uvicorn app.main:app --reload --port 8000

# terminal 2 — UI (proxies /api to port 8000)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Refresh the Elexon cache

Only needed if you want to rebuild January 2026 from the live API:

```bash
cd backend
python -m app.ingest
```

## Deploy

### Vercel (frontend + Python `/api`)

The repo is set up for Vercel: static UI from `frontend/dist`, FastAPI behind `api/index.py`.

```bash
npx vercel --prod
```

Include `backend/data/processed.json` in the deployment (it is committed).

### Docker on Heroku (or any container host)

```bash
heroku container:login
heroku create <app>
heroku stack:set container
heroku container:push web
heroku container:release web
```

Set `PORT` from the platform; the image already reads it.

## AI tools

Cursor (Grok) was used to research Elexon/BMRS and EPEX GB gate timing, write the FastAPI + React app, Docker/Vercel wiring, and tests. Domain choices (09:20 vintage rule, hourly alignment, error metrics) were implemented explicitly in `backend/app/processing.py` and `backend/app/metrics.py` so they can be reviewed without relying on the chat.

## Demo video

Record an unlisted YouTube video (max 10 minutes) with two halves. Suggested beats:

**Part 1 — client (≤5 min):** problem (DA buy vs weather-driven wind); 09:20 gate; pick a January day; show the vintage used vs later unused publishes; forecast vs outturn and P90 band; switch to Forecast skill and walk MAE/bias/energy gap and what it means for residual thermal/wholesale cover.

**Part 2 — tech lead (≤5 min):** architecture (ingest → processed.json → FastAPI → React); why not “latest WINDFOR”; alignment of HH vs hourly; tests; Docker; no extra data sources.

Paste the unlisted URL into the submission form after checking it in incognito.
