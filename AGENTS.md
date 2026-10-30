# Guide for AI agents

This file tells AI coding agents (Claude, Codex, Copilot and others) how to work on this repository. Humans can use it too. Read [PLAN.md](PLAN.md) first: it holds the product decisions, the data model and the phases.

## 1. The product in short

- An online store for Pakistan. It sells Dubai auction items and export leftovers.
- Payment is **Cash on Delivery only**. There is no payment gateway. A large item can need an advance, which the customer pays by bank transfer and proves with a screenshot.
- Currency is **PKR only**. Language is **English only**. Time zone is `Asia/Karachi`.
- **No paid services** (no SMS gateway, no paid WhatsApp API, no paid SaaS) unless the owner approves them.
- The owner and staff work in the **staff portal** at `/staff/` (`apps/portal`). The Django admin is only a hidden fallback for the owner (superusers only). **A new category, attribute, fee or page must never need a code change.**

## 2. Tech stack

| Part | Choice |
|---|---|
| Backend | Python 3.12, Django 5.2 LTS |
| Frontend | Django templates, HTMX 2, Alpine.js 3, Tailwind (CDN browser build for the test UI) |
| Database | PostgreSQL 16 |
| Static files | WhiteNoise |
| App server | Gunicorn |
| Audit log | `django-simple-history` |
| Tests | pytest, pytest-django, factory_boy |
| Lint and format | ruff |
| Hosting | Docker Compose on PetHost (`pethost.compose.yaml`, see DEPLOY.md) |

Do not add Node, a SPA framework, Redis, Celery or a paid service without the owner's approval.

## 3. Repository layout

```
config/            Django project: settings (base, dev, test, prod), urls, wsgi
apps/core/         Home, pages, health check, roles, dashboard, staff activity, seed_demo
apps/catalog/      Categories, attributes, products, variants, tiers, pricing.py, search.py, importer.py
apps/inventory/    Lots, stock items, stock movements, services.py (all stock changes)
apps/shipping/     Shipping settings (single row), cities, services.quote()
apps/cart/         Session cart (cart.py) and cart views
apps/orders/       Orders, services.place_order(), workflow.transition(), notifications, admin
apps/portal/       Staff portal: access.py (permissions and menu), views/, forms.py, history.py (audit)
apps/accounts/     Login by phone, signup, account page, order tracking, wholesale buyers
apps/<name>/tests/ Tests for that app
templates/         Site-wide templates (base.html, partials/)
apps/<name>/templates/<name>/  App templates
static/            Site-wide static files
docker/            Container entrypoint, Caddyfile and backup script for production
PLAN.md            Product plan and phases
```

## 4. Run it

With Docker:

```bash
cp .env.example .env
docker compose up --build
docker compose exec web python manage.py createsuperuser
docker compose exec web pytest
```

Without Docker, you need a PostgreSQL database and `DATABASE_URL` in `.env`:

```bash
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py runserver
```

## 5. Before every commit

Run all 3 checks. CI runs the same checks on every pull request.

```bash
ruff check . && ruff format --check .
python manage.py makemigrations --check --dry-run
pytest
```

## 6. Git workflow (required)

1. Each phase gets a branch from `main`: `phase-N/short-name`.
2. Each task in a phase gets a sub-branch from the phase branch: `phase-N/short-name--task-name`.
3. A task branch merges into its phase branch through a pull request.
4. When all tasks of the phase are done and tested, the phase branch merges into `main` through a pull request.
5. Do not commit directly to `main`. Do not rewrite history on shared branches.

Commit messages: an imperative summary line ("Add price tiers to variants"), then details if needed.

## 7. Code rules

### Business logic

- Put business logic in `services.py` (or a model method), **not** in views or templates. Views read input, call a service and render. This keeps the logic ready for the real UI later.
- Money is `DecimalField(max_digits=12, decimal_places=0)` in whole rupees. Never use `float` for money. Show money with the `rupees` filter: `{{ price|rupees }}`.
- An order stores copies (snapshots) of names, prices and the address. Later changes to a product must not change old orders.
- Stock changes only through a stock service that writes a `StockMovement` row with the user and the reason. Use `select_for_update()` inside a transaction when you reserve stock.
- Order status changes only through the order service, which checks the allowed transitions and writes the history.
- Never trust prices or totals from the browser. Calculate them again on the server.
- Customers never see a product without stock (`Product.objects.listed()`), because most items are one-off pieces. Staff see stock levels through `apps.inventory.levels` (near empty, out of stock).

### Staff portal first

- Every model that staff or the owner manage has a page in the staff portal (`apps/portal`). Simple models use the `Crud` class in `apps/portal/views/simple.py`. Protect each view with `portal_view(perm)` and add it to `MENU` in `apps/portal/access.py`.
- Keep the Django admin registrations working as the owner's fallback, but do not build new staff features there.
- Add `HistoricalRecords()` (django-simple-history) to every model that staff edit, so the owner sees who changed what.
- Staff do not delete. Use `is_active` to hide. Only the owner (superuser) deletes.
- When a new model needs staff access, add its permissions to `apps/core/roles.py`. `manage.py setup_roles` runs at container start.
- Sensitive actions use custom permissions (for example `view_cost_and_profit`, `change_price`, `adjust_stock`). Check them in the portal views and in services.

### Templates, HTMX and Alpine

- The current UI is a **throwaway test UI**. Keep templates simple and logic-free. Do not spend time on design.
- Use HTMX for server calls (add to cart, filters, form updates). Return a partial template for HTMX requests (`request.htmx` from `django-htmx`).
- Use Alpine only for small client-side state (menus, galleries, show/hide).
- Pin every CDN script to an exact version.

### Style

- Follow ruff (line length 100). Use clear names. Add a docstring when the reason for the code is not obvious.
- Keep settings in `config/settings/`. Read secrets and environment values from `.env` with `django-environ`. Never commit `.env` or a secret.

## 8. Tests

- Each app has a `tests/` folder. Use pytest functions and `factory_boy` factories.
- Test every service: prices and tiers, MOQ, stock reserve and release, order status changes, fees.
- Test the main views with the Django test client, including HTMX requests (`HTTP_HX_REQUEST="true"`).
- A bug fix comes with a test that fails before the fix.

## 9. Key entry points

| Need | Use |
|---|---|
| Price for a quantity | `apps.catalog.pricing.unit_price()` and `quantity_error()` |
| Change stock | `apps.inventory.services` (`receive`, `reserve`, `release`, `dispatch`, `return_to_stock`, `adjust`) |
| Delivery and COD fees | `apps.shipping.services.quote()` |
| Create an order | `apps.orders.services.place_order()` |
| Change an order status | `apps.orders.workflow.transition()` |
| Tell the owner or customer | `apps.orders.notifications` |
| Demo data | `manage.py seed_demo` (never on the live store) |

## 10. Things to avoid

- Do not hard-code categories, attributes, cities, fees or bank details. They are data in the staff portal.
- Do not add a feature that needs a paid service.
- Do not change a migration that is already on `main`. Add a new migration.
- Do not remove or skip a failing test to make CI pass. Fix the cause.
