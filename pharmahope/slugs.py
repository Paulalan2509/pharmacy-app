from django.utils.text import slugify


def unique_slug(instance, value, fallback='item'):
    """Return a slug for `instance` built from `value` that no other row of the same model uses.

    Two objects with the same title get "my-title", "my-title-2", "my-title-3"... instead of
    failing with a database IntegrityError. Titles with no usable characters fall back to `fallback`.
    """
    model = type(instance)
    max_length = model._meta.get_field('slug').max_length
    base = (slugify(value) or fallback)[:max_length - 10]  # leave room for a "-123" suffix
    others = model._default_manager.all()
    if instance.pk:
        others = others.exclude(pk=instance.pk)

    slug, counter = base, 2
    while others.filter(slug=slug).exists():
        slug = f'{base}-{counter}'
        counter += 1
    return slug
