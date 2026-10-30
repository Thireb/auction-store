# Auction Store: Project Plan

Status: **draft for review**. No code is written until Ahmad approves this plan.

## 1. Goal

Build an online store for the Pakistani market. The store sells Dubai auction items and export leftovers. Categories include furniture, mobile accessories, decor, shoes and watches (smart and analog). Customers buy single pieces or bulk quantities. Payment is Cash on Delivery (COD) only.

The first UI is minimal and only for tests. A real design comes later. So all templates stay simple, and business logic stays out of templates.

## 2. Tech stack

| Area | Choice | Reason |
|---|---|---|
| Backend | Django 5.2 LTS, Python 3.12 | Asked for. LTS gives security updates until April 2028. |
| Interactivity | HTMX + Alpine.js | Asked for. HTMX does server calls (add to cart, filters). Alpine does small client state (image gallery, quantity input). |
| CSS | Tailwind CSS from the CDN (Play CDN) for now | No Node build step. Replace with a compiled build when the real UI starts. |
| Database | PostgreSQL 16 | Good full-text search, safe row locks for stock, JSON fields. Runs as a container on PetHost. SQLite only for local tests if wanted. |
| Static files | WhiteNoise | Serves CSS/JS from Django with compression. No separate web server needed. |
| Media (product images) | Named Docker volume, served by a small Caddy or nginx container (or WhiteNoise-like view in phase 1) | Images must survive a deploy. Later option: Cloudflare R2 or S3 through `django-storages`. |
| Image handling | Pillow + `django-imagekit` (or `sorl-thumbnail`) | Makes thumbnails. Phone photos are large. |
| App server | Gunicorn | Standard for Django in a container. |
| Back office | Django admin, with `django-import-export` | Fast to build. CSV/Excel import for large auction lots. |
| Background jobs | None in phase 1. Later: `django-q2` or `huey` with the DB as broker | No Redis or Celery is assumed. Add only if WhatsApp/SMS sends need it. |
| Tests | `pytest`, `pytest-django`, `factory_boy` | Fast unit and view tests. |
| Lint and format | `ruff` | One tool for lint and format. |
| CI | GitHub Actions: ruff + pytest on every PR | Catches errors before a merge. |

**Suggestion:** keep the stack above. It fits Django + HTMX + Alpine well and needs no Node build. Do not use a SPA framework.

## 3. Hosting on PetHost

PetHost (the hosting connected to this account) runs **Docker Compose projects on one rented Linux machine**. It is not shared cPanel hosting. This removes the usual shared hosting limits:

- We can run PostgreSQL as its own container. No need for MySQL or SQLite.
- We can run Gunicorn. No Passenger or `.htaccess` setup.
- A free HTTPS address `<name>.<apps_domain>` is ready at once. A custom domain needs 1 CNAME record.

The PetHost rules that affect the design:

1. Only **named volumes** keep data across deploys. So the database and media images must be in named volumes.
2. Secrets (`SECRET_KEY`, DB password, WhatsApp token) go in the project `.env` file on PetHost. They never go in git or in `compose.yaml`.
3. Only 1 replica per service. One Gunicorn container with 2-4 workers is enough at the start.
4. No `container_name`, no writable bind mounts, no published ports for routed services.
5. Images build on the machine, so CPU, memory and disk are the plan limits. Keep the image small (`python:3.12-slim`).
6. Backups only work if backups are on for the machine. We also add a nightly `pg_dump` into a volume.

Planned services in `compose.yaml`:

```yaml
services:
  web:      # Django + Gunicorn + WhiteNoise, runs migrate and collectstatic on start
  db:       # postgres:16-alpine, volume pgdata
  media:    # caddy:alpine, serves the media volume read-only (optional, phase 7)
volumes:
  pgdata:
  media:
```

Note: the PetHost connection failed in this session, so I did not check the machine size yet. I check it before the deploy phase.

## 4. Data model

Apps: `catalog`, `inventory`, `cart`, `orders`, `shipping`, `accounts`, `core`.

### 4.1 Catalog

- **Category**: name, slug, parent (tree, 2 levels is enough), image, sort order, is_active.
- **Brand** (optional): name, slug.
- **Product**: title, slug, category, brand, description, condition (`new`, `open box`, `used - like new`, `used - good`, `damaged/as is`), origin note (for example "Dubai auction, lot 2024-17"), is_active, is_featured, created_at.
- **ProductImage**: product, image, alt text, sort order.
- **Attribute / AttributeValue**: free attributes per category (size, color, material, strap type). A JSON field on the product is a simpler first choice; we decide in phase 1.
- **Variant**: product, SKU, option values (for example size 42, black), price, compare-at price, weight. Each product has at least 1 variant. This keeps cart and stock logic the same for all items.

### 4.2 Bulk pricing and MOQ

- **PriceTier**: variant, min_quantity, unit_price. Example: 1-9 pcs at Rs 1,200, 10-49 at Rs 1,000, 50+ at Rs 850.
- **Variant.min_order_qty** (MOQ) and **Variant.order_step** (for example sold in packs of 12).
- The cart always calculates the unit price from the highest tier the quantity reaches.
- Optional (answer to question 3): **wholesale buyers**. A customer applies, an admin approves, and only approved buyers see wholesale tiers.

### 4.3 Lots and stock

- **Lot**: a purchase from an auction or exporter. Fields: reference, source (auction house, exporter), purchase date, total cost, landed cost (shipping, customs), notes. Used for cost and profit reports.
- **StockItem**: variant, lot, quantity_on_hand, quantity_reserved, cost_per_unit.
- **StockMovement**: variant, lot, change (+/-), reason (`received`, `order reserved`, `order cancelled`, `delivered`, `returned`, `adjustment`), order link, user, time. This is the audit trail. Stock numbers come from these rows.
- **One-off items** (a single sofa) are a variant with quantity 1. When sold, the product shows "Sold" and stays visible for a few days, then hides.

Stock rule: the store **reserves stock when the order is placed**. It releases stock when the order is cancelled or fails delivery. It uses `select_for_update` so two buyers cannot buy the last piece.

### 4.4 Customers

- Guest checkout with name, phone and address (most COD buyers in Pakistan expect this).
- Optional account: login by phone + password, or phone OTP later. Saves addresses and shows order history.
- **Address**: name, phone, city, area, street address, nearest landmark, postal code (optional).
- **Phone** is the main key. Store it in `+92 3XX XXXXXXX` format and validate it.

### 4.5 Shipping

- **City**: name, province, is_active, delivery_fee, cod_fee, estimated days, courier, is_cod_allowed.
- **ShippingRule** (optional): extra fee by weight or for bulky items (furniture). Free delivery above an order total.
- **Shipment**: order, courier, tracking number, booked_at, status. Phase 1 enters tracking numbers by hand. Courier APIs (PostEx, Leopards, TCS, Trax, M&P) come in a later phase.

### 4.6 Orders

- **Order**: number (for example `AS-24-000123`), customer or guest data, address snapshot, city, subtotal, delivery fee, COD fee, discount, total, status, confirmation status, notes, source (web, WhatsApp, phone), IP address, created_at.
- **OrderItem**: order, variant, title snapshot, unit price snapshot, quantity, line total. Prices are copied so later price changes do not change old orders.
- **OrderStatusHistory**: order, from status, to status, user, note, time.

## 5. COD order flow

```
pending_confirmation -> confirmed -> packed -> shipped -> delivered -> completed
        |                   |                     |
        v                   v                     v
   cancelled           cancelled        returned (refused / failed delivery)
```

| Status | Meaning | Stock |
|---|---|---|
| `pending_confirmation` | Customer placed the order. Staff must confirm it by phone or WhatsApp. | Reserved |
| `confirmed` | Customer confirmed address and intent. | Reserved |
| `packed` | Items packed. | Reserved |
| `shipped` | Handed to the courier. Tracking number entered. | Deducted |
| `delivered` | Courier delivered and collected cash. | Deducted |
| `completed` | Courier paid the COD amount to us (cash reconciled). | Deducted |
| `cancelled` | Customer or staff cancelled before dispatch. | Released |
| `returned` | Customer refused or courier failed. Items came back. | Back in stock after check |

Fake order protection (a large COD risk in Pakistan):

- Phone confirmation before dispatch (staff call, or WhatsApp "reply 1 to confirm").
- Limit open orders per phone number. Block a phone or IP after many refusals.
- Optional advance payment for large bulk orders or furniture (answer needed, see question 5). This is not COD, so it needs your decision.
- Rate limit on the checkout view.

## 6. Cart and checkout

- Session cart for guests. It merges into the user cart after login.
- HTMX "add to cart", quantity change and remove, with partial page updates.
- Quantity input follows MOQ and order step. Price updates live when a new tier is reached.
- Checkout is 1 page: contact, address, city (dropdown), order summary with delivery and COD fees, notes, "Place order".
- Server checks stock and prices again on submit. The order total is never trusted from the browser.
- Thank you page with order number and "We will call you to confirm" text.

## 7. Order confirmation and notifications

- Phase 1: staff confirm by phone. Admin shows a "click to WhatsApp" link (`https://wa.me/92...`) with a pre-filled message.
- Later phase: WhatsApp Cloud API template messages for "order received", "shipped" and "delivered", or an SMS gateway (for example a local SMS provider). This needs a Meta business account.
- Email to the store owner for each new order.

## 8. Search and filters

- PostgreSQL full-text search on title, description, brand and category.
- Filters: category, price range, condition, brand, in stock only, bulk available.
- Sort: newest, price low to high, price high to low.
- HTMX updates the product list without a full reload. The URL keeps the filter values so links can be shared.

## 9. Admin (back office)

- Django admin with inlines: product with variants, images and price tiers.
- Bulk actions: activate, hide, mark featured, change category.
- CSV/Excel import for products and stock per lot.
- Order list with filters by status, city and date. Actions: confirm, mark packed, mark shipped (with tracking number), cancel.
- Printable packing slip and invoice (HTML print view).
- Simple dashboard: orders today, orders to confirm, low stock, COD amount pending from couriers.
- Staff roles with Django groups: Owner, Order manager, Inventory manager.

## 10. Other parts

- **Currency**: PKR only. Show prices as `Rs 1,250`. Store money as `DecimalField` with 0 decimals, or as whole rupees.
- **Language**: English first. Use Django `gettext` in templates from the start so Urdu can come later.
- **SEO**: slugs, meta title and description, sitemap.xml, robots.txt, Open Graph tags for WhatsApp and Facebook shares.
- **Static pages**: About, Contact, Delivery and Returns policy, FAQ.
- **Security**: CSRF on all forms, `DEBUG=False` in production, secure cookies, admin at a non-default URL, rate limits.
- **Analytics** (later): Meta Pixel and Google Analytics, because ads drive most traffic in this market.

## 11. Testing

- Unit tests for price tiers, MOQ, stock reserve and release, status changes, fee calculation.
- View tests for cart, checkout and order placement (including a race test for the last item).
- Admin smoke tests.
- A seed command (`manage.py seed_demo`) that creates demo categories, products, lots and cities, so the test UI is never empty.
- GitHub Actions runs ruff and pytest on every PR. A phase merges into `main` only when CI passes and you test it.

## 12. Git workflow

1. Each phase gets a branch from `main`, for example `phase-1/foundation`.
2. Each task in a phase gets a sub-branch from the phase branch, for example `phase-1/foundation--catalog-models`.
3. Each task branch merges into its phase branch through a PR.
4. When all tasks in a phase are done and tested, the phase branch merges into `main` through a PR.
5. A phase with only 1 task uses only the phase branch.

## 13. Phases

### Phase 0: Plan (this PR)
- Write this plan. Get answers to the open questions.

### Phase 1: Foundation
1. Django project skeleton, settings split (base, dev, prod), `.env` with `django-environ`, ruff, pytest.
2. Docker setup: `Dockerfile`, `compose.yaml` for local and PetHost, Postgres, WhiteNoise.
3. Base templates: Tailwind CDN, HTMX, Alpine, header with cart count, footer.
4. GitHub Actions CI.

### Phase 2: Catalog
1. Category, Brand, Product, Variant, ProductImage models and admin.
2. Product list and detail pages, category pages, image gallery (Alpine).
3. Seed command with demo data.

### Phase 3: Inventory and bulk pricing
1. Lot, StockItem, StockMovement models and admin.
2. PriceTier, MOQ and order step, with price calculation service and tests.
3. One-off item "Sold" behavior. Low stock list.
4. CSV/Excel import for products and stock.

### Phase 4: Cart and checkout
1. Session cart with HTMX updates and tier pricing.
2. City model with delivery and COD fees.
3. Checkout form, order creation with stock reservation, thank you page.
4. Fake order protections (limits, rate limit, blocklist).

### Phase 5: Order management
1. Order status machine with history and stock effects.
2. Admin order actions, packing slip and invoice print view.
3. WhatsApp click-to-chat confirm link. New order email to owner.
4. Dashboard numbers.

### Phase 6: Customers, search and content
1. Optional accounts (phone login), saved addresses, order history, order tracking page by number + phone.
2. Full-text search, filters and sort with HTMX.
3. Static pages, SEO basics, sitemap.

### Phase 7: Deploy to PetHost
1. Production settings, Gunicorn, health check view.
2. Media serving and volumes, nightly `pg_dump`.
3. First deploy, domain, smoke test on the live URL.

### Phase 8: Later (after real use)
- Courier API booking and tracking (PostEx, Leopards, TCS).
- WhatsApp Cloud API or SMS notifications.
- Wholesale buyer accounts (if not in phase 3).
- Urdu translation.
- Real UI design.
- Reports: profit per lot, sales per category, COD reconciliation.

## 14. Open questions for Ahmad

1. **PetHost**: Is it the Docker machine connected to this account? Which plan size (CPU, RAM, disk)? Do you have a domain name?
2. **Accounts**: Guest checkout only, or guest checkout plus optional accounts?
3. **Bulk pricing**: Price tiers per product for everyone, or wholesale buyers who need approval? Or both?
4. **Stock type**: Are most items one-off lots (1 piece each), repeated stock (many of the same), or a mix?
5. **Delivery**: Flat fee, fee per city, or courier rates by weight? Which courier(s) do you use (TCS, Leopards, PostEx, Trax, M&P, own rider)? Do you want an advance payment for large or furniture orders?
6. **Confirmation**: Phone call by staff, WhatsApp, or SMS? Do you have a WhatsApp Business account?
7. **Language**: English only, or English and Urdu?
8. **Money and invoices**: PKR only? Do you need tax (GST/FBR) on invoices, or a simple invoice?
9. **Team**: Who adds products and images, and who handles orders? How many staff accounts?
10. **Returns**: What is your return or exchange policy for used and auction items?
