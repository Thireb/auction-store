# Auction Store: Project Plan

Status: **approved by Ahmad on 2026-10-30**. Phases 1 to 6 are built. Phase 7 has the production files; the first deploy waits for the PetHost plan. Phase 9 (storefront design) is built on branch `phase-9/storefront`.

## 0. Decisions from Ahmad

| Topic | Decision |
|---|---|
| Hosting | Build and finish the app locally first. Then deploy to the PetHost $12 plan. |
| Accounts | Guest checkout. At checkout, a "Create an account" checkbox makes an account from the same form data. |
| Bulk pricing | Both: price tiers per product for everyone, and approved wholesale buyers. Bulk is mostly for mobile accessories. Most items are normal "add quantity to cart". |
| Stock | A mix of one-off pieces and repeated stock. |
| Delivery | Not decided yet (depends on a courier partner). Fees must be configurable. Advance payment (full or part) is possible for large items. |
| Confirmation | Staff call the customer. Leave room for WhatsApp. **No paid services** for now. |
| Language | English only. |
| Currency | PKR only. No tax on invoices for now. |
| Staff | Staff add products and images. An owner (admin) account creates staff accounts and can see what each staff member did and all stock. |
| Returns | No return policy now. Focus on a functional store. |

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
| Background jobs | None | No Redis or Celery. Nothing in the app needs a queue now. |
| Audit log | `django-simple-history` (history on products, variants, stock, orders) + Django admin log | The owner sees who changed what and when. Free and runs in the same DB. |
| Tests | `pytest`, `pytest-django`, `factory_boy` | Fast unit and view tests. |
| Lint and format | `ruff` | One tool for lint and format. |
| CI | GitHub Actions: ruff + pytest on every PR | Catches errors before a merge. |

**Suggestion:** keep the stack above. It fits Django + HTMX + Alpine well and needs no Node build. Do not use a SPA framework.

## 3. Hosting on PetHost

All development and tests run locally first with Docker Compose (the same `compose.yaml`). The deploy to the PetHost $12 plan comes last (phase 7), when the app is complete. A small plan is enough for one Django container and one Postgres container, but we keep Gunicorn at 2 workers and check memory at deploy time.

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
- **Attribute** (defined in the admin, no code): name, type (text, number, choice, yes/no), choices, unit, is_filterable, is_variant_option. Linked to 1 or more categories. A child category inherits the attributes of its parent.
- **ProductAttributeValue**: product, attribute, value. The product form in the admin shows the attributes of the product category.
- Result: the owner adds a new category (for example "Perfumes") and its attributes (for example "Volume (ml)") in the admin. The product form, the filters and the product page use them at once. **No code change for a new category.**
- **Variant**: product, SKU, option values (for example size 42, black), price, compare-at price, weight. Each product has at least 1 variant. This keeps cart and stock logic the same for all items.

### 4.2 Bulk pricing and MOQ

- **PriceTier**: variant, min_quantity, unit_price. Example: 1-9 pcs at Rs 1,200, 10-49 at Rs 1,000, 50+ at Rs 850.
- **Variant.min_order_qty** (MOQ) and **Variant.order_step** (for example sold in packs of 12).
- The cart always calculates the unit price from the highest tier the quantity reaches.
- **Wholesale buyers** (decided: yes). A customer with an account applies (business name, city, phone). Staff approve or reject. A PriceTier has a flag `wholesale_only`. Only approved buyers see and get those tiers. Normal buyers still get public tiers.
- Most products have no tiers. They are simple "add quantity to cart" items. Bulk tiers are mainly for mobile accessories.

### 4.3 Lots and stock

- **Lot**: a purchase from an auction or exporter. Fields: reference, source (auction house, exporter), purchase date, total cost, landed cost (shipping, customs), notes. Used for cost and profit reports.
- **StockItem**: variant, lot, quantity_on_hand, quantity_reserved, cost_per_unit.
- **StockMovement**: variant, lot, change (+/-), reason (`received`, `order reserved`, `order cancelled`, `delivered`, `returned`, `adjustment`), order link, user, time. This is the audit trail. Stock numbers come from these rows.
- **One-off items** (a single sofa) are a variant with quantity 1. When sold, the product shows "Sold" and stays visible for a few days, then hides.

Stock rule: the store **reserves stock when the order is placed**. It releases stock when the order is cancelled or fails delivery. It uses `select_for_update` so two buyers cannot buy the last piece.

### 4.4 Customers

- Guest checkout with name, phone and address (most COD buyers in Pakistan expect this).
- At checkout, a **"Create an account"** checkbox. When checked (Alpine shows a password field), the store creates an account from the checkout data and links the order to it.
- Account login by phone (or email) + password. No OTP (SMS costs money). Saves addresses and shows order history.
- **Address**: name, phone, city, area, street address, nearest landmark, postal code (optional).
- **Phone** is the main key. Store it in `+92 3XX XXXXXXX` format and validate it.

### 4.5 Shipping

The courier is not decided yet. So all fees are data in the admin, not code:

- **ShippingSettings** (one row): default delivery fee, default COD fee, free delivery above an order total.
- **City**: name, province, is_active, is_cod_allowed. Optional fee overrides. A city without overrides uses the defaults.
- **Bulky flag** on a product or category (furniture): extra delivery fee and "advance required" rules.
- **Shipment**: order, courier name (free text), tracking number, booked_at, status. Staff enter it by hand. A courier API comes after a partner is chosen.

### 4.5.1 Advance payment

For large items the store can ask for an advance. No payment gateway is used.

- Rules: per product or category, `advance_type` = none, fixed amount, or percent of the price. Also an optional rule "advance for orders above Rs X".
- Checkout shows the advance amount and the store bank / Easypaisa / JazzCash account details (from the admin settings).
- The customer uploads a screenshot of the transfer (optional at checkout, or later from the order tracking page).
- Staff check it and mark the advance as received. The rest is COD.
- Order fields: advance_required, advance_amount, advance_status (`not_required`, `pending`, `received`), advance_proof image.

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
| `pending_confirmation` | Customer placed the order. Staff must confirm it by phone (or WhatsApp click-to-chat). | Reserved |
| `awaiting_advance` | Only for orders that need an advance. Waits for staff to check the transfer. | Reserved |
| `confirmed` | Customer confirmed address and intent. | Reserved |
| `packed` | Items packed. | Reserved |
| `shipped` | Handed to the courier. Tracking number entered. | Deducted |
| `delivered` | Courier delivered and collected cash. | Deducted |
| `completed` | Courier paid the COD amount to us (cash reconciled). | Deducted |
| `cancelled` | Customer or staff cancelled before dispatch. | Released |
| `returned` | Customer refused the COD parcel or the courier failed. Items came back. (This is not a return policy. It is a normal COD event.) | Back in stock after check |

Fake order protection (a large COD risk in Pakistan):

- Phone confirmation before dispatch (staff call, or WhatsApp "reply 1 to confirm").
- Limit open orders per phone number. Block a phone or IP after many refusals.
- Advance payment for large items (section 4.5.1).
- Rate limit on the checkout view.

## 6. Cart and checkout

- Session cart for guests. It merges into the user cart after login.
- HTMX "add to cart", quantity change and remove, with partial page updates.
- Quantity input follows MOQ and order step. Price updates live when a new tier is reached.
- Checkout is 1 page: contact, address, city (dropdown), order summary with delivery and COD fees, notes, "Place order".
- Server checks stock and prices again on submit. The order total is never trusted from the browser.
- Thank you page with order number and "We will call you to confirm" text.

## 7. Order confirmation and notifications

- Staff confirm by phone. The admin order page shows the phone as a `tel:` link and a free "click to WhatsApp" link (`https://wa.me/92...`) with a pre-filled message.
- No paid service (no SMS gateway, no paid WhatsApp API). A `notifications` module with one function per event keeps room to add WhatsApp later without changes in other code.
- Email to the store owner for each new order, through any SMTP account (free). If no SMTP is set, the store skips the email.

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
- **Everything is data in the admin.** Categories, attributes, brands, fees, bank details, home page banners, featured products and static pages are all edited in the admin. Code changes are only for new features.
- **Owner account** (superuser) creates staff accounts. Staff cannot create or edit users.
- **Roles are Django groups with ticked permissions.** The owner can change a role or make a new role in the admin, with no code. Default roles:

  | Role | Can do | Cannot do |
  |---|---|---|
  | Inventory manager | Add and edit products, images, categories, attributes, brands. Receive stock into lots. | See cost and profit. Change prices (optional). Touch orders. Delete anything. |
  | Order manager | See and update orders, confirm by phone, enter tracking, mark advance received, see customers. | Edit products or prices. Adjust stock by hand. Delete orders. |
  | Owner | Everything. | - |

- **Custom permissions** for sensitive actions, given per role or per person: `view_cost_and_profit`, `change_price`, `adjust_stock`, `approve_wholesale_buyer`, `cancel_confirmed_order`, `view_reports`.
- **No hard delete for staff.** Products and categories are hidden with `is_active`. Orders are cancelled, never deleted. Only the owner can delete.
- Every staff change is in the audit log (who, what, old value, new value, time).
- **Staff activity page** for the owner: a list of all changes (who, what, when, old and new values) from `django-simple-history`, filtered by staff member and date. Each StockMovement also stores the user.
- **Stock view** for the owner: all variants with on hand, reserved, available, lot and cost value.

## 10. Other parts

- **Currency**: PKR only. Show prices as `Rs 1,250`. Store money as `DecimalField` with 0 decimals, or as whole rupees.
- **Language**: English only. No translation work.
- **SEO**: slugs, meta title and description, sitemap.xml, robots.txt, Open Graph tags for WhatsApp and Facebook shares.
- **Static pages**: About, Contact, Delivery info, FAQ. Editable in the admin. No return policy page now.
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
1. Django project skeleton, settings split (base, dev, prod), `.env` with `django-environ`, ruff, pytest. Owner superuser and staff groups.
2. Docker setup: `Dockerfile`, `compose.yaml` for local and PetHost, Postgres, WhiteNoise.
3. Base templates: Tailwind CDN, HTMX, Alpine, header with cart count, footer.
4. GitHub Actions CI.

### Phase 2: Catalog
1. Category, Brand, Product, Variant, ProductImage models and admin.
2. Product list and detail pages, category pages, image gallery (Alpine).
3. Seed command with demo data.

### Phase 3: Inventory and bulk pricing
1. Lot, StockItem, StockMovement models and admin.
2. PriceTier (public and wholesale-only), MOQ and order step, with price calculation service and tests.
3. One-off item "Sold" behavior. Low stock list.
4. CSV/Excel import for products and stock.

### Phase 4: Cart and checkout
1. Session cart with HTMX updates and tier pricing.
2. ShippingSettings and City models with configurable fees. Advance payment rules.
3. Checkout form with "Create an account" checkbox, order creation with stock reservation, advance proof upload, thank you page.
4. Fake order protections (limits, rate limit, blocklist).

### Phase 5: Order management
1. Order status machine with history and stock effects.
2. Admin order actions (including "advance received"), packing slip and invoice print view.
3. WhatsApp click-to-chat confirm link. New order email to owner.
4. Owner dashboard, staff activity page (`django-simple-history`), stock view.

### Phase 6: Customers, search and content
1. Accounts (login, saved addresses, order history), wholesale buyer application and approval, order tracking page by number + phone.
2. Full-text search, filters and sort with HTMX.
3. Static pages, SEO basics, sitemap.

### Phase 7: Deploy to PetHost ($12 plan, after the app is complete and tested locally)
1. Production settings, Gunicorn, health check view.
2. Media serving and volumes, nightly `pg_dump`.
3. First deploy, domain, smoke test on the live URL.

### Phase 8: Later (after real use)
- Courier API booking and tracking, after a partner is chosen.
- WhatsApp or SMS messages, only if a paid service is approved later.
- Reports: profit per lot, sales per category, COD reconciliation.

### Phase 9: Storefront design ("lots")

Approved by Ahmad on 2026-11-01. Mockups: https://claude.ai/artifact/UshbKGTrJ8u5X7cRuXR5mr

Goal: customers do not only buy and leave. Each shipment is a public **lot** with a number, a story and a count of pieces left. A new lot opens at a set time, so customers come back.

Backend:

1. **Public lots.** `Lot` gets `slug`, `public_title`, `story`, `cover_image`, `is_public` and `opens_at`. A product belongs to the lots it has stock in (`StockItem`). Pages: `/lots/`, `/lots/<slug>/`, `/lots/<slug>/dig/` and `/lots/<slug>/calendar.ics` (a free reminder).
2. **Lot opening time.** A product whose stock is only in lots that open later is hidden until the lot opens (`Product.objects.listed()`).
3. **Lot numbers.** `apps.inventory.lots` counts pieces received and pieces left per lot, in 1 query.
4. **Saved pieces.** Guests save in the session. Signed-in customers save in `SavedProduct`. The session list merges into the account at login.
5. **Just sold.** Products sold out in the last 3 days show with a "Sold" stamp. They cannot be opened or bought.
6. **Condition notes.** `Product.condition_notes`: one line per note, shown under the condition scale.
7. **Recently viewed.** The last 12 product pages, in the session.
8. **Delivery estimate.** `/cart/quote/` returns the delivery fee and the days for a city, from `apps.shipping.services.quote()`.
9. **Lot reminders.** `ShippingSettings.whatsapp_channel_url` (a free WhatsApp channel). Empty hides the button.
10. **Staff portal.** The lot form, the product form and the store settings get the new fields.

Frontend:

1. One hand-written stylesheet (`static/store/store.css`) and one small script (`static/store/store.js`). No Tailwind and no build step on the storefront. HTMX and Alpine stay.
2. Pages: home, lot list, lot page, Dig mode, product list and category, product page, cart drawer and cart page, checkout, thank-you page, account, log in, sign up, track order and content pages.
3. Motion: the lot tag swings, the hero cards fan out, the stock bar fills, a heart pops, the cart drawer slides, Dig cards fly out and a stamp drops on "Sold". Page changes use View Transitions where the browser has them. All motion stops when the visitor asks for reduced motion.

## 14. Open questions

All 10 first questions are answered (section 0). Still open, not blocking:

1. The delivery partner and its fee model. The store keeps fees configurable until then.
2. The bank / Easypaisa / JazzCash details for advance payments. These go in the admin settings.
