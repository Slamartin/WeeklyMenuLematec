# Weekly Lunch Menu Aggregator

This project scrapes the current weekly lunch menus from:

- Bistro 22
- Cookpoint

It exposes a JSON API at `/menu` and serves a small responsive frontend from the same FastAPI app.

## Stack

- Backend: FastAPI
- Frontend: plain HTML, CSS, and JavaScript
- Scraping: `requests`, `BeautifulSoup`, `pdfplumber`

## Features

- Aggregates both menus into a single normalized JSON response
- Parses Bistro 22 from HTML
- Detects Cookpoint's latest weekly PDF and extracts text from it
- Caches results for 6 hours
- Responsive UI with:
  - current day highlight
  - weekly day tabs
  - today-only toggle
  - loading state
  - partial failure warnings

## Run locally

1. Create a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Start the app:

   ```powershell
   uvicorn app.main:app --reload
   ```

4. Open:

   [http://127.0.0.1:8000](http://127.0.0.1:8000)

## API shape

`GET /menu`

Example response:

```json
{
  "bistro22": {
    "monday": ["Soup", "Main dish"],
    "tuesday": []
  },
  "cookpoint": {
    "monday": ["Soup", "Main dish"],
    "tuesday": []
  },
  "_meta": {
    "generatedAt": "2026-04-14T08:00:00+00:00",
    "cacheTtlHours": 6,
    "weekLabel": "09.03.2026 - 13.03.2026",
    "sourceWeekLabels": {
      "bistro22": "09.03.2026 - 13.03.2026",
      "cookpoint": "09.02. - 13.02.2025"
    },
    "errors": {}
  }
}
```

## Docker

Build:

```powershell
docker build -t weekly-menu .
```

Run:

```powershell
docker run --rm -p 8000:8000 weekly-menu
```

## Deploy to Render

1. Push this project to a GitHub repository.

2. Sign in to [Render](https://render.com/) and choose `New +` -> `Blueprint`.

3. Connect your GitHub repository.

4. Render will detect [`render.yaml`](./render.yaml) and create one free web service with:

   - build command: `pip install -r requirements.txt`
   - start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

5. Confirm the deploy and wait for the build to finish.

6. Open the generated Render URL. The homepage serves the frontend, and `/menu` returns JSON.

### Notes for free hosting

- The free Render instance may sleep after inactivity, so the first request can take a little longer.
- No database or external storage is required for this project.
- The 6-hour cache is in memory, so it resets whenever the service restarts or sleeps.

## Notes

- The source websites control the menu formatting. If they change markup or PDF layout significantly, parser updates may be needed.
- The FastAPI service keeps running even if one source fails, and returns the other source together with an error message in `_meta.errors`.
