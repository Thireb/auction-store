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
- Django admin back office. The owner creates staff accounts and sees an audit log of all staff changes.

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

5. Open http://localhost:8000 for the store and http://localhost:8000/admin/ for the back office.

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

## Back office (admin)

- **Admin home**: shortcuts to the dashboard, staff activity, stock view, low stock and orders to confirm.
- **Catalog**: categories, attributes (define them per category, no code needed), brands, products with variants, images and price tiers. Products > **Import CSV** for bulk uploads.
- **Stock**: Stock movements > Add to receive or adjust stock. Lots hold auction purchases and costs.
- **Orders**: status buttons, call and WhatsApp links, print slip, advance check.
- **Shipping and payment settings** and **Cities**: all delivery fees and advance rules.
- **Pages**: About, Delivery information, FAQ, Contact.
- **Users and groups**: the owner creates staff accounts and puts them in the "Inventory manager" or "Order manager" group.

## Deployment

See [DEPLOY.md](DEPLOY.md).
