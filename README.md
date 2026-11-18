# PharmaHope

PharmaHope is a Django-based online pharmacy and health community platform. It combines a medicine catalog and shopping cart with customer accounts, checkout and payment integrations, a health blog, and a discussion forum.

## Features

- Browse pharmacy products by category, price, name, availability, and sale status.
- View product details, ratings, and authenticated customer reviews.
- Register, sign in, update account details, manage profile information, and change passwords.
- Add products to a session-based shopping cart, update quantities, and persist the cart for signed-in users.
- Checkout with shipping information and order creation.
- PayPal checkout: totals are computed on the server, and an order is marked paid only after PayPal's verified IPN notification matches it.
- Admin and staff order-management views for shipping status.
- Publish and manage blog posts with categories, tags, featured images, comments, pagination, and moderation.
- Create forum categories and threads, reply to discussions, and mark replies as solutions.
- Serve uploaded media and static assets during development.
- Tailwind CSS and Django Browser Reload support are configured for local development.

## Technology

- Python 3.12+ recommended
- Django 5.2 LTS
- MySQL
- Django Tailwind
- PayPal (django-paypal, IPN)
- MySQL in production; SQLite for quick local development (`DB_ENGINE=sqlite`)
- HTML templates, CSS, and vanilla JavaScript

## Project structure

```text
pharmacy-app/
├── blog/                 # Blog posts, categories, tags, comments, and moderation
├── cart/                 # Session cart and cart endpoints
├── forum/                # Community categories, threads, and replies
├── payment/              # Shipping, orders, checkout, and PayPal integration (services.py, signals.py)
├── pharmahope/           # Django project settings, URLs, ASGI, and WSGI
├── store/                # Products, categories, profiles, reviews, accounts, and storefront
├── theme/                # Django Tailwind app
├── media/                # Uploaded and seed media files
├── static/               # CSS, JavaScript, and favicon
├── manage.py             # Django management entry point
├── requirements.txt      # Core dependencies
├── requirements-mysql.txt# Adds mysqlclient for MySQL
├── requirements-dev.txt  # Development-only tools
└── .env.example          # Template for your local .env (never commit .env)
```

## Main routes

| Area | URL |
| --- | --- |
| Home | `/` |
| Store | `/store/` |
| Product details | `/product/<id>/` |
| Search | `/search/` |
| Categories | `/category_summary/` and `/category/<name>` |
| Cart | `/cart/` |
| Checkout | `/payment/checkout` |
| Blog | `/blog/` |
| Forum | `/forum/` |
| User login and registration | `/login/` and `/register/` |
| Django admin | `/admin/` |

## Local setup

### 1. Clone the repository

```bash
git clone https://github.com/Paulalan2509/pharmacy-app.git
cd pharmacy-app
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt     # development (adds browser reload + django-extensions)
# python -m pip install -r requirements-mysql.txt # production with MySQL (adds mysqlclient)
# python -m pip install -r requirements.txt       # production with SQLite / any other database
```

`mysqlclient` lives in its own file because it needs the MySQL client headers to build (it often fails on Windows). Local development with `DB_ENGINE=sqlite` does not need it.

### 4. Configure the environment

All secrets and environment-specific values come from environment variables. Copy the template and fill it in:

```bash
cp .env.example .env
```

For local development the simplest setup is:

```text
DJANGO_DEBUG=True
DB_ENGINE=sqlite
```

`DJANGO_DEBUG` defaults to **False**, and in that mode the app refuses to start unless `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` and database credentials are set. `.env` is git-ignored.

To use MySQL instead, create the database and set `DB_ENGINE=mysql`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`:

```sql
CREATE DATABASE pharmadb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 5. Configure PayPal

Set these in `.env` (use PayPal **sandbox** values while developing):

- `PAYPAL_TEST=True` for the sandbox, `False` for live payments
- `PAYPAL_RECEIVER_EMAIL` - the PayPal business account that receives payments
- `PAYPAL_EXCHANGE_RATE` - how many `STORE_CURRENCY` units (default `XAF`/Fcfa) equal 1 `PAYPAL_CURRENCY` (default `USD`). PayPal does not support XAF, so this is **required**: checkout refuses to start a payment without it rather than charging a guessed amount.

PayPal must be able to reach your server to send payment notifications (IPN) at `/payment/paypal`, so use a public HTTPS URL (for local testing, a tunnel such as ngrok).

### 6. Apply migrations and create an administrator

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 7. Start the development server

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

## Tailwind development

The project registers `theme` as the Tailwind app. If you need to rebuild Tailwind assets, install Node.js and run the Django Tailwind commands:

```bash
python manage.py tailwind install
python manage.py tailwind start
```

Run the Django server in a separate terminal. Django Browser Reload is enabled for local development through `/__reload__/`.

## Payments and checkout

1. The customer fills in shipping details at `/payment/checkout`. They are validated with `ShippingForm`.
2. `billing_info` creates a **pending** order and its items from the cart, using prices from the database (nothing price-related is read from the browser). The Fcfa total is converted to the PayPal currency with `PAYPAL_EXCHANGE_RATE`, and that exact amount is stored on the order.
3. The customer pays on PayPal's own site. Card details never reach this server.
4. PayPal sends an IPN to `/payment/paypal`. `payment/signals.py` marks the order **paid** only if the notification is verified by django-paypal *and* the receiver, currency and amount match the order exactly. Replayed notifications are harmless, and refunds/reversals are recorded.
5. Only paid orders appear in the "not shipped" dashboard and can be marked as shipped.

The page PayPal returns the customer to (`/payment/payment_success`) does not confirm payment on its own; it shows the order's real status.

Orders that were already marked shipped before payment tracking existed are migrated to "paid"; other pre-existing orders become "pending" and can be reviewed in the admin.

## Administration

Create a superuser to access `/admin/`. Superusers can also use the project dashboard and payment views to review orders and update shipping status.

The admin dashboard depends on seeded product, category, and forum/blog data being available in the database.

### Blog authors

Only trusted people can publish blog posts. Superusers always can; for anyone else, create a group called "Blog authors" in `/admin/` (Authentication and Authorization > Groups), give it the "Can add blog post" permission (and "Can change blog post" for editors who may edit others' posts), and add the users to it. Ordinary registered customers can read and comment. Comments wait for approval in the admin. Drafts and archived posts are visible only to their author and to editors. Post HTML is sanitized on save and on display.

### Login throttling

After 5 failed logins for the same username from the same IP, further attempts are refused for 15 minutes (HTTP 429), even with the correct password. This uses Django's cache. The default per-process cache is fine for one server; with several workers or servers, configure a shared cache (Redis or Memcached) so the counter is shared.

## Static and media files

- Static assets are under `static/`.
- User uploads and project media are under `media/`.
- In development, Django serves media through the project URL configuration.
- In production, configure a proper static/media server and run:

```bash
python manage.py collectstatic
```

## Testing and checks

```bash
python manage.py check
python manage.py test
```

The test suite covers the cart limits, server-side totals, the PayPal currency guard, IPN verification (amount, currency, receiver, replay, refund), shipping permissions, the forum, blog security (XSS, permissions, drafts), login throttling, unique emails, and store filtering/pagination. Run it with `DJANGO_DEBUG=True DB_ENGINE=sqlite` for a quick local run.

## Production checklist

- Set `DJANGO_DEBUG=False`, a unique `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS` (with `https://`).
- Use HTTPS. Behind a reverse proxy, set `DJANGO_BEHIND_PROXY=True`. Start with a short `DJANGO_HSTS_SECONDS` and raise it once HTTPS is confirmed. Run `python manage.py check --deploy`.
- Use a dedicated database user with a password (never `root`).
- Set `PAYPAL_TEST=False`, your live `PAYPAL_RECEIVER_EMAIL` and a current `PAYPAL_EXCHANGE_RATE`, and verify a real IPN end-to-end in the sandbox first.
- Run `python manage.py collectstatic` and serve static and media files from a web server or object storage (not Django).
- Configure email, backups and monitoring.
- Review the legal requirements for selling medicines in your country (prescription-only products, licensing) before accepting real orders.
- If credentials were ever committed to this repository, rotate them: removing them from the code does not remove them from git history.

## License

No license file is currently included. Add a license before distributing or accepting external contributions.
