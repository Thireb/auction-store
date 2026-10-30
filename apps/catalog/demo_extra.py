"""A large demo catalog, made from short lists. Used by `manage.py seed_demo`.

Each subcategory lists its brands, a price range, a variant kind and item names. The seed
makes 1 product per name, with a brand, a condition and a price picked by a fixed random seed,
so every run makes the same products.
"""

# Variant kinds: None = 1 variant, "color", "size_eu", "length", "storage", "pack", "clothes".
VARIANT_OPTIONS = {
    "color": [("Black", 0), ("White", 0), ("Blue", 0)],
    "size_eu": [("40", 0), ("41", 0), ("42", 0), ("43", 0)],
    "length": [("1 m", 0), ("2 m", 0.2)],
    "storage": [("10000 mAh", 0), ("20000 mAh", 0.35)],
    "pack": [("Single", 0), ("Pack of 3", 1.6)],
    "clothes": [("S", 0), ("M", 0), ("L", 0), ("XL", 0)],
}

EXTRA_CATALOG = {
    "Furniture": {
        "Sofas": (
            ["Home Centre", "IKEA", "Pan Emirates"],
            (45000, 220000),
            None,
            [
                "L-shaped corner sofa",
                "Velvet 2-seater sofa",
                "Sofa cum bed",
                "Chesterfield sofa",
                "Modular 5-seater sofa",
            ],
        ),
        "Tables": (
            ["IKEA", "Home Centre", "Pan Emirates"],
            (9000, 95000),
            None,
            [
                "Marble top dining table",
                "Extendable dining table",
                "Nesting side tables, set of 3",
                "Study desk with drawers",
                "Console table",
                "Round bistro table",
            ],
        ),
        "Chairs": (
            ["IKEA", "Home Centre", "Herman Miller"],
            (6000, 85000),
            None,
            [
                "Ergonomic office chair",
                "Dining chairs, set of 4",
                "Bar stools, set of 2",
                "Accent armchair",
                "Gaming chair",
                "Rocking chair",
            ],
        ),
        "Beds": (
            ["IKEA", "Home Centre", "Pan Emirates"],
            (35000, 180000),
            None,
            [
                "King size bed with storage",
                "Queen size upholstered bed",
                "Single bed frame",
                "Bunk bed for kids",
                "Orthopedic mattress, king",
            ],
        ),
        "Wardrobes": (
            ["IKEA", "Home Centre"],
            (28000, 120000),
            None,
            ["3-door wardrobe", "Sliding door wardrobe", "Chest of drawers", "Shoe cabinet"],
        ),
    },
    "Mobile accessories": {
        "Chargers": (
            ["Anker", "Baseus", "Samsung", "Ugreen", "Apple"],
            (900, 9000),
            None,
            [
                "20W USB-C charger",
                "45W super fast charger",
                "Wireless charging pad",
                "3-in-1 wireless charging stand",
                "Car charger, dual port",
                "100W GaN desktop charger",
            ],
        ),
        "Cables": (
            ["Anker", "Baseus", "Ugreen"],
            (350, 2500),
            "length",
            [
                "USB-C to USB-C cable 60W",
                "USB-C to Lightning cable",
                "Micro USB cable, nylon",
                "Magnetic charging cable",
                "3-in-1 charging cable",
            ],
        ),
        "Phone cases": (
            ["Spigen", "Ringke", "Baseus"],
            (500, 3500),
            "color",
            [
                "Clear case for Galaxy S24",
                "Armor case for iPhone 14",
                "Leather wallet case for iPhone 15",
                "MagSafe case for iPhone 15 Pro",
                "Rugged case for Redmi Note 13",
            ],
        ),
        "Earbuds": (
            ["Anker", "Samsung", "JBL", "Xiaomi"],
            (2500, 28000),
            None,
            [
                "Noise cancelling earbuds",
                "Sports earbuds with ear hooks",
                "Galaxy Buds style earbuds",
                "Budget wireless earbuds",
                "Open-ear earbuds",
            ],
        ),
        "Power banks": (
            ["Anker", "Baseus", "Xiaomi"],
            (2500, 12000),
            "storage",
            ["Slim power bank", "Fast charge power bank 22.5W", "MagSafe power bank"],
        ),
        "Screen protectors": (
            ["Spigen", "Baseus"],
            (300, 1800),
            "pack",
            [
                "Tempered glass for iPhone 15",
                "Privacy glass for iPhone 14",
                "Tempered glass for Galaxy A54",
                "Camera lens protector",
            ],
        ),
        "Car holders": (
            ["Baseus", "Ugreen"],
            (800, 4500),
            None,
            ["Dashboard phone holder", "Air vent magnetic holder", "Wireless charging car mount"],
        ),
    },
    "Decor": {
        "Lamps": (
            ["IKEA", "Home Centre"],
            (2500, 25000),
            None,
            ["Arc floor lamp", "Rattan pendant light", "LED desk lamp", "Crystal table lamp"],
        ),
        "Wall art": (
            ["Home Centre"],
            (1800, 18000),
            None,
            ["Calligraphy wall frame", "Metal wall sculpture", "Set of 3 botanical prints"],
        ),
        "Vases": (
            ["Home Centre", "IKEA"],
            (1200, 9000),
            None,
            ["Tall floor vase", "Glass bud vases, set of 3", "Gold metal vase"],
        ),
        "Mirrors": (
            ["IKEA", "Home Centre"],
            (4500, 38000),
            None,
            ["Round wall mirror 80 cm", "Full length standing mirror", "Sunburst mirror"],
        ),
        "Rugs": (
            ["IKEA", "Home Centre"],
            (6000, 65000),
            None,
            ["Persian style rug 200x300", "Shaggy rug 160x230", "Kilim runner rug"],
        ),
    },
    "Shoes": {
        "Men's shoes": (
            ["Clarks", "Ecco", "Bata"],
            (5500, 28000),
            "size_eu",
            ["Leather loafers", "Suede desert boots", "Oxford shoes", "Leather sandals"],
        ),
        "Women's shoes": (
            ["Clarks", "Charles & Keith", "Aldo"],
            (3500, 22000),
            "size_eu",
            ["Block heel pumps", "Ballet flats", "Ankle boots", "Wedge sandals"],
        ),
        "Sneakers": (
            ["Nike", "Adidas", "Puma", "New Balance", "Skechers"],
            (6500, 38000),
            "size_eu",
            [
                "Running shoes, cushioned",
                "Court sneakers, white",
                "Trail running shoes",
                "Slip-on walking shoes",
                "Basketball shoes",
                "Retro suede sneakers",
            ],
        ),
    },
    "Watches": {
        "Smart watches": (
            ["Samsung", "Huawei", "Amazfit", "Xiaomi"],
            (4500, 75000),
            None,
            [
                "AMOLED smart watch",
                "GPS sports watch",
                "Kids smart watch with SIM",
                "Smart band with heart rate",
            ],
        ),
        "Analog watches": (
            ["Casio", "Fossil", "Seiko", "Citizen", "Tissot"],
            (6000, 120000),
            None,
            [
                "Automatic dress watch",
                "Diver style watch",
                "Rose gold ladies watch",
                "Field watch, canvas strap",
                "Two-tone steel watch",
            ],
        ),
    },
    "Kitchen": {
        "Cookware": (
            ["Tefal", "Prestige", "Tramontina"],
            (2500, 30000),
            None,
            [
                "Non-stick cookware set, 7 pieces",
                "Pressure cooker 5 litre",
                "Cast iron skillet",
                "Stainless steel stock pot",
                "Granite frying pan 28 cm",
            ],
        ),
        "Small appliances": (
            ["Philips", "Kenwood", "Black+Decker", "Tefal"],
            (4500, 55000),
            None,
            [
                "Air fryer 5.5 litre",
                "Stand mixer",
                "Blender with grinder jar",
                "Electric kettle 1.7 litre",
                "Sandwich maker",
                "Coffee machine with frother",
                "Juicer extractor",
            ],
        ),
        "Dinner sets": (
            ["Corelle", "Noritake", "Luminarc"],
            (6500, 48000),
            None,
            ["Dinner set, 72 pieces", "Porcelain tea set", "Glass serving bowls, set of 6"],
        ),
    },
    "Electronics": {
        "Headphones": (
            ["Sony", "JBL", "Bose", "Anker"],
            (4500, 85000),
            None,
            [
                "Over-ear noise cancelling headphones",
                "Studio monitor headphones",
                "Kids headphones",
                "Gaming headset with mic",
            ],
        ),
        "Speakers": (
            ["JBL", "Sony", "Anker"],
            (3500, 65000),
            None,
            [
                "Portable Bluetooth speaker",
                "Party speaker with lights",
                "Soundbar 2.1",
                "Smart speaker",
            ],
        ),
        "Laptop accessories": (
            ["Logitech", "Ugreen", "Baseus"],
            (1200, 18000),
            None,
            [
                "Wireless mouse",
                "Mechanical keyboard",
                "USB-C hub, 7 in 1",
                "Laptop stand, aluminium",
                "Webcam 1080p",
            ],
        ),
    },
    "Bags": {
        "Handbags": (
            ["Charles & Keith", "Aldo", "Guess"],
            (4500, 35000),
            None,
            ["Leather tote bag", "Crossbody bag", "Evening clutch", "Shoulder bag"],
        ),
        "Backpacks": (
            ["Samsonite", "American Tourister", "Nike"],
            (3500, 25000),
            None,
            ["Laptop backpack 15.6 inch", "School backpack", "Travel backpack 40 L"],
        ),
        "Luggage": (
            ["Samsonite", "American Tourister", "Delsey"],
            (12000, 95000),
            None,
            ["Hard shell cabin trolley", "Large check-in suitcase", "Luggage set of 3"],
        ),
    },
    "Perfumes": {
        "Men's perfume": (
            ["Lattafa", "Rasasi", "Armaf", "Ajmal"],
            (3500, 28000),
            None,
            ["Oud eau de parfum 100 ml", "Fresh citrus cologne", "Amber woody perfume"],
        ),
        "Women's perfume": (
            ["Lattafa", "Rasasi", "Ajmal"],
            (3500, 26000),
            None,
            ["Floral eau de parfum 100 ml", "Musk perfume oil", "Vanilla body mist"],
        ),
    },
    "Toys": {
        "Kids toys": (
            ["LEGO", "Mattel", "Hasbro"],
            (1500, 32000),
            None,
            [
                "Building blocks set, 500 pieces",
                "Remote control car",
                "Doll house with furniture",
                "Kids ride-on car",
                "Wooden puzzle set",
            ],
        ),
        "Board games": (
            ["Hasbro", "Mattel"],
            (1800, 9000),
            None,
            ["Family board game", "Chess set, wooden", "Card game party pack"],
        ),
    },
    "Clothing": {
        "Men's clothing": (
            ["Zara", "H&M", "Levi's"],
            (1800, 18000),
            "clothes",
            ["Denim jacket", "Polo shirt", "Slim fit chinos", "Puffer jacket"],
        ),
        "Women's clothing": (
            ["Zara", "H&M", "Mango"],
            (1800, 16000),
            "clothes",
            ["Knit cardigan", "Linen shirt", "Long trench coat", "Wide leg trousers"],
        ),
    },
    "Tools": {
        "Power tools": (
            ["Bosch", "Makita", "DeWalt", "Black+Decker"],
            (6500, 65000),
            None,
            [
                "Cordless drill 18V",
                "Angle grinder",
                "Impact driver kit",
                "Jigsaw",
                "Pressure washer",
            ],
        ),
        "Hand tools": (
            ["Stanley", "Bosch", "Tolsen"],
            (1200, 15000),
            None,
            ["Screwdriver set, 32 pieces", "Socket wrench set", "Tool box with tools"],
        ),
    },
    "Home appliances": {
        "Vacuum cleaners": (
            ["Philips", "Dyson", "Xiaomi"],
            (12000, 145000),
            None,
            ["Robot vacuum cleaner", "Cordless stick vacuum", "Wet and dry vacuum"],
        ),
        "Fans and heaters": (
            ["Xiaomi", "Philips", "Black+Decker"],
            (4500, 38000),
            None,
            ["Tower fan with remote", "Oil-filled heater", "Air purifier", "Pedestal fan"],
        ),
        "Irons": (
            ["Philips", "Tefal", "Braun"],
            (3500, 28000),
            None,
            ["Steam iron 2400W", "Garment steamer", "Dry iron"],
        ),
    },
    "Sports": {
        "Fitness": (
            ["Decathlon", "Reebok", "Adidas"],
            (1500, 95000),
            None,
            [
                "Adjustable dumbbells, pair",
                "Yoga mat 6 mm",
                "Foldable treadmill",
                "Exercise bike",
                "Resistance bands set",
            ],
        ),
        "Cycling": (
            ["Decathlon", "Giant"],
            (3500, 120000),
            None,
            ["Mountain bike 26 inch", "Kids bicycle 16 inch", "Cycling helmet"],
        ),
    },
}

# Subcategories that sell in bulk: big stock and bulk price tiers.
EXTRA_BULK = {"Power banks", "Screen protectors", "Car holders", "Laptop accessories"}
