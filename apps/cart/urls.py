from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_detail, name="detail"),
    path("add/", views.add, name="add"),
    path("update/<int:variant_id>/", views.update, name="update"),
    path("remove/<int:variant_id>/", views.remove, name="remove"),
]
