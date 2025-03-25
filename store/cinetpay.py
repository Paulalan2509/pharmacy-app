# cinetpay view


# try:
#     # CinetPay configuration
#     payment_response = create_cinetpay_payment(
#         request,
#         amount=int(totals),
#         description='PharmaHope Order'
#     )
#
#     if payment_response['success']:
#         cinetpay_payment_url = payment_response['payment_url']
#     else:
#         raise Exception(payment_response['error'])
#
# except Exception as e:
#     messages.error(request, f"CinetPay initialization failed: {str(e)}")
#     cinetpay_payment_url = None



# Add this after create actual paypal button in billing info view
# Check to see if user is logged in
# if request.user.is_authenticated:
#     billing_form = PaymentForm()
#     return render(request, "payment/billing_info.html",
#                   {"paypal_form": paypal_form, "cart_products": cart_products, "quantities": quantities,
#                    "totals": totals, "shipping_info": request.POST, "cinetpay_payment_url": cinetpay_payment_url,
#                    "billing_form": billing_form})
# else:
#     billing_form = PaymentForm()
#     return render(request, "payment/billing_info.html",
#                   {"paypal_form": paypal_form, "cart_products": cart_products, "quantities": quantities,
#                    "totals": totals, "shipping_info": request.POST, "cinetpay_payment_url": cinetpay_payment_url,
#                    "billing_form": billing_form})
