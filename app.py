from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor


app = Flask(__name__)
app.secret_key = 'pwr_projekt_secret'

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="system_biletowy",
        user="postgres",
        password="admin"
    )

def cleanup_expired_reservations():
    """Przeniesienie logiki wygasania rezerwacji do aplikacji."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE tickets 
            SET status = 'free', reserved_until = NULL, booking_id = NULL 
            WHERE status = 'reserved' AND reserved_until < NOW();
        ''')
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd sprzątania: {e}")
    finally:
        cur.close()
        conn.close()


@app.route('/shop')
def shop_index():
    cleanup_expired_reservations()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Pobieramy wydarzenia z informacją o wykonawcach
    cur.execute('''
                SELECT e.*, v.name as venue_name, STRING_AGG(p.name, ', ') as performers
                FROM events e
                         JOIN venues v ON e.venue_id = v.id
                         LEFT JOIN event_performers ep ON e.id = ep.event_id
                         LEFT JOIN performers p ON ep.performer_id = p.id
                GROUP BY e.id, v.name
                ORDER BY e.date_start
                ''')
    events = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('shop_index.html', events=events)


@app.route('/shop/event/<int:event_id>')
def shop_event_details(event_id):
    cleanup_expired_reservations()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Pobieramy bilety i dane o miejscach
    cur.execute('''
                SELECT t.id as ticket_id, t.price, t.status, s.seat_row, s.seat_number, s.category
                FROM tickets t
                         JOIN seats s ON t.seat_id = s.id
                WHERE t.event_id = %s
                ORDER BY s.seat_row::int, s.seat_number
                ''', (event_id,))
    tickets = cur.fetchall()

    cur.execute('SELECT name FROM events WHERE id = %s', (event_id,))
    event_name = cur.fetchone()['name']

    cur.close()
    conn.close()
    return render_template('shop_event.html', tickets=tickets, event_name=event_name, event_id=event_id)


@app.route('/shop/reserve/<int:ticket_id>')
def reserve_ticket(ticket_id):
    conn = get_db_connection()
    cur = conn.cursor()
    # Rezerwujemy na 10 minut
    reserved_until = datetime.now() + timedelta(minutes=10)

    cur.execute('''
                UPDATE tickets
                SET status         = 'reserved',
                    reserved_until = %s
                WHERE id = %s
                  AND status = 'free' RETURNING event_id
                ''', (reserved_until, ticket_id))

    result = cur.fetchone()
    if result:
        conn.commit()
        # Dodajemy do koszyka w sesji
        if 'cart' not in session:
            session['cart'] = []
        session['cart'].append(ticket_id)
        session.modified = True

    cur.close()
    conn.close()
    return redirect(request.referrer)


@app.route('/shop/cart')
def view_cart():
    cleanup_expired_reservations()
    if 'cart' not in session or not session['cart']:
        return render_template('shop_cart.html', tickets=[])

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Pobieramy dane biletów z koszyka, które nadal są zarezerwowane
    cur.execute('''
                SELECT t.id, t.price, e.name as event_name, s.seat_row, s.seat_number, t.reserved_until
                FROM tickets t
                         JOIN events e ON t.event_id = e.id
                         JOIN seats s ON t.seat_id = s.id
                WHERE t.id = ANY (%s)
                  AND t.status = 'reserved'
                ''', (session['cart'],))
    tickets = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('shop_cart.html', tickets=tickets)


@app.route('/shop/buy', methods=['POST'])
def buy_tickets():
    if 'cart' not in session or not session['cart']:
        return redirect(url_for('shop_index'))

    conn = get_db_connection()
    cur = conn.cursor()
    # Finalizujemy: status 'sold' (lub inny z Twojej logiki, np. 'paid')
    cur.execute('''
                UPDATE tickets
                SET status         = 'sold',
                    reserved_until = NULL
                WHERE id = ANY (%s)
                  AND status = 'reserved'
                ''', (session['cart'],))

    conn.commit()
    session['cart'] = []  # Czyścimy koszyk
    cur.close()
    conn.close()
    return "<h3>Dziękujemy za zakup! Twoje bilety zostały wygenerowane.</h3><a href='/shop'>Powrót</a>"

# --- GŁÓWNY PANEL (DASHBOARD) ---
# 1. Strona Główna (Dashboard) - tylko podgląd
@app.route('/')
def index():
    cleanup_expired_reservations()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Pobieramy wydarzenia
    cur.execute('''
        SELECT 
            e.id, 
            e.name, 
            v.name as venue_name, 
            e.date_start, 
            e.date_end, 
            e.description,
            STRING_AGG(p.name, ', ') as performers,
            (SELECT count(*) FROM tickets t WHERE t.event_id = e.id AND t.status = 'free') as available
        FROM events e
        JOIN venues v ON e.venue_id = v.id
        LEFT JOIN event_performers ep ON e.id = ep.event_id
        LEFT JOIN performers p ON ep.performer_id = p.id
        GROUP BY e.id, v.name, e.name, e.date_start, e.date_end, e.description
        ORDER BY e.date_start;
                ''')
    wydarzenia = cur.fetchall()

    # 2. POBIERAMY LOKALIZACJE (potrzebne do listy rozwijanej w formularzu)
    cur.execute('SELECT id, name FROM venues ORDER BY name')
    venues = cur.fetchall()

    # 3. Pobranie listy wykonawców
    cur.execute('SELECT id, name FROM performers ORDER BY name')
    all_performers = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('index.html', wydarzenia=wydarzenia, venues=venues, all_performers=all_performers)

# 2. Nowa funkcja obsługująca podstronę events.html
@app.route('/events_management')
def events_management():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM events ORDER BY date_start DESC')
    wydarzenia = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('events.html', wydarzenia=wydarzenia)
# --- ZARZĄDZANIE WYDARZENIAMI ---
@app.route('/create_event', methods=['POST'])
def create_event():
    name = request.form['name']
    venue_id = request.form['venue_id']
    date_start = request.form['date_start']
    date_end = request.form.get('date_end') or None
    description = request.form.get('description') or ""

    performer_ids = request.form.getlist('performers')

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # 1. Tworzymy wydarzenie
        cur.execute('''
                    INSERT INTO events (name, venue_id, date_start, date_end, description)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                    ''', (name, venue_id, date_start, date_end, description))
        event_id = cur.fetchone()[0]

        # 2. Zapisujemy powiązania z wykonawcami (Tabela łącząca)
        for p_id in performer_ids:
            cur.execute('INSERT INTO event_performers (event_id, performer_id) VALUES (%s, %s)',
                        (event_id, p_id))

        # 2. Szukamy w danych z formularza wszystkich pól zaczynających się od 'price_'
        for key in request.form:
            if key.startswith('price_'):
                category_name = key.replace('price_', '')
                price = request.form[key]

                # 3. Generujemy bilety dla tej konkretnej kategorii
                cur.execute('''
                            INSERT INTO tickets (event_id, seat_id, price, status)
                            SELECT %s, id, %s, 'free'
                            FROM seats
                            WHERE venue_id = %s
                              AND category = %s
                            ''', (event_id, price, venue_id, category_name))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"BŁĄD: {e}")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('index'))
@app.route('/usun/<int:event_id>')
def delete_event(event_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Usunięcie biletów (dzieci) przed wydarzeniem (rodzicem) zapewnia integralność [cite: 58, 63]
        cur.execute('DELETE FROM tickets WHERE event_id = %s', (event_id,))
        cur.execute('DELETE FROM events WHERE id = %s', (event_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))

# --- ZARZĄDZANIE WYKONAWCAMI I LOKALIZACJAMI ---
@app.route('/performers', methods=['GET', 'POST'])
def manage_performers():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        name = request.form['name']
        cur.execute('INSERT INTO performers (name) VALUES (%s)', (name,))
        conn.commit()
        return redirect(url_for('manage_performers'))
    cur.execute('SELECT * FROM performers ORDER BY name')
    data = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('performers.html', performers=data)


@app.route('/venues', methods=['GET', 'POST'])
def manage_venues():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == 'POST':
        # 1. Pobieramy dane o sali
        name = request.form['name']
        address = request.form['address']
        rows = int(request.form['rows'])
        cols = int(request.form['cols'])

        try:
            # 2. Wstawiamy lokalizację i pobieramy jej ID
            cur.execute(
                'INSERT INTO venues (name, address) VALUES (%s, %s) RETURNING id',
                (name, address)
            )
            venue_id = cur.fetchone()['id']

            # 3. Automatycznie generujemy siatkę miejsc (domyślnie 'Standard')
            for r in range(1, rows + 1):
                for c in range(1, cols + 1):
                    cur.execute(
                        'INSERT INTO seats (venue_id, seat_row, seat_number, category) VALUES (%s, %s, %s, %s)',
                        (venue_id, str(r), c, '')
                    )

            conn.commit()
            return redirect(url_for('manage_venues'))
        except Exception as e:
            conn.rollback()
            print(f"Błąd tworzenia sali: {e}")

    # Pobieranie danych do wyświetlenia (bez zmian)
    cur.execute('SELECT * FROM venues ORDER BY id')
    venues = cur.fetchall()
    cur.execute('SELECT DISTINCT category FROM seats ORDER BY category')
    existing_categories = [row['category'] for row in cur.fetchall()]

    cur.close()
    conn.close()
    return render_template('venues.html', venues=venues, existing_categories=existing_categories)
@app.route('/add_seats', methods=['POST'])
def add_seats():
    venue_id = request.form['venue_id']
    rows = int(request.form['rows'])
    numbers = int(request.form['numbers'])
    category = request.form['category'] # Pobieramy kategorię z formularza

    conn = get_db_connection()
    cur = conn.cursor()
    for r in range(1, rows + 1):
        for n in range(1, numbers + 1):
            # Zapisujemy miejsce wraz z jego kategorią [cite: 36, 40]
            cur.execute('INSERT INTO seats (venue_id, seat_row, seat_number, category) VALUES (%s, %s, %s, %s)',
                        (venue_id, str(r), n, category))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('manage_venues'))


@app.route('/prepare_event', methods=['POST'])
def prepare_event():
    venue_id = request.form['venue_id']
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Pobieramy TYLKO te kategorie, które faktycznie są w tej sali
    cur.execute('SELECT DISTINCT category FROM seats WHERE venue_id = %s', (venue_id,))
    categories = cur.fetchall()

    cur.execute('SELECT name FROM venues WHERE id = %s', (venue_id,))
    venue_name = cur.fetchone()['name']

    cur.close()
    conn.close()
    return render_template('create_event_final.html',
                           categories=categories,
                           venue_id=venue_id,
                           venue_name=venue_name)


@app.route('/confirm_event', methods=['POST'])
def confirm_event():
    venue_id = request.form['venue_id']
    name = request.form['name']

    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Dodaj wydarzenie
    cur.execute('INSERT INTO events (name, venue_id, date_start) VALUES (%s, %s, NOW()) RETURNING id', (name, venue_id))
    event_id = cur.fetchone()[0]

    # 2. Przejdź przez wszystkie przesłane pola i wyciągnij ceny
    for key in request.form:
        if key.startswith('price_'):
            category_name = key.replace('price_', '')
            price = request.form[key]

            # Dodaj cenę do tabeli cennika
            cur.execute('INSERT INTO event_category_prices (event_id, category_name, price) VALUES (%s, %s, %s)',
                        (event_id, category_name, price))

            # Wygeneruj bilety dla tej kategorii w tym wydarzeniu
            cur.execute('''
                        INSERT INTO tickets (event_id, seat_id, price, status)
                        SELECT %s, id, %s, 'free'
                        FROM seats
                        WHERE venue_id = %s
                          AND category = %s
                        ''', (event_id, price, venue_id, category_name))

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/api/categories/<int:venue_id>')
def get_categories(venue_id):
    conn = get_db_connection()
    cur = conn.cursor()
    # Pobieramy unikalne kategorie dla danej sali
    cur.execute('SELECT DISTINCT category FROM seats WHERE venue_id = %s', (venue_id,))
    categories = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(categories)

# UPDATE: Edycja nazwy wykonawcy
@app.route('/edit_performer/<int:performer_id>', methods=['POST'])
def edit_performer(performer_id):
    new_name = request.form['name']
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE performers SET name = %s WHERE id = %s', (new_name, performer_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd edycji wykonawcy: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_performers'))

# DELETE: Usuwanie wykonawcy
@app.route('/delete_performer/<int:performer_id>')
def delete_performer(performer_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # UWAGA: Jeśli wykonawca jest przypisany do wydarzenia,
        # baza może zablokować usunięcie (Klucz Obcy).
        cur.execute('DELETE FROM performers WHERE id = %s', (performer_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        # Tu można by dodać informację dla użytkownika, że wykonawca ma przypisane koncerty
        print(f"Błąd usuwania wykonawcy: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_performers'))

# UPDATE: Edycja danych lokalizacji (Nazwa, Adres)
@app.route('/edit_venue/<int:venue_id>', methods=['POST'])
def edit_venue(venue_id):
    name = request.form['name']
    address = request.form['address']
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE venues SET name = %s, address = %s WHERE id = %s',
                    (name, address, venue_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd edycji lokalizacji: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_venues'))

# DELETE: Usuwanie lokalizacji
@app.route('/delete_venue/<int:venue_id>')
def delete_venue(venue_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # PAMIĘTAJ: To usunie też wszystkie miejsca (seats) przypisane do tej sali!
        cur.execute('DELETE FROM venues WHERE id = %s', (venue_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd usuwania lokalizacji: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_venues'))

# DELETE SEATS: Czyszczenie układu miejsc (aby stworzyć nowy)
@app.route('/clear_seats/<int:venue_id>')
def clear_seats(venue_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM seats WHERE venue_id = %s', (venue_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd czyszczenia miejsc: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_venues'))


# Widok szczegółowy układu sali
@app.route('/venue_layout/<int:venue_id>')
def venue_layout(venue_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Pobieramy dane o sali
    cur.execute('SELECT name FROM venues WHERE id = %s', (venue_id,))
    venue = cur.fetchone()

    # Pobieramy wszystkie miejsca, pogrupowane rzędami
    cur.execute('''
                SELECT seat_row, category, COUNT(*) as count, MIN(seat_number) as min_num, MAX(seat_number) as max_num
                FROM seats
                WHERE venue_id = %s
                GROUP BY seat_row, category
                ORDER BY seat_row:: integer
                ''', (venue_id,))
    layout = cur.fetchall()

    # Lista kategorii do selecta
    cur.execute('SELECT DISTINCT category FROM seats WHERE category IS NOT NULL ORDER BY category')
    categories = [row['category'] for row in cur.fetchall()]

    cur.close()
    conn.close()
    return render_template('venue_layout.html', venue=venue, venue_id=venue_id, layout=layout, categories=categories)


# Akcja: Masowa zmiana kategorii dla zakresu rzędów
@app.route('/update_seats_batch/<int:venue_id>', methods=['POST'])
def update_seats_batch(venue_id):
    row_start = request.form['row_start']
    row_end = request.form['row_end']
    # Tutaj pobierasz dane z formularza:
    new_category = request.form['new_category']

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # W zapytaniu SQL musisz użyć tej samej nazwy: new_category
        cur.execute('''
                    UPDATE seats
                    SET category = %s
                    WHERE venue_id = %s
                      AND seat_row::integer BETWEEN %s
                      AND %s
                    ''', (new_category, venue_id, row_start, row_end))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd aktualizacji: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('venue_layout', venue_id=venue_id))

if __name__ == '__main__':
    app.run(debug=True)