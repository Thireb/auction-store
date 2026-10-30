"""Demo customers, wholesale buyers and staff. Used by `manage.py seed_demo`.

Demo accounts get no usable password, so nobody can sign in with them on a live store.
The owner can set a password in the admin to try them.
"""

import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command

from apps.core import roles

from .models import WholesaleProfile

CUSTOMERS = [
    # phone, first name, last name, city
    ("+923001110001", "Ayesha", "Khan", "Lahore"),
    ("+923001110002", "Bilal", "Ahmed", "Karachi"),
    ("+923001110003", "Sana", "Malik", "Islamabad"),
    ("+923001110004", "Usman", "Raza", "Rawalpindi"),
    ("+923001110005", "Hira", "Siddiqui", "Faisalabad"),
    ("+923001110006", "Imran", "Qureshi", "Multan"),
    ("+923001110007", "Fatima", "Sheikh", "Peshawar"),
    ("+923001110008", "Hamza", "Butt", "Gujranwala"),
    ("+923001110009", "Zainab", "Chaudhry", "Sialkot"),
    ("+923001110010", "Ali", "Hassan", "Hyderabad"),
    ("+923001110011", "Mariam", "Javed", "Quetta"),
    ("+923001110012", "Omar", "Farooq", "Lahore"),
    ("+923001110013", "Nida", "Aslam", "Karachi"),
    ("+923001110014", "Fahad", "Iqbal", "Islamabad"),
    ("+923001110015", "Rabia", "Anwar", "Abbottabad"),
    ("+923001110016", "Saad", "Mirza", "Bahawalpur"),
    ("+923001110017", "Amna", "Tariq", "Sargodha"),
    ("+923001110018", "Kashif", "Nawaz", "Sukkur"),
]

WHOLESALE = [
    # phone, first name, last name, city, business, status
    (
        "+923002220001",
        "Asif",
        "Mehmood",
        "Lahore",
        "Hafeez Centre Mobile Zone",
        WholesaleProfile.APPROVED,
    ),
    (
        "+923002220002",
        "Rizwan",
        "Shah",
        "Karachi",
        "Saddar Accessories Traders",
        WholesaleProfile.APPROVED,
    ),
    (
        "+923002220003",
        "Naveed",
        "Akhtar",
        "Rawalpindi",
        "Raja Bazaar Gadgets",
        WholesaleProfile.APPROVED,
    ),
    ("+923002220004", "Tahir", "Abbas", "Multan", "Multan Phone House", WholesaleProfile.PENDING),
    ("+923002220005", "Junaid", "Saleem", "Peshawar", "Khyber Mobiles", WholesaleProfile.REJECTED),
]

STAFF = [
    # username, first name, last name, role
    ("demo-inventory", "Kamran", "Yousaf", roles.INVENTORY_MANAGER),
    ("demo-orders", "Sadia", "Rehman", roles.ORDER_MANAGER),
]


def _user(username, first, last, **extra):
    User = get_user_model()
    user, created = User.objects.get_or_create(
        username=username, defaults={"first_name": first, "last_name": last, **extra}
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def seed_people(stdout=None):
    if Group.objects.filter(name__in=[role for *_, role in STAFF]).count() != len(STAFF):
        call_command("setup_roles", stdout=io.StringIO())
    for phone, first, last, _city in CUSTOMERS:
        _user(phone, first, last, email=f"{first.lower()}.{last.lower()}@example.com")
    for phone, first, last, city, business, status in WHOLESALE:
        user = _user(phone, first, last)
        WholesaleProfile.objects.get_or_create(
            user=user,
            defaults={
                "business_name": business,
                "city": city,
                "details": "Mobile accessories shop. Buys chargers, cables and cases in bulk.",
                "status": status,
            },
        )
    for username, first, last, role in STAFF:
        user = _user(username, first, last, is_staff=True)
        user.groups.add(Group.objects.get(name=role))
    if stdout:
        stdout.write(
            f"People: {len(CUSTOMERS)} customers, {len(WHOLESALE)} wholesale buyers, "
            f"{len(STAFF)} staff (no passwords)."
        )
