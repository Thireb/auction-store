from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("products/", views.product_list, name="product_list"),
    path("c/<slug:slug>/", views.category_detail, name="category"),
    path("p/<slug:slug>/", views.product_detail, name="product"),
    path("saved/", views.saved_list, name="saved"),
    path("saved/<int:pk>/", views.saved_toggle, name="saved_toggle"),
    path("nav/c/<int:pk>/", views.nav_children, name="nav_children"),
    path("nav/search/", views.nav_search, name="nav_search"),
]
