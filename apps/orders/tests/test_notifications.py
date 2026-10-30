import pytest
from django.core import mail

from apps.catalog.tests.factories import VariantFactory
from apps.orders.notifications import order_whatsapp_url, whatsapp_url

from .factories import make_order

pytestmark = pytest.mark.django_db


def test_whatsapp_url():
    assert whatsapp_url("+923001234567", "Hi there") == "https://wa.me/923001234567?text=Hi%20there"


def test_order_whatsapp_message_has_number_and_total():
    order = make_order([(VariantFactory(price=900), 1)])
    url = order_whatsapp_url(order)
    assert url.startswith("https://wa.me/923001234567?text=")
    assert order.number in url


def test_new_order_email(settings, django_capture_on_commit_callbacks):
    settings.ORDER_ALERT_EMAIL = "owner@example.com"
    with django_capture_on_commit_callbacks(execute=True):
        order = make_order([(VariantFactory(price=900), 1)])
    assert len(mail.outbox) == 1
    assert order.number in mail.outbox[0].subject


def test_no_email_when_not_set(settings, django_capture_on_commit_callbacks):
    settings.ORDER_ALERT_EMAIL = ""
    with django_capture_on_commit_callbacks(execute=True):
        make_order([(VariantFactory(price=900), 1)])
    assert mail.outbox == []


def test_mail_failure_does_not_break_the_order(settings, django_capture_on_commit_callbacks):
    settings.ORDER_ALERT_EMAIL = "owner@example.com"
    settings.EMAIL_BACKEND = "apps.orders.tests.test_notifications.BrokenBackend"
    with django_capture_on_commit_callbacks(execute=True):
        order = make_order([(VariantFactory(price=900), 1)])
    assert order.pk


class BrokenBackend:
    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise OSError("SMTP down")
