# Deploy to PetHost

PetHost runs Docker Compose projects on one rented machine. This store uses `pethost.compose.yaml`, which PetHost takes before `compose.yaml` (the local development file).

## What runs

| Service | Image | Job |
|---|---|---|
| `caddy` | `caddy:2.10-alpine` | The routed service (port 8080). Serves `/media/` from the media volume and sends everything else to `web`. |
| `web` | Built from `Dockerfile` | Django with Gunicorn (2 workers). Runs `migrate` and `setup_roles` at start. WhiteNoise serves static files. |
| `db` | `postgres:16-alpine` | The database, in the `pgdata` volume. |
| `backup` | `postgres:16-alpine` | `pg_dump` every 24 hours into the `backups` volume. Keeps 14 days. |

Data that must survive a deploy is only in named volumes: `pgdata`, `media` (product images and payment screenshots) and `backups`.

## First deploy

1. Choose the address. The free one is `<name>.<your PetHost apps domain>`. Put it in the `host` of the route at the end of `pethost.compose.yaml`.
2. Make the project `/.env` from `.env.prod.example`. Use long random values for `SECRET_KEY` and `POSTGRES_PASSWORD`, the same password inside `DATABASE_URL`, your address in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`, and a hard-to-guess `ADMIN_URL`.
3. Create the PetHost project from this repository (GitHub source) or upload the directory, with the `/.env` file. With the GitHub source, every push to `main` deploys.
4. When the deploy succeeds, create the owner account:

   ```bash
   python manage.py createsuperuser
   ```

   Run it in the `web` service (PetHost "run a command in a service").
5. Add the cities, the starter pages and the default settings:

   ```bash
   python manage.py setup_store
   ```

   Then edit the pages and set the fees and the advance payment details in the staff portal at `/staff/settings/`.
6. Smoke test: open the store, `/healthz/`, the staff portal at `/staff/`, place a test order and cancel it in the portal.
7. When HTTPS works, set `SECURE_HSTS_SECONDS=31536000` in `/.env` and deploy again.

Do not run `seed_demo` on the live store. It adds demo products.

## A custom domain

Add a route for the domain in PetHost and make 1 DNS record: a CNAME from your domain to the PetHost machine host name (an ALIAS record for a bare domain such as `example.com`). Add the domain to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

## Backups and restore

- The `backup` service writes `db-YYYY-MM-DD.dump` files to the `backups` volume. Download one from PetHost from time to time and keep it somewhere else.
- Restore into the `db` service:

  ```bash
  pg_restore --clean --no-owner -d "$DATABASE_URL" /backups/db-YYYY-MM-DD.dump
  ```

- Product images are in the `media` volume. Download it too when you take an off-site copy.

## Resources

The $12 plan is enough to start: Gunicorn has 2 workers and PostgreSQL uses its defaults. If the machine is short of memory, keep the workers at 2. If the store gets busy, raise the workers in the `CMD` of the `Dockerfile` (about 2 per CPU core).
