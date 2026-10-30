import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.core.roles import ROLES


@pytest.mark.django_db
def test_home_page(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_healthz(client):
    response = client.get(reverse("core:healthz"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_setup_roles_creates_groups_and_can_run_again():
    call_command("setup_roles")
    call_command("setup_roles")
    assert set(Group.objects.values_list("name", flat=True)) == set(ROLES)


def test_roles_never_manage_users_or_groups():
    for perms in ROLES.values():
        assert not [p for p in perms if p.startswith("auth.")]
