"""
Human-readable names and geocoding hints for every stop token used in routes_source.py.

LANDMARKS maps a token to (display name, search query, area).
The search query is sent to OpenStreetMap Nominatim by tools/build_data.py.
If OSM does not know a place, add its coordinates to MANUAL_COORDS instead.

Sector tokens (S22, 22/17, M82, P4 ...) are generated automatically:
a junction "22/17" is placed at the midpoint between the centres of Sector 22 and
Sector 17, which is where the light point / bus stop between them is.
"""

CHD, MOH, PKL, ZRK, NCH = "Chandigarh", "Mohali", "Panchkula", "Zirakpur", "New Chandigarh"

LANDMARKS = {
    # --- Chandigarh hubs ---
    "ISBT17": ("ISBT Sector 17", "ISBT Sector 17, Chandigarh", CHD),
    "ISBT43": ("ISBT Sector 43", "Inter State Bus Terminal Sector 43, Chandigarh", CHD),
    "PGI": ("PGIMER", "Post Graduate Institute of Medical Education and Research, Chandigarh", CHD),
    "NEW_OPD": ("PGI New OPD", "New OPD, PGIMER, Chandigarh", CHD),
    "PEC": ("Punjab Engineering College", "Punjab Engineering College, Chandigarh", CHD),
    "PU": ("Panjab University", "Panjab University, Sector 14, Chandigarh", CHD),
    "AROMA": ("Aroma Chowk (Sector 22)", "Aroma Light Point, Chandigarh", CHD),
    "PICCADILLY": ("Piccadilly Chowk", "Piccadilly Chowk, Chandigarh", CHD),
    "KISAN_BHAWAN": ("Kisan Bhawan (Sector 35)", "Kisan Bhawan, Sector 35, Chandigarh", CHD),
    "ATTAWA": ("Attawa (Sector 42)", "Attawa, Chandigarh", CHD),
    "MATKA": ("Matka Chowk", "Matka Chowk, Chandigarh", CHD),
    "ROSE_GARDEN": ("Rose Garden (Sector 16)", "Zakir Hussain Rose Garden, Chandigarh", CHD),
    "GMCH16": ("Govt. Hospital Sector 16", "Government Multi Specialty Hospital, Sector 16, Chandigarh", CHD),
    "GMCH32": ("GMCH Sector 32", "Government Medical College and Hospital, Sector 32, Chandigarh", CHD),
    "TRIBUNE": ("Tribune Chowk", "Tribune Chowk, Chandigarh", CHD),
    "ELANTE": ("Elante Mall", "Elante Mall, Chandigarh", CHD),
    "RLY": ("Chandigarh Railway Station", "Chandigarh Railway Station", CHD),
    "RLY_CROSSING": ("Railway Crossing (Mani Majra)", "Railway Crossing, Manimajra, Chandigarh", CHD),
    "CTU_WS": ("CTU Workshop (Industrial Area)", "CTU Workshop, Industrial Area Phase 1, Chandigarh", CHD),
    "IND_PH1": ("Industrial Area Phase-1", "Industrial Area Phase 1, Chandigarh", CHD),
    "IND_PH2": ("Industrial Area Phase-2", "Industrial Area Phase 2, Chandigarh", CHD),
    "COLONY4": ("Colony No. 4", "Colony Number 4, Chandigarh", CHD),
    "TPT": ("Transport Chowk", "Transport Chowk, Chandigarh", CHD),
    "GRAIN_MKT26": ("Grain Market Sector 26", "Grain Market, Sector 26, Chandigarh", CHD),
    "POULTRY_FARM": ("Poultry Farm Chowk", "Poultry Farm Chowk, Chandigarh", CHD),
    "KALAGRAM": ("Kalagram", "Kalagram, Chandigarh", CHD),
    "HB_CHOWK": ("Housing Board Chowk", "Housing Board Chowk, Chandigarh", CHD),
    "MANIMAJRA": ("Mani Majra", "Mani Majra, Chandigarh", CHD),
    "INDIRA_COLONY": ("Indira Colony", "Indira Colony, Manimajra, Chandigarh", CHD),
    "FUN_REPUBLIC": ("Fun Republic (Mani Majra)", "Fun Republic, Manimajra, Chandigarh", CHD),
    "KISHANGARH": ("Kishangarh", "Kishangarh, Chandigarh", CHD),
    "IT_PARK": ("Chandigarh IT Park", "Rajiv Gandhi Chandigarh Technology Park", CHD),
    "MANSA_DEVI": ("Mata Mansa Devi Temple", "Mata Mansa Devi Mandir, Panchkula", PKL),
    "SAKETRI": ("Saketri", "Saketri, Panchkula", PKL),
    "SUKHNA": ("Sukhna Lake", "Sukhna Lake, Chandigarh", CHD),
    "ROCK_GARDEN": ("Rock Garden", "Rock Garden of Chandigarh", CHD),
    "BIRD_PARK": ("Bird Park", "Bird Park, Chandigarh", CHD),
    "HIGH_COURT": ("Punjab & Haryana High Court", "Punjab and Haryana High Court, Chandigarh", CHD),
    "CIVIL_SECTT": ("Punjab Civil Secretariat", "Punjab Civil Secretariat, Chandigarh", CHD),
    "UT_SECTT": ("UT Secretariat (Sector 9)", "UT Secretariat, Sector 9, Chandigarh", CHD),
    "MLA_FLAT": ("MLA Flats (Sector 3/4)", "MLA Hostel, Sector 4, Chandigarh", CHD),
    "KAIMBWALA": ("Kaimbwala", "Kaimbwala, Chandigarh", CHD),
    "RAM_DARBAR": ("Ram Darbar", "Ram Darbar, Chandigarh", CHD),
    "JAGATPURA": ("Jagatpura (Sector 48)", "Jagatpura, Chandigarh", CHD),
    "MALOYA": ("Maloya", "Maloya, Chandigarh", CHD),
    "NEW_MALOYA": ("New Maloya Colony", "Maloya Colony, Chandigarh", CHD),
    "DADU_MAJRA": ("Dadu Majra", "Dadu Majra, Chandigarh", CHD),
    "DMC": ("Dadu Majra Colony", "Dadu Majra Colony, Chandigarh", CHD),
    "DHANAS": ("Dhanas", "Dhanas, Chandigarh", CHD),
    "SP_BARRIER": ("Sarangpur Barrier", "Sarangpur, Chandigarh", CHD),
    "KHUDA_LAHORA": ("Khuda Lahora", "Khuda Lahora, Chandigarh", CHD),
    "KHUDA_ALISHER": ("Khuda Ali Sher", "Khuda Ali Sher, Chandigarh", CHD),
    "NAYAGAON": ("Nayagaon", "Naya Gaon, Punjab", NCH),
    "BADI_KARORAN": ("Badi Karoran", "Karoran, Punjab", NCH),
    "HALLOMAJRA": ("Hallo Majra", "Hallomajra, Chandigarh", CHD),
    "RAIPUR_KALAN": ("Raipur Kalan", "Raipur Kalan, Chandigarh", CHD),
    "MAULI_JAGRAN": ("Mauli Jagran", "Mauli Jagran, Chandigarh", CHD),
    "BEHLANA": ("Behlana", "Behlana, Chandigarh", CHD),
    "AIRPORT_CHOWK": ("Airport Light Point (Zirakpur road)", "Airport Road Chowk, Chandigarh", CHD),
    "BADHERI": ("Badheri Chowk", "Badheri, Chandigarh", CHD),
    "JAYANTI_MAJRI": ("Jayanti Majri", "Jayanti Majri, Punjab", MOH),
    "COMMAND_HOSPITAL": ("Command Hospital, Chandimandir", "Command Hospital Chandimandir", PKL),
    "CHANDIMANDIR": ("Chandimandir Cantonment", "Chandimandir Cantonment", PKL),
    "MAJRI_CHOWK": ("Majri Chowk", "Majri Chowk, Panchkula", PKL),
    "NADA_SAHIB": ("Gurudwara Nada Sahib", "Gurudwara Nada Sahib, Panchkula", PKL),
    "OLD_PANCHKULA": ("Old Panchkula", "Old Panchkula", PKL),
    "PANCHKULA_BS": ("Panchkula Bus Stand", "Panchkula Bus Stand, Sector 5, Panchkula", PKL),
    "RAMGARH": ("Ramgarh", "Ramgarh, Panchkula", PKL),
    "DHAKOLI": ("Dhakoli", "Dhakoli, Zirakpur", ZRK),
    "ZIRAKPUR": ("Zirakpur", "Zirakpur, Punjab", ZRK),
    "BALTANA": ("Baltana", "Baltana, Zirakpur", ZRK),
    "BHABHAT": ("Bhabhat", "Bhabat, Zirakpur", ZRK),
    "BHANKHARPUR": ("Bhankharpur", "Bhankharpur, Punjab", ZRK),
    "MUBARAKPUR": ("Mubarakpur", "Mubarakpur, Dera Bassi", ZRK),
    "DERABASSI": ("Dera Bassi", "Dera Bassi, Punjab", ZRK),
    "CHHATBIR": ("Chhatbir Zoo", "Mahendra Chaudhary Zoological Park, Chhatbir", ZRK),
    "MULLANPUR": ("Mullanpur", "Mullanpur Garibdass, Punjab", NCH),
    "ECO_CITY": ("Eco City, New Chandigarh", "Omaxe New Chandigarh", NCH),
    "NEW_CHANDIGARH": ("Omaxe, New Chandigarh", "Omaxe New Chandigarh", NCH),
    "RANI_MAJRA": ("Rani Majra", "Rani Majra, Punjab", NCH),
    "PAROL": ("Parol", "Parol, Punjab", NCH),
    "BOOTHGARH": ("Boothgarh", "Boothgarh, Punjab", NCH),
    "KHIZRABAD": ("Khizrabad", "Khizrabad, Punjab", NCH),
    "KURALI": ("Kurali", "Kurali, Punjab", NCH),
    # --- Mohali ---
    "MOHALI_PH2": ("Mohali Phase 2", "Phase 2, Mohali", MOH),
    "MOHALI_PH3_5": ("Phase 3/5 Light Point, Mohali", "Phase 5, Mohali", MOH),
    "MOHALI_PH6": ("Mohali Phase 6", "Phase 6, Mohali", MOH),
    "MOHALI_ISBT": ("Mohali ISBT (Phase 6)", "Mohali Bus Stand", MOH),
    "MOHALI_PH7": ("Phase 7 Light Point, Mohali", "Phase 7, Mohali", MOH),
    "MOHALI_PH8": ("Mohali Phase 8", "Phase 8, Mohali", MOH),
    "MOHALI_PH11": ("Mohali Phase 11", "Phase 11, Mohali", MOH),
    "IND_PH9_MOHALI": ("Industrial Area Phase 9, Mohali", "Industrial Area Phase 9, Mohali", MOH),
    "MOHALI_RLY": ("Mohali Railway Station", "Sahibzada Ajit Singh Nagar railway station", MOH),
    "YPS": ("YPS Chowk", "YPS Chowk, Mohali", MOH),
    "CHAWLA_CHOWK": ("Chawla Chowk, Mohali", "Chawla Chowk, Mohali", MOH),
    "FURNITURE_CHOWK": ("Furniture Market Chowk", "Furniture Market, Mohali", MOH),
    "MADANPUR": ("Madanpur Chowk", "Madanpur, Mohali", MOH),
    "IVY": ("Ivy Hospital, Mohali", "Ivy Hospital, Sector 71, Mohali", MOH),
    "PSEB": ("PSEB (Punjab School Education Board)", "Punjab School Education Board, Mohali", MOH),
    "FORTIS": ("Fortis Hospital, Mohali", "Fortis Hospital, Mohali", MOH),
    "KUMBRA": ("Kumbra", "Kumbra, Mohali", MOH),
    "SOHANA": ("Sohana", "Sohana, Mohali", MOH),
    "IISER": ("IISER Mohali (Sector 81)", "IISER Mohali", MOH),
    "AEROCITY": ("Aerocity, Mohali", "Aerocity, Mohali", MOH),
    "AMITY": ("Amity University, Mohali", "Amity University Punjab, Mohali", MOH),
    "PLAKSHA": ("Plaksha University", "Plaksha University", MOH),
    "TANGORI": ("Tangori", "Tangori, Punjab", MOH),
    "MOHALI_AIRPORT_CHOWK": ("Airport Road Chowk, Mohali", "Airport Road, Sector 82, Mohali", MOH),
    "JHURHERI": ("Jhurheri", "Jhurheri, Mohali", MOH),
    "CHD_AIRPORT": ("Chandigarh International Airport", "Chandigarh International Airport", MOH),
    "MANAULI": ("Manauli", "Manauli, Mohali", MOH),
    "BALONGI": ("Balongi", "Balongi, Mohali", MOH),
    "DAUN": ("Daun", "Daun, Mohali", MOH),
    "DESUMAJRA": ("Desu Majra", "Desu Majra, Kharar", MOH),
    "KHARAR": ("Kharar Bus Stand", "Kharar Bus Stand", MOH),
    "SEC123": ("Sector 123 (Sunny Enclave)", "Sunny Enclave, Kharar", MOH),
    "LANDRAN": ("Landran", "Landran, Punjab", MOH),
    "LAKHNAUR": ("Lakhnaur", "Lakhnaur, Mohali", MOH),
    "CHAPPAR_CHIRI": ("Chappar Chiri", "Chappar Chiri, Punjab", MOH),
    "SANTE_MAJRA": ("Sante Majra", "Sante Majra, Kharar", MOH),
}

# Coordinates (lat, lng) used instead of a search, because OSM's answer for the
# query above was missing or pointed at the wrong place.
# "osm" = taken from an OpenStreetMap lookup with a shorter name (reliable).
# "est" = estimated by hand from the map (approximate, please verify on the ground).
MANUAL_COORDS = {
    "PGI": (30.76354, 76.77475),            # osm "PGIMER"
    "NEW_OPD": (30.76090, 76.77652),        # osm "Nehru Hospital" (PGI)
    "ISBT43": (30.71632, 76.74466),         # osm "ISBT 43"
    "AROMA": (30.73011, 76.77338),          # osm "Hotel Aroma"
    "HB_CHOWK": (30.70822, 76.83741),       # osm "Housing Board Chowk"
    "MANIMAJRA": (30.71275, 76.83294),      # osm "Manimajra"
    "INDIRA_COLONY": (30.72240, 76.84428),  # osm "Indira Colony"
    "ROSE_GARDEN": (30.74582, 76.78148),    # osm "Rose Garden"
    "GMCH16": (30.75088, 76.78091),         # osm "GMSH 16"
    "GMCH32": (30.70916, 76.78131),         # osm "GMCH"
    "MANSA_DEVI": (30.72380, 76.86083),     # osm "Mansa Devi"
    "JAGATPURA": (30.68239, 76.76057),      # osm "Jagatpura"
    "ROCK_GARDEN": (30.75320, 76.80663),    # osm "Rock Garden"
    "NAYAGAON": (30.77393, 76.79025),       # osm "Nayagaon"
    "ATTAWA": (30.72663, 76.75025),         # osm "Atawa"
    "YPS": (30.70388, 76.73721),            # osm "Yadavindra Public School"
    "COMMAND_HOSPITAL": (30.71325, 76.85518),  # osm "Command Hospital"
    "NADA_SAHIB": (30.69420, 76.88090),     # osm "Nada Sahib"
    "FUN_REPUBLIC": (30.71316, 76.84426),   # osm "Fun Republic"
    "FURNITURE_CHOWK": (30.72591, 76.73193),  # osm "Furniture Market"
    "DESUMAJRA": (30.73863, 76.67144),      # osm "Desu Majra"
    "MOHALI_ISBT": (30.73200, 76.70594),    # osm "Mohali ISBT"
    "CHAWLA_CHOWK": (30.70834, 76.72408),   # osm "Chawla Nursing Home"
    "MULLANPUR": (30.78800, 76.71100),      # est
    "ECO_CITY": (30.79500, 76.72300),       # est (Omaxe, New Chandigarh)
    "NEW_CHANDIGARH": (30.79500, 76.72300),  # est
    "IT_PARK": (30.72750, 76.84650),        # est
    "BALONGI": (30.73000, 76.69600),        # est
    "DAUN": (30.73300, 76.68300),           # est
    "TANGORI": (30.62650, 76.69900),        # est
    "AMITY": (30.64050, 76.72600),          # est (Sector 82A, north of Plaksha)
    "CHHATBIR": (30.60300, 76.79300),       # est
    "SEC123": (30.73850, 76.66500),         # est (Sunny Enclave, Sector 123-125)
    "KHARAR": (30.74500, 76.64600),         # est (OSM bus-stand hit was ~10 km off)
    "MOHALI_PH7": (30.71200, 76.71650),     # est (Phase 7 light point; OSM area centre was ~2 km off)
}

# Points placed at the average of other tokens (e.g. a chowk where several sectors meet).
DERIVED = {
    "PICCADILLY": ["S20", "S21", "S33", "S34"],
    "TPT": ["S26", "S28"],
    "GRAIN_MKT26": ["S26"],
    "RLY_CROSSING": ["RLY", "MANIMAJRA"],
    "COLONY4": ["ELANTE", "RLY"],
    "CTU_WS": ["IND_PH1", "RLY"],
    "POULTRY_FARM": ["TRIBUNE", "COLONY4"],
    "UT_SECTT": ["S9"],
    "MLA_FLAT": ["S3", "S4"],
    "CIVIL_SECTT": ["HIGH_COURT", "S1"],
    "AIRPORT_CHOWK": ["HALLOMAJRA", "ZIRAKPUR"],
    "JHURHERI": ["MOHALI_AIRPORT_CHOWK", "CHD_AIRPORT"],
    "MADANPUR": ["MOHALI_PH3_5", "FURNITURE_CHOWK"],
}

# Places students search for that are not bus stops themselves (shown as destinations).
POPULAR = [
    # (id, name, icon, category, token-or-coords, aliases)
    ("plaksha", "Plaksha University", "🏫", "Campus", "PLAKSHA", "plaksha campus university college"),
    ("sec17", "Sector 17 Plaza", "🛍️", "Shopping", "S17", "sector 17 plaza neelam market"),
    ("isbt17", "ISBT Sector 17", "🚌", "Bus terminal", "ISBT17", "isbt 17 bus stand"),
    ("isbt43", "ISBT Sector 43", "🚌", "Bus terminal", "ISBT43", "isbt 43 bus stand"),
    ("railway", "Chandigarh Railway Station", "🚉", "Transit", "RLY", "railway station train rly"),
    ("elante", "Elante Mall", "🛍️", "Shopping", "ELANTE", "elante mall movies"),
    ("pgi", "PGIMER", "🏥", "Hospital", "PGI", "pgi hospital pgimer"),
    ("pu", "Panjab University", "🎓", "Education", "PU", "pu panjab university"),
    ("sukhna", "Sukhna Lake", "🌅", "Leisure", "SUKHNA", "sukhna lake"),
    ("rockgarden", "Rock Garden", "🪨", "Leisure", "ROCK_GARDEN", "rock garden nek chand"),
    ("sec22", "Sector 22 Market", "🛒", "Market", "S22", "sector 22 shastri market aroma"),
    ("sec35", "Sector 35 Market", "🍜", "Food", "S35", "sector 35 food"),
    ("ph7", "Mohali Phase 7", "🛒", "Market", "MOHALI_PH7", "phase 7 mohali market"),
    ("fortis", "Fortis Hospital, Mohali", "🏥", "Hospital", "FORTIS", "fortis hospital"),
    ("itpark", "Chandigarh IT Park", "💼", "Work", "IT_PARK", "it park tech"),
    ("airport", "Chandigarh Airport", "✈️", "Transit", "CHD_AIRPORT", "airport flight"),
    ("mohalirly", "Mohali Railway Station", "🚉", "Transit", "MOHALI_RLY", "mohali railway station train"),
    ("iiser", "IISER Mohali", "🎓", "Education", "IISER", "iiser"),
    ("tribune", "Tribune Chowk", "🛣️", "Junction", "TRIBUNE", "tribune chowk"),
    ("kharar", "Kharar", "🏘️", "Town", "KHARAR", "kharar"),
    ("zirakpur", "Zirakpur", "🏘️", "Town", "ZIRAKPUR", "zirakpur"),
    ("panchkula", "Panchkula Bus Stand", "🚌", "Bus terminal", "PANCHKULA_BS", "panchkula"),
]
