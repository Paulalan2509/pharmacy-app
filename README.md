# PharmaHope

PharmaHope is a Django-based online pharmacy and health community platform. It combines a medicine catalog and shopping cart with customer accounts, checkout and payment integrations, a health blog, and a discussion forum.

## Features

- Browse pharmacy products by category, price, name, availability, and sale status.
- View product details, ratings, and authenticated customer reviews.
- Register, sign in, update account details, manage profile information, and change passwords.
- Add products to a session-based shopping cart, update quantities, and persist the cart for signed-in users.
- Checkout with shipping information and order creation.
- PayPal IPN integration for payment notifications; CinetPay configuration is also present for payment gateway work.
- Admin and staff order-management views for shipping status.
- Publish and manage blog posts with categories, tags, featured images, comments, pagination, and moderation.
- Create forum categories and threads, reply to discussions, and mark replies as solutions.
- Serve uploaded media and static assets during development.
- Tailwind CSS and Django Browser Reload support are configured for local development.

## Technology

- Python 3.12+ recommended
- Django 5.1
- MySQL
- Django Tailwind
- PayPal IPN
- CinetPay configuration
- SQLite database file included in the repository for local data, while the active settings use MySQL
- HTML templates, CSS, and vanilla JavaScript

## Project structure

```text
pharmacy-app/
├── blog/                 # Blog posts, categories, tags, comments, and moderation
├── cart/                 # Session cart and cart endpoints
├── forum/                # Community categories, threads, and replies
├── payment/              # Shipping, orders, checkout, and PayPal integration
├── pharmahope/           # Django project settings, URLs, ASGI, and WSGI
├── store/                # Products, categories, profiles, reviews, accounts, and storefront
├── theme/                # Django Tailwind app
├── media/                # Uploaded and seed media files
├── static/               # CSS, JavaScript, and favicon
├── manage.py             # Django management entry point
└── db.sqlite3            # Checked-in SQLite database file
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

This repository does not currently include a `requirements.txt` or `pyproject.toml`. Install the packages used by the project:

```bash
python -m pip install --upgrade pip
python -m pip install \
  "Django>=5.1,<5.2" \
  django-tailwind \
  django-browser-reload \
  django-extensions \
  django-paypal \
  mysqlclient \
  Pillow \
  requests
```

On Windows, use a MySQL client package compatible with your Python version if `mysqlclient` cannot be built locally.

### 4. Configure the database

The active configuration in `pharmahope/settings.py` expects a local MySQL database with:

```text
Database: pharmadb
User: root
Host: localhost
Port: 3306
```

Create the database before migrating:

```sql
CREATE DATABASE pharmadb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Update the database settings for your local credentials. For a quick local prototype, the `db.sqlite3` file is present, but Django will use the configured MySQL connection unless `DATABASES` is changed.

### 5. Configure payment and development settings

Before running the project, review `pharmahope/settings.py` and configure:

- `SECRET_KEY`
- `DEBUG` and `ALLOWED_HOSTS`
- MySQL credentials
- PayPal sandbox receiver settings
- CinetPay API settings and callback URLs
- `NPM_BIN_PATH` if Tailwind is used on Windows

The current settings contain hard-coded development secrets and payment credentials. Do not reuse them in production; move secrets to environment variables and rotate any credentials that have been exposed.

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

Checkout uses the cart contents and shipping information to create an `Order` and related `OrderItem` records. PayPal payment forms and IPN URLs are wired through the `payment` app. CinetPay settings and an unfinished/example API implementation are also present, but the active checkout flow currently constructs a PayPal form.

Use sandbox/test credentials and callback URLs while developing. Payment callbacks must be publicly reachable over HTTPS in a deployed environment.

## Administration

Create a superuser to access `/admin/`. Superusers can also use the project dashboard and payment views to review orders and update shipping status.

The admin dashboard depends on seeded product, category, and forum/blog data being available in the database.

## Static and media files

- Static assets are under `static/`.
- User uploads and project media are under `media/`.
- In development, Django serves media through the project URL configuration.
- In production, configure a proper static/media server and run:

```bash
python manage.py collectstatic
```

## Testing and checks

Run Django's built-in checks and test discovery with:

```bash
python manage.py check
python manage.py test
```

The repository currently contains only placeholder test modules, so additional automated coverage is recommended before production use.

## Production checklist

- Move all secrets and payment credentials to environment variables or a secret manager.
- Rotate credentials currently present in source-controlled settings.
- Set `DEBUG = False` and configure `ALLOWED_HOSTS`.
- Use HTTPS and production payment callback URLs.
- Configure a production database, static file server, media storage, email backend, and logging.
- Review authentication, authorization, CSRF, checkout, and payment callback behavior before accepting real orders.
- Do not use the checked-in development database as production data.

## License

No license file is currently included. Add a license before distributing or accepting external contributions.
