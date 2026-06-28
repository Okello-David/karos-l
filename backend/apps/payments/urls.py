from django.urls import path

from . import views

urlpatterns = [
    path("", views.PaymentViewSet.as_view({
        "get": "list",
        "post": "create",
    })),
    path("<int:pk>/", views.PaymentViewSet.as_view({
        "get": "retrieve",
    })),
    path("student_balance/", views.PaymentViewSet.as_view({
        "get": "student_balance",
    })),
    path("overdue/", views.PaymentViewSet.as_view({
        "get": "overdue",
    })),
    path("receipts/", views.ReceiptViewSet.as_view({
        "get": "list",
    })),
    path("receipts/<int:pk>/", views.ReceiptViewSet.as_view({
        "get": "retrieve",
    })),
    path("receipts/<int:pk>/pdf/", views.ReceiptViewSet.as_view({
        "get": "pdf",
    })),
]
