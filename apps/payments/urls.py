from django.urls import path

from .views import PaymentViewSet

pending_payments = PaymentViewSet.as_view({"get": "pending"})
payment_detail = PaymentViewSet.as_view({"get": "retrieve"})
payment_confirm = PaymentViewSet.as_view({"post": "confirm"})
payment_reject = PaymentViewSet.as_view({"post": "reject"})

urlpatterns = [
    path("pending/", pending_payments, name="payment-pending-list"),
    path("<int:pk>/", payment_detail, name="payment-detail"),
    path("<int:pk>/confirm/", payment_confirm, name="payment-confirm"),
    path("<int:pk>/reject/", payment_reject, name="payment-reject"),
]
