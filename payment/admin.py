from django.contrib import admin
from .models import ShippingAddress, Order, OrderItem


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = ('shipping_full_name', 'shipping_email', 'shipping_city', 'shipping_country')
    search_fields = ('shipping_full_name', 'shipping_email', 'shipping_city')
    list_filter = ('shipping_country', 'shipping_city')


class OrderItemInline(admin.StackedInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'full_name', 'email', 'amount_paid', 'payment_status', 'date_ordered', 'shipped')
    readonly_fields = ('date_ordered', 'invoice', 'paypal_amount', 'paypal_currency', 'paypal_txn_id', 'paid_at')
    list_filter = ('payment_status', 'shipped', 'date_ordered')
    search_fields = ('full_name', 'email')
    date_hierarchy = 'date_ordered'

    fields = [
        'user',
        'full_name',
        'email',
        'shipping_address',
        'amount_paid',
        'payment_status',
        'invoice',
        'paypal_amount',
        'paypal_currency',
        'paypal_txn_id',
        'paid_at',
        'date_ordered',
        'shipped',
        'date_shipped'
    ]

    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product_name', 'user', 'quantity', 'price')
    list_filter = ('order', 'product', 'user')
    search_fields = ('order__full_name', 'product__name', 'user__username')