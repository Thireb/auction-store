# Auction Store

An online store for the Pakistani market. It sells Dubai auction items and export leftovers: furniture, mobile accessories, decor, shoes, watches and more. Customers buy single pieces or bulk quantities. Payment is Cash on Delivery (COD) only.

> Status: phases 1 to 6 are built. See [PLAN.md](PLAN.md) for the plan and [DEPLOY.md](DEPLOY.md) to put the store online.

## Features

- Catalog with categories, product variants and image galleries.
- Bulk price tiers, minimum order quantity (MOQ) and approved wholesale buyers.
- Stock per auction lot, with a full stock movement history.
- Cart and 1-page COD checkout. Guest checkout, with an optional "Create an account" checkbox.
- Configurable delivery and COD fees per city. Optional advance payment for large items.
- Order flow with phone confirmation, status history and printable packing slips.
- Staff portal at `/staff/`. The owner creates staff accounts and sees an audit log of all staff changes. The Django admin stays as a hidden fallback for the owner.

## Tech stack

- Python 3.12, Django 5.2 LTS
- HTMX and Alpine.js for interactivity
- Tailwind CSS (CDN for the test UI)
- PostgreSQL 16
- WhiteNoise for static files, Gunicorn as the app server
- Docker Compose for local development and for hosting on PetHost
- pytest, factory_boy and ruff for tests and lint

## Local development

You need Docker with Docker Compose.

1. Copy the example environment file and edit the values:

   ```bash
   cp .env.example .env
   ```

2. Start the app and the database. The app applies migrations and creates the staff roles at start:

   ```bash
   docker compose up --build
   ```

3. Create the owner account (a superuser):

   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

4. Optional: add demo categories, products and images:

   ```bash
   docker compose exec web python manage.py seed_demo
   ```

5. Open http://localhost:8000 for the store and http://localhost:8000/staff/ for the staff portal.

Without Docker: create a PostgreSQL database, set `DATABASE_URL` in `.env` to it, then run `pip install -r requirements-dev.txt`, `python manage.py migrate` and `python manage.py runserver`.

## Tests and lint

```bash
docker compose exec web pytest
docker compose exec web ruff check .
docker compose exec web ruff format --check .
```

## Working with AI agents

AI coding agents follow [AGENTS.md](AGENTS.md).

## Git workflow

1. Each phase gets a branch from `main`, for example `phase-1/foundation`.
2. Each task in a phase gets a sub-branch from the phase branch, for example `phase-1/foundation--settings`.
3. A task branch merges into its phase branch through a pull request.
4. When all tasks of a phase are done and tested, the phase branch merges into `main`.

## Staff portal (/staff/)

- **Dashboard**: orders to confirm, advances to check, orders to dispatch, COD cash, sales, profit (owner), near-empty and out-of-stock counts. A bell in the header lists near-empty items.
- **Orders**: status tabs, call and WhatsApp buttons, status changes with notes and courier, advance screenshot and "Mark advance received", address edit until dispatch, print slip. **Wholesale buyers**: approve or reject. **Blocked phones**.
- **Catalog**: products with photos (many at once), attributes from the category, variants, and stock received on the same page. Categories (tree), attributes, brands.
- **Stock**: stock levels, **Near empty**, **Out of stock** (hidden from customers), stock movements, lots, CSV import. Each variant page has bulk prices, receive or adjust stock, stock by lot and history.
- **Store settings**: fees, advance rules, payment details and the store-wide "near empty" number; cities; pages.
- **Owner**: staff accounts with roles ("Inventory manager", "Order manager") and extra permissions; staff activity.

Every page checks the same Django permissions. The owner (superuser) sees everything.

## Deployment

See [DEPLOY.md](DEPLOY.md).
