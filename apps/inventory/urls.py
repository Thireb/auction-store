from django.urls import path

from . import views

app_name = "lots"

urlpatterns = [
    path("", views.lot_list, name="list"),
    path("<slug:slug>/", views.lot_detail, name="detail"),
    path("<slug:slug>/dig/", views.dig, name="dig"),
    path("<slug:slug>/calendar.ics", views.calendar, name="calendar"),
]
