from django.urls import path

from . import views

urlpatterns = [
    # Property management
    path("properties/", views.AdminPropertyViewSet.as_view({"get": "list", "post": "create"}), name="admin-property-list"),
    path("properties/<int:pk>/", views.AdminPropertyViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"}), name="admin-property-detail"),
    path("properties/<int:pk>/archive/", views.AdminPropertyViewSet.as_view({"post": "archive"}), name="admin-property-archive"),
    # Section management
    path("sections/", views.AdminSectionViewSet.as_view({"get": "list", "post": "create"}), name="admin-section-list"),
    path("sections/<int:pk>/", views.AdminSectionViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"}), name="admin-section-detail"),
    path("sections/<int:pk>/archive/", views.AdminSectionViewSet.as_view({"post": "archive"}), name="admin-section-archive"),
    path("sections/reorder/", views.AdminSectionViewSet.as_view({"post": "reorder"}), name="admin-section-reorder"),
    # Unit management
    path("units/", views.AdminUnitViewSet.as_view({"get": "list", "post": "create"}), name="admin-unit-list"),
    path("units/<int:pk>/", views.AdminUnitViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"}), name="admin-unit-detail"),
    path("units/<int:pk>/archive/", views.AdminUnitViewSet.as_view({"post": "archive"}), name="admin-unit-archive"),
    # Pricing rules
    path("pricing-rules/", views.PricingRuleViewSet.as_view({"get": "list", "post": "create"}), name="admin-pricing-list"),
    path("pricing-rules/<int:pk>/", views.PricingRuleViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}), name="admin-pricing-detail"),
    # User management
    path("users/", views.AdminUserViewSet.as_view({"get": "list", "post": "create"}), name="admin-user-list"),
    path("users/<int:pk>/", views.AdminUserViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"}), name="admin-user-detail"),
    path("users/groups/", views.AdminUserViewSet.as_view({"get": "groups"}), name="admin-user-groups"),
    path("users/<int:pk>/toggle-active/", views.AdminUserViewSet.as_view({"post": "toggle_active"}), name="admin-user-toggle-active"),
]
