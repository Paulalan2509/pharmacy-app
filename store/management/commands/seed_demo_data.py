"""Fill a local database with sample pharmacy products so the store looks alive.

Development only: it refuses to run when DJANGO_DEBUG is off. Every product,
price and description is made up. Product images are simple generated tiles.

Usage:  python manage.py seed_demo_data
"""
import io
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from store.models import Category, Product

CATEGORIES = {
    'Vitamins & Supplements': '#16a34a',
    'Pain Relief': '#2563eb',
    'First Aid': '#dc2626',
    'Skin Care': '#c026d3',
    'Cold & Flu': '#0891b2',
}

# (name, category, price, description, sale_price or None, status)
PRODUCTS = [
    ('Vitamin C 500 mg', 'Vitamins & Supplements', '8.50', 'Sample product. Daily vitamin C tablets, 60 count.', None, 'In Stock'),
    ('Multivitamin Daily', 'Vitamins & Supplements', '12.00', 'Sample product. Once-a-day multivitamin, 90 count.', '9.99', 'In Stock'),
    ('Zinc 25 mg', 'Vitamins & Supplements', '7.25', 'Sample product. Zinc tablets, 100 count.', None, 'In Stock'),
    ('Paracetamol 500 mg', 'Pain Relief', '3.20', 'Sample product. Pain and fever relief tablets, 20 count.', None, 'In Stock'),
    ('Ibuprofen Gel', 'Pain Relief', '6.80', 'Sample product. Topical gel for muscle aches, 50 g.', '5.50', 'In Stock'),
    ('Adhesive Bandages', 'First Aid', '2.90', 'Sample product. Assorted sizes, box of 40.', None, 'In Stock'),
    ('Antiseptic Solution', 'First Aid', '4.10', 'Sample product. Skin antiseptic, 100 ml.', None, 'In Stock'),
    ('Moisturising Cream', 'Skin Care', '9.40', 'Sample product. Fragrance-free daily moisturiser, 200 ml.', None, 'In Stock'),
    ('Sunscreen SPF 50', 'Skin Care', '11.60', 'Sample product. Broad-spectrum sunscreen lotion, 100 ml.', '9.90', 'In Stock'),
    ('Throat Lozenges', 'Cold & Flu', '3.75', 'Sample product. Honey and lemon lozenges, 24 count.', None, 'In Stock'),
    ('Saline Nasal Spray', 'Cold & Flu', '5.30', 'Sample product. Saline spray, 30 ml.', None, 'In Stock'),
    ('Digital Thermometer', 'First Aid', '10.20', 'Sample product. Fast-read digital thermometer.', None, 'In Stock'),
]


def _font(size):
    for path in ('DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                 'C:/Windows/Fonts/arialbd.ttf', 'arial.ttf'):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_tile(name, colour):
    img = Image.new('RGB', (600, 600), colour)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((60, 60, 540, 540), radius=48, fill='white')
    d.rectangle((270, 150, 330, 330), fill=colour)
    d.rectangle((210, 210, 390, 270), fill=colour)
    words, lines, line = name.split(), [], ''
    for w in words:
        if len(line + ' ' + w) > 16 and line:
            lines.append(line)
            line = w
        else:
            line = (line + ' ' + w).strip()
    lines.append(line)
    y = 370
    for ln in lines[:2]:
        width = d.textlength(ln, font=_font(38))
        d.text(((600 - width) / 2, y), ln, fill='#1f2937', font=_font(38))
        y += 48
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=85)
    return buf.getvalue()


class Command(BaseCommand):
    help = 'Create sample categories and products for local development.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise ImproperlyConfigured('seed_demo_data is for development only. Set DJANGO_DEBUG=True.')

        cats = {}
        for name in CATEGORIES:
            cats[name], _ = Category.objects.get_or_create(name=name)

        created = 0
        for name, cat, price, desc, sale, status in PRODUCTS:
            product, was_created = Product.objects.get_or_create(
                name=name,
                defaults=dict(
                    category=cats[cat], price=Decimal(price), description=desc,
                    availability_status=status, is_sale=bool(sale),
                    sale_price=Decimal(sale) if sale else Decimal('0'),
                    expiration_date=date.today() + timedelta(days=700),
                ),
            )
            if was_created or not product.image:
                product.image.save(f'{name.lower().replace(" ", "-")}.jpg',
                                   ContentFile(make_tile(name, CATEGORIES[cat])), save=True)
            created += int(was_created)

        self.stdout.write(self.style.SUCCESS(
            f'Done: {len(CATEGORIES)} categories, {len(PRODUCTS)} sample products ({created} new).'))
