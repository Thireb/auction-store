from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("products/", views.product_list, name="product_list"),
    path("c/<slug:slug>/", views.category_detail, name="category"),
    path("p/<slug:slug>/", views.product_detail, name="product"),
]
