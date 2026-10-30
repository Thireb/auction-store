"""Main Pakistani cities. `manage.py load_cities` adds them; fees stay empty (use the defaults)."""

CITIES = {
    "punjab": [
        "Lahore",
        "Faisalabad",
        "Rawalpindi",
        "Gujranwala",
        "Multan",
        "Sialkot",
        "Bahawalpur",
        "Sargodha",
        "Sheikhupura",
        "Jhang",
        "Rahim Yar Khan",
        "Gujrat",
        "Kasur",
        "Sahiwal",
        "Okara",
        "Dera Ghazi Khan",
        "Wah Cantt",
        "Chiniot",
        "Kamoke",
        "Mandi Bahauddin",
        "Jhelum",
        "Sadiqabad",
        "Khanewal",
        "Hafizabad",
        "Muzaffargarh",
        "Khanpur",
        "Attock",
    ],
    "sindh": [
        "Karachi",
        "Hyderabad",
        "Sukkur",
        "Larkana",
        "Nawabshah",
        "Mirpur Khas",
        "Jacobabad",
        "Shikarpur",
        "Khairpur",
        "Dadu",
        "Thatta",
    ],
    "kp": [
        "Peshawar",
        "Mardan",
        "Abbottabad",
        "Mingora",
        "Kohat",
        "Dera Ismail Khan",
        "Mansehra",
        "Nowshera",
        "Swabi",
        "Charsadda",
        "Bannu",
    ],
    "balochistan": ["Quetta", "Turbat", "Khuzdar", "Gwadar", "Hub", "Chaman"],
    "ict": ["Islamabad"],
    "gb": ["Gilgit", "Skardu"],
    "ajk": ["Muzaffarabad", "Mirpur", "Kotli"],
}

TOP_CITIES = ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad", "Multan", "Peshawar"]


def load_cities():
    from .models import City

    created = 0
    for province, names in CITIES.items():
        for name in names:
            order = TOP_CITIES.index(name) if name in TOP_CITIES else 100
            _, new = City.objects.get_or_create(
                name=name, defaults={"province": province, "sort_order": order}
            )
            created += new
    return created
