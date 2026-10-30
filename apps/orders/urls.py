from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("order/<str:number>/thanks/", views.thanks, name="thanks"),
    path("order/<str:number>/advance/", views.upload_advance_proof, name="advance_proof"),
]
