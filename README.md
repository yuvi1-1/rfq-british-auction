# British Auction RFQ

An RFQ system with British auction bidding. Suppliers bid prices down, bids near the end
extend the auction, and the forced close time caps all extensions.

**Stack:** FastAPI, PostgreSQL, Celery + Redis, React + TypeScript, Docker Compose.

## Docs

- [High-level design](docs/HLD.md)
- [Database schema](docs/SCHEMA.md)
- [Both as PDF](docs/British-Auction-RFQ-Design.pdf)

## Running

```bash
docker compose up --build
```

- App: http://localhost:8080
- API docs: http://localhost:8000/docs

Demo data (a buyer, 5 suppliers and some auctions) is loaded on the first start. Use the user
switcher in the header to act as the buyer or one of the suppliers.

To reset the demo data:

```bash
docker compose exec api python -m app.seed --reset
```

## Features

- Create an RFQ with British auction settings: bid start, bid close, forced close, trigger
  window (X), extension (Y) and the trigger type
- Suppliers submit quotes: carrier, freight / origin / destination charges, transit time, validity
- Automatic extensions on bid received / any rank change / L1 change, never past the forced close
- Auction list with lowest bid, current close, forced close and status
- Auction details with ranking (L1, L2, ...), all bids, configuration and an activity log
  with the reason for each extension
- Live updates over WebSocket
- Also: award after closing, suppliers can't see competitors' names or prices, a metrics page,
  and a "Live demo" button that starts a short auction with bidding bots

## Local development

```bash
docker compose up -d db redis

cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload
uv run celery -A app.worker:celery_app worker -B --loglevel=INFO

cd frontend
npm install
npm run dev   # http://localhost:5173
```

## Tests

```bash
cd backend && uv run pytest     # needs the db container running
cd frontend && npm test
```

## Project structure

```
backend/
  app/auction/   auction rules (engine.py), services, queries
  app/api/       FastAPI routes
  app/worker.py  Celery tasks
  alembic/       migrations
  tests/
frontend/
  src/pages/     pages
  src/components/
  src/lib/       API client and helpers
docs/            HLD and schema
```
