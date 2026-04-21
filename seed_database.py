"""
Seed script – wypełnia bazę danych pseudo-rzeczywistymi danymi.
Wymagania: pip install psycopg2-binary faker

Użycie:
    python seed_database.py

Zmień stałe w sekcji CONFIG przed uruchomieniem.
"""

import random
from datetime import datetime, timedelta

import psycopg2
from psycopg2.extras import execute_values
from faker import Faker

# =============================================================
# CONFIG – dostosuj do swojego środowiska
# =============================================================
DB = dict(
    host="localhost",
    port=5432,
    database="system_biletowy",
    user="postgres",
    password="admin",
)

SEED             = 42
NUM_VENUES       = 100
EVENTS_PER_VENUE = 100
SEATS_PER_VENUE  = (300, 500)   # losowo z tego zakresu
NUM_PERFORMERS   = 500
NUM_USERS        = 5_000
BOOKINGS_PER_EVENT  = (2, 8)    # ile bookingów losujemy per event
TICKETS_PER_BOOKING = (1, 6)
# =============================================================
 
fake = Faker("pl_PL")
Faker.seed(SEED)
random.seed(SEED)
 
VENUE_TYPES = [
    ("Stadion Miejski",  "stadion"),
    ("Klub Muzyczny",    "klub"),
    ("Teatr Wielki",     "teatr"),
    ("Hala Widowiskowa", "hala"),
    ("Amfiteatr Letni",  "amfiteatr"),
    ("Opera",            "opera"),
    ("Dom Kultury",      "dom_kultury"),
    ("Arena Sportowa",   "arena"),
]
 
CATEGORIES = {
    "stadion":    [("Trybuna VIP", 1), ("Trybuna A",    2), ("Trybuna B",   3)],
    "klub":       [("VIP Lounge",  1), ("Parter",       2), ("Balkon",      3)],
    "teatr":      [("Parter",      1), ("Balkon I",     2), ("Balkon II",   3), ("Galeria", 4)],
    "hala":       [("Strefa VIP",  1), ("Sektory A-C",  2), ("Sektory D-F", 3)],
    "amfiteatr":  [("Premium",     1), ("Centralny",    2), ("Boczny",      3)],
    "opera":      [("Parter",      1), ("Loża",         2), ("Balkon",      3), ("Galeria", 4)],
    "dom_kultury":[("Rząd 1-5",    1), ("Rząd 6-15",    2), ("Rząd 16+",    3)],
    "arena":      [("Skybox",      1), ("Dolny",        2), ("Górny",       3)],
}
 
BASE_PRICES = {1: 350, 2: 180, 3: 100, 4: 60}
 
EVENT_NAMES = [
    "Wielki Festiwal", "Noc Muzyki", "Gala Otwarcia", "Koncert Jubileuszowy",
    "Letnie Brzmienia", "Zimowy Wieczór", "Premiera Sezonu", "Benefis",
    "Tournée", "Finałowy Koncert", "Spektakl Plenerowy", "Retrospektywa",
    "Jam Session", "Tribute Night", "Acoustic Evening", "Noc Jazzowa",
    "Festiwal Rockowy", "Gala Charytatywna", "Debiut", "Pożegnalne Show",
]

EVENT_DESCRIPTIONS = {
    "stadion": [
        "Wielkie sportowe widowisko na jednej z największych aren w Polsce. Emocje gwarantowane od pierwszego gwizdka do ostatniej minuty.",
        "Niepowtarzalna atmosfera trybun, tysiące kibiców i walka o najwyższe trofea. Nie możesz tego przegapić!",
        "Masowe wydarzenie sportowe z udziałem czołowych zawodników. Przyjdź i dopinguj swoich faworytów na żywo.",
    ],
    "klub": [
        "Kameralna noc w klimatycznym klubie z najlepszą muzyką na żywo. Idealne miejsce dla miłośników dobrego brzmienia.",
        "Ekskluzywna impreza z selekcjonowaną muzyką i wyjątkową atmosferą. Ilość miejsc ograniczona.",
        "Wieczór pełen rytmu i energii w jednym z najbardziej rozchwytywanych klubów w mieście.",
    ],
    "teatr": [
        "Spektakl w wykonaniu wybitnych artystów sceny – wzruszająca historia, która długo pozostanie w pamięci.",
        "Premierowe przedstawienie z udziałem gwiazd polskiego teatru. Kostiumy, scenografia i muzyka na najwyższym poziomie.",
        "Klasyka literatury w nowoczesnej interpretacji. Wieczór, który zachwyci zarówno stałych bywalców teatru, jak i debiutantów.",
    ],
    "hala": [
        "Spektakularne widowisko w największej hali regionu. Wielka scena, niesamowite efekty świetlne i dźwiękowe.",
        "Wydarzenie na skalę ogólnopolską – tysiące widzów, gwiazdy i niezapomniane emocje pod jednym dachem.",
        "Koncert w hali widowiskowej z doskonałą akustyką i panoramicznym widokiem na scenę z każdego miejsca.",
    ],
    "amfiteatr": [
        "Letni koncert pod gołym niebem – muzyka, gwiazdy i ciepłe noce tworzą magiczną atmosferę.",
        "Plenerowe wydarzenie w naturalnej scenerii amfiteatru. Przynieś koc, zostań na cały wieczór.",
        "Wyjątkowe brzmienie na świeżym powietrzu. Artyści, którzy wypełnią letnią noc niezapomnianymi melodiami.",
    ],
    "opera": [
        "Wieczór operowy z udziałem solistów klasy światowej. Muzyka, która porusza do głębi.",
        "Uroczysta gala operowa – elegancja, pasja i kunszt wokalistów w pięknej oprawie scenicznej.",
        "Arcydzieło repertuaru operowego w wykonaniu uznanej trupy. Dress code mile widziany.",
    ],
    "dom_kultury": [
        "Lokalne wydarzenie kulturalne łączące pokolenia – muzyka, taniec i wspólna zabawa dla całej rodziny.",
        "Kameralny wieczór artystyczny w sercu społeczności. Wstęp dla wszystkich miłośników kultury.",
        "Spotkanie z lokalną sceną artystyczną – odkryj talenty z Twojego miasta.",
    ],
    "arena": [
        "Widowiskowe wydarzenie na największej arenie w regionie – skalą i rozmachem nie ustępuje światowym standardom.",
        "Megakoncert z rozbudowaną produkcją sceniczną, efektami pirotechnicznymi i setami na żywo.",
        "Arena wypełniona po brzegi, energia nie do opisania. Zarezerwuj miejsce, zanim będzie za późno.",
    ],
}


def rand_description(vtype_key: str) -> str:
    return random.choice(EVENT_DESCRIPTIONS[vtype_key])
 
 
def rand_date(future: bool):
    if future:
        start = datetime.now() + timedelta(days=random.randint(7, 500))
    else:
        start = datetime.now() - timedelta(days=random.randint(1, 500))
    return start, start + timedelta(hours=random.choice([1, 2, 3]))
 
 
def bulk_insert(cur, table, cols, rows, page=2000):
    """Wstawia wiersze stronicami i zwraca listę id w kolejności wstawienia."""
    ids = []
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES %s RETURNING id"
    for i in range(0, len(rows), page):
        result = execute_values(cur, sql, rows[i:i + page], fetch=True)
        ids.extend(r[0] for r in result)
    assert len(ids) == len(rows), (
        f"bulk_insert({table}): oczekiwano {len(rows)} id, dostano {len(ids)}"
    )
    return ids
 
 
def bulk_insert_no_return(cur, table, cols, rows, page=2000):
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES %s"
    for i in range(0, len(rows), page):
        execute_values(cur, sql, rows[i:i + page])
 
 
def seed(conn):
    cur = conn.cursor()

    # ----------------------------------------------------------
    # 1. venues
    # ----------------------------------------------------------
    print("venues...", end=" ", flush=True)
    venue_rows = []
    venue_meta = []
    for i in range(NUM_VENUES):
        vtype_name, vtype_key = VENUE_TYPES[i % len(VENUE_TYPES)]
        city = fake.city()
        street = fake.street_address()
        venue_rows.append((f"{vtype_name} {city}", f"{street}, {city}"))
        venue_meta.append(vtype_key)
    venue_ids = bulk_insert(cur, "venues", ["name", "address"], venue_rows)
    print(len(venue_ids))

    # ----------------------------------------------------------
    # 2. seat_categories  (per venue)
    # ----------------------------------------------------------
    print("seat_categories...", end=" ", flush=True)
    cat_rows = []
    cat_meta = []
    for i, vid in enumerate(venue_ids):
        for cname, tier in CATEGORIES[venue_meta[i]]:
            cat_rows.append((vid, cname))
            cat_meta.append((vid, cname, tier))
    cat_ids = bulk_insert(cur, "seat_categories", ["venue_id", "name"], cat_rows)
    cat_map: dict[int, dict[str, tuple[int, int]]] = {}
    for idx, (vid, cname, tier) in enumerate(cat_meta):
        cat_map.setdefault(vid, {})[cname] = (cat_ids[idx], tier)
    print(len(cat_ids))

    # ----------------------------------------------------------
    # 3. seats
    # ----------------------------------------------------------
    print("seats...", end=" ", flush=True)
    seat_rows = []
    for i, vid in enumerate(venue_ids):
        cats = CATEGORIES[venue_meta[i]]
        total_seats = random.randint(*SEATS_PER_VENUE)
        seats_per_cat = max(1, total_seats // len(cats))
        global_row = 0
        for cname, _ in cats:
            cid, _ = cat_map[vid][cname]
            rows_n  = max(1, seats_per_cat // 15)
            seats_n = max(1, seats_per_cat // rows_n)
            for row_num in range(1, rows_n + 1):
                global_row += 1
                row_label = "R" + str(global_row)
                for sn in range(1, seats_n + 1):
                    seat_rows.append((vid, cid, row_label, sn))
    seat_ids_flat = bulk_insert(cur, "seats",
                                ["venue_id", "category_id", "seat_row", "seat_number"],
                                seat_rows)
    seat_map: dict[int, list[int]] = {vid: [] for vid in venue_ids}
    for idx, (vid, *_) in enumerate(seat_rows):
        seat_map[vid].append(seat_ids_flat[idx])
    print(sum(len(v) for v in seat_map.values()))

    # ----------------------------------------------------------
    # 4. performers
    # ----------------------------------------------------------
    print("performers...", end=" ", flush=True)
    perf_rows = []
    for _ in range(NUM_PERFORMERS):
        name = random.choice([
            fake.name(),
            f"Zespół {fake.last_name()}",
            f"DJ {fake.first_name()}",
            f"Orkiestra {fake.city()}",
        ])
        perf_rows.append((name,))
    performer_ids = bulk_insert(cur, "performers", ["name"], perf_rows)
    print(len(performer_ids))

    # ----------------------------------------------------------
    # 5. events
    # ----------------------------------------------------------
    print("events...", end=" ", flush=True)
    event_rows = []
    event_venue = []
    for i, vid in enumerate(venue_ids):
        for _ in range(EVENTS_PER_VENUE):
            name = f"{random.choice(EVENT_NAMES)} {fake.last_name()}"
            ds, de = rand_date(random.random() < 0.6)
            event_rows.append((name, vid, ds, de, rand_description(venue_meta[i])))
            event_venue.append(vid)
    event_ids = bulk_insert(cur, "events",
                            ["name", "venue_id", "date_start", "date_end", "description"],
                            event_rows)
    event_map: dict[int, list[int]] = {vid: [] for vid in venue_ids}
    for idx, vid in enumerate(event_venue):
        event_map[vid].append(event_ids[idx])
    print(len(event_ids))

    # ----------------------------------------------------------
    # 6. event_performers (1–4 per event)
    # ----------------------------------------------------------
    print("event_performers...", end=" ", flush=True)
    ep_set: set[tuple[int, int]] = set()
    for eid in event_ids:
        for pid in random.sample(performer_ids, k=random.randint(1, 4)):
            ep_set.add((eid, pid))
    bulk_insert_no_return(cur, "event_performers",
                          ["event_id", "performer_id"], list(ep_set))
    print(len(ep_set))

    # ----------------------------------------------------------
    # 7. event_category_prices
    # ----------------------------------------------------------
    print("event_category_prices...", end=" ", flush=True)
    ecp_rows = []
    for i, vid in enumerate(venue_ids):
        for eid in event_map[vid]:
            for cname, tier in CATEGORIES[venue_meta[i]]:
                cid, _ = cat_map[vid][cname]
                price = round(BASE_PRICES[tier] * random.uniform(0.7, 1.5), 2)
                ecp_rows.append((eid, cid, price))
    bulk_insert_no_return(cur, "event_category_prices",
                          ["event_id", "category_id", "price"], ecp_rows)
    print(len(ecp_rows))

    # ----------------------------------------------------------
    # 8. users
    # ----------------------------------------------------------
    print("users...", end=" ", flush=True)
    user_rows = [(fake.unique.email(), fake.name()) for _ in range(NUM_USERS)]
    user_ids = bulk_insert(cur, "users", ["email", "name"], user_rows)
    print(len(user_ids))

   # ----------------------------------------------------------
    # 9. tickets (available) + bookings + aktualizacja ticketów
    # ----------------------------------------------------------
    print("tickets (available)...", end=" ", flush=True)

    # Krok 1: wstaw wszystkie tickety jako available
    available_ticket_rows = []
    # (event_id, seat_id) -> ticket_id – potrzebne do UPDATE
    ticket_id_map: dict[tuple[int, int], int] = {}

    for vid in venue_ids:
        for eid in event_map[vid]:
            for sid in seat_map[vid]:
                available_ticket_rows.append((eid, sid, None, 0, "available", None))

    ticket_ids = bulk_insert(cur, "tickets",
                             ["event_id", "seat_id", "booking_id", "price",
                              "status", "reserved_until"],
                             available_ticket_rows)

    for idx, (eid, sid, *_) in enumerate(available_ticket_rows):
        ticket_id_map[(eid, sid)] = ticket_ids[idx]

    print(len(ticket_ids))

    # Krok 2: bookings
    print("bookings + tickets update...", end=" ", flush=True)

    event_date_map  = {eid: event_rows[i][2] for i, eid in enumerate(event_ids)}
    event_venue_map = {eid: event_venue[i]   for i, eid in enumerate(event_ids)}

    booking_rows = []
    booking_event_meta = []  # (event_id, b_status, created_at)
    taken: dict[int, set[int]] = {eid: set() for eid in event_ids}

    for vid in venue_ids:
        for eid in event_map[vid]:
            is_future = event_date_map[eid] > datetime.now()
            for _ in range(random.randint(*BOOKINGS_PER_EVENT)):
                uid = random.choice(user_ids)
                if is_future:
                    b_status = random.choices(
                        ["pending", "confirmed", "cancelled"], [30, 50, 20]
                    )[0]
                else:
                    b_status = random.choices(
                        ["confirmed", "cancelled"], [75, 25]
                    )[0]
                created = fake.date_time_between("-365d", "now")
                booking_rows.append((uid, created, b_status))
                booking_event_meta.append((eid, b_status, created))

    booking_ids = bulk_insert(cur, "bookings",
                              ["user_id", "created_at", "status"], booking_rows)

    # Krok 3: UPDATE ticketów przypisanych do bookingów
    ticket_updates = []  # (booking_id, status, reserved_until, ticket_id)

    for b_idx, bid in enumerate(booking_ids):
        eid, b_status, created = booking_event_meta[b_idx]
        vid = event_venue_map[eid]

        if b_status == "cancelled":
            continue

        free = [s for s in seat_map[vid] if s not in taken[eid]]
        if not free:
            continue

        n = min(random.randint(*TICKETS_PER_BOOKING), len(free))
        chosen = random.sample(free, k=n)

        for sid in chosen:
            taken[eid].add(sid)
            tid = ticket_id_map[(eid, sid)]

            if b_status == "confirmed":
                t_status, reserved_until = "sold", None
            else:  # pending
                t_status = "reserved"
                reserved_until = created + timedelta(minutes=random.randint(15, 60))

            ticket_updates.append((bid, t_status, reserved_until, tid))

    # Bulk UPDATE przez execute_values
    execute_values(
        cur,
        """
        UPDATE tickets AS t SET
            booking_id     = u.booking_id::int,
            status         = u.status,
            reserved_until = u.reserved_until::timestamp
        FROM (VALUES %s) AS u(booking_id, status, reserved_until, id)
        WHERE t.id = u.id::int
        """,
        ticket_updates,
    )

    print(f"{len(booking_ids)} bookings, "
          f"{len(ticket_updates)} tickets zaktualizowanych, "
          f"{len(ticket_ids) - len(ticket_updates)} available")

    conn.commit()
    cur.close()
 
if __name__ == "__main__":
    print("Łączenie z bazą danych...")
    conn = psycopg2.connect(**DB)
    try:
        print("Generowanie danych:\n")
        seed(conn)
        print("\nGotowe!")
    except Exception as e:
        conn.rollback()
        print(f"\nBłąd – rollback: {e}")
        raise
    finally:
        conn.close()