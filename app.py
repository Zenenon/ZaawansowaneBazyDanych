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
    """Wygasanie rezerwacji – status 'available' zamiast 'free'."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE tickets
            SET status = 'available', reserved_until = NULL, booking_id = NULL
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

    # ZMIANA: s.category → sc.name (join przez seat_categories)
    # ZMIANA: seat_row::int → seat_row (teraz VARCHAR typu 'R1', 'R2'...)
    cur.execute('''
        SELECT t.id as ticket_id, t.price, t.status,
               s.seat_row, s.seat_number, sc.name as category
        FROM tickets t
            JOIN seats s ON t.seat_id = s.id
            JOIN seat_categories sc ON s.category_id = sc.id
        WHERE t.event_id = %s
        ORDER BY s.seat_row, s.seat_number
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
    reserved_until = datetime.now() + timedelta(minutes=10)

    # ZMIANA: status 'free' → 'available'
    cur.execute('''
        UPDATE tickets
        SET status = 'reserved', reserved_until = %s
        WHERE id = %s AND status = 'available'
        RETURNING event_id
    ''', (reserved_until, ticket_id))

    result = cur.fetchone()
    if result:
        conn.commit()
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
    cur.execute('''
        SELECT t.id, t.price, e.name as event_name,
               s.seat_row, s.seat_number, t.reserved_until
        FROM tickets t
            JOIN events e ON t.event_id = e.id
            JOIN seats s ON t.seat_id = s.id
        WHERE t.id = ANY(%s) AND t.status = 'reserved'
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
    cur.execute('''
        UPDATE tickets
        SET status = 'sold', reserved_until = NULL
        WHERE id = ANY(%s) AND status = 'reserved'
    ''', (session['cart'],))

    conn.commit()
    session['cart'] = []
    cur.close()
    conn.close()
    return "<h3>Dziękujemy za zakup! Twoje bilety zostały wygenerowane.</h3><a href='/shop'>Powrót</a>"


# --- GŁÓWNY PANEL ---

@app.route('/')
def index():
    cleanup_expired_reservations()
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('''
        SELECT
            e.id, e.name, v.name as venue_name,
            e.date_start, e.date_end, e.description,
            STRING_AGG(p.name, ', ') as performers,
            (SELECT COUNT(*) FROM tickets t
             WHERE t.event_id = e.id AND t.status = 'available') as available
        FROM events e
            JOIN venues v ON e.venue_id = v.id
            LEFT JOIN event_performers ep ON e.id = ep.event_id
            LEFT JOIN performers p ON ep.performer_id = p.id
        GROUP BY e.id, v.name, e.name, e.date_start, e.date_end, e.description
        ORDER BY e.date_start;
    ''')
    wydarzenia = cur.fetchall()

    cur.execute('SELECT id, name FROM venues ORDER BY name')
    venues = cur.fetchall()

    cur.execute('SELECT id, name FROM performers ORDER BY name')
    all_performers = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('index.html', wydarzenia=wydarzenia, venues=venues, all_performers=all_performers)


@app.route('/events_management')
def events_management():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM events ORDER BY date_start DESC')
    wydarzenia = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('events.html', wydarzenia=wydarzenia)


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
        cur.execute('''
            INSERT INTO events (name, venue_id, date_start, date_end, description)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        ''', (name, venue_id, date_start, date_end, description))
        event_id = cur.fetchone()[0]

        for p_id in performer_ids:
            cur.execute(
                'INSERT INTO event_performers (event_id, performer_id) VALUES (%s, %s)',
                (event_id, p_id)
            )

        # ZMIANA: key to 'price_{category_id}' (id zamiast nazwy)
        # ZMIANA: INSERT do event_category_prices używa category_id (int)
        # ZMIANA: bilety generowane przez JOIN z seat_categories po id
        # ZMIANA: trigger trg_fill_ticket_price uzupełni cenę automatycznie,
        #         ale wstawiamy price=0 jako placeholder (trigger to nadpisze)
        for key in request.form:
            if key.startswith('price_'):
                category_id = int(key.replace('price_', ''))
                price = request.form[key]

                cur.execute('''
                    INSERT INTO event_category_prices (event_id, category_id, price)
                    VALUES (%s, %s, %s)
                ''', (event_id, category_id, price))

                cur.execute('''
                    INSERT INTO tickets (event_id, seat_id, price, status)
                    SELECT %s, s.id, 0, 'available'
                    FROM seats s
                    WHERE s.venue_id = %s AND s.category_id = %s
                ''', (event_id, venue_id, category_id))

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


# --- WYKONAWCY I LOKALIZACJE ---

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
        name = request.form['name']
        address = request.form['address']
        rows = int(request.form['rows'])
        cols = int(request.form['cols'])
        # ZMIANA: formularz powinien też przekazywać nazwę domyślnej kategorii
        default_category = request.form.get('default_category', 'Standard')

        try:
            cur.execute(
                'INSERT INTO venues (name, address) VALUES (%s, %s) RETURNING id',
                (name, address)
            )
            venue_id = cur.fetchone()['id']

            # ZMIANA: tworzymy domyślną kategorię dla nowego venue
            cur.execute(
                'INSERT INTO seat_categories (venue_id, name) VALUES (%s, %s) RETURNING id',
                (venue_id, default_category)
            )
            category_id = cur.fetchone()['id']

            # ZMIANA: seats używają category_id zamiast category (varchar)
            for r in range(1, rows + 1):
                for c in range(1, cols + 1):
                    cur.execute(
                        'INSERT INTO seats (venue_id, seat_row, seat_number, category_id) VALUES (%s, %s, %s, %s)',
                        (venue_id, str(r), c, category_id)
                    )

            conn.commit()
            return redirect(url_for('manage_venues'))
        except Exception as e:
            conn.rollback()
            print(f"Błąd tworzenia sali: {e}")

    cur.execute('SELECT * FROM venues ORDER BY id')
    venues = cur.fetchall()

    # ZMIANA: kategorie pobieramy z seat_categories, nie z seats.category
    cur.execute('SELECT id, name, venue_id FROM seat_categories ORDER BY name')
    existing_categories = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('venues.html', venues=venues, existing_categories=existing_categories)


@app.route('/add_seats', methods=['POST'])
def add_seats():
    venue_id = request.form['venue_id']
    rows = int(request.form['rows'])
    numbers = int(request.form['numbers'])
    # ZMIANA: przyjmujemy category_id (int) zamiast nazwy kategorii
    category_id = int(request.form['category_id'])

    conn = get_db_connection()
    cur = conn.cursor()
    for r in range(1, rows + 1):
        for n in range(1, numbers + 1):
            cur.execute(
                'INSERT INTO seats (venue_id, seat_row, seat_number, category_id) VALUES (%s, %s, %s, %s)',
                (venue_id, str(r), n, category_id)
            )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('manage_venues'))


@app.route('/prepare_event', methods=['POST'])
def prepare_event():
    venue_id = request.form['venue_id']
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ZMIANA: pobieramy kategorie z seat_categories (id + name) zamiast DISTINCT category z seats
    cur.execute(
        'SELECT id, name FROM seat_categories WHERE venue_id = %s ORDER BY name',
        (venue_id,)
    )
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

    cur.execute(
        'INSERT INTO events (name, venue_id, date_start) VALUES (%s, %s, NOW()) RETURNING id',
        (name, venue_id)
    )
    event_id = cur.fetchone()[0]

    # ZMIANA: key to 'price_{category_id}', INSERT używa category_id
    for key in request.form:
        if key.startswith('price_'):
            category_id = int(key.replace('price_', ''))
            price = request.form[key]

            cur.execute(
                'INSERT INTO event_category_prices (event_id, category_id, price) VALUES (%s, %s, %s)',
                (event_id, category_id, price)
            )

            # trigger trg_fill_ticket_price nadpisze price=0 właściwą wartością
            cur.execute('''
                INSERT INTO tickets (event_id, seat_id, price, status)
                SELECT %s, s.id, 0, 'available'
                FROM seats s
                WHERE s.venue_id = %s AND s.category_id = %s
            ''', (event_id, venue_id, category_id))

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))


# ZMIANA: zwracamy {id, name} zamiast samej nazwy
@app.route('/api/categories/<int:venue_id>')
def get_categories(venue_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        'SELECT id, name FROM seat_categories WHERE venue_id = %s ORDER BY name',
        (venue_id,)
    )
    categories = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(categories)


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


@app.route('/delete_performer/<int:performer_id>')
def delete_performer(performer_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM performers WHERE id = %s', (performer_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd usuwania wykonawcy: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_performers'))


@app.route('/edit_venue/<int:venue_id>', methods=['POST'])
def edit_venue(venue_id):
    name = request.form['name']
    address = request.form['address']
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            'UPDATE venues SET name = %s, address = %s WHERE id = %s',
            (name, address, venue_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd edycji lokalizacji: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_venues'))


@app.route('/delete_venue/<int:venue_id>')
def delete_venue(venue_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM venues WHERE id = %s', (venue_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd usuwania lokalizacji: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('manage_venues'))


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


@app.route('/venue_layout/<int:venue_id>')
def venue_layout(venue_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute('SELECT name FROM venues WHERE id = %s', (venue_id,))
    venue = cur.fetchone()

    # ZMIANA: JOIN z seat_categories zamiast s.category
    # ZMIANA: seat_row to VARCHAR (R1, R2...) – usunięto ::integer cast
    cur.execute('''
        SELECT s.seat_row, sc.name as category, sc.id as category_id,
               COUNT(*) as count,
               MIN(s.seat_number) as min_num,
               MAX(s.seat_number) as max_num
        FROM seats s
            JOIN seat_categories sc ON s.category_id = sc.id
        WHERE s.venue_id = %s
        GROUP BY s.seat_row, sc.name, sc.id
        ORDER BY s.seat_row
    ''', (venue_id,))
    layout = cur.fetchall()

    # ZMIANA: kategorie z seat_categories (id + name)
    cur.execute(
        'SELECT id, name FROM seat_categories WHERE venue_id = %s ORDER BY name',
        (venue_id,)
    )
    categories = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('venue_layout.html', venue=venue, venue_id=venue_id,
                           layout=layout, categories=categories)


@app.route('/update_seats_batch/<int:venue_id>', methods=['POST'])
def update_seats_batch(venue_id):
    row_start = request.form['row_start']
    row_end = request.form['row_end']
    # ZMIANA: przyjmujemy category_id (int) zamiast nazwy
    new_category_id = int(request.form['new_category_id'])

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # ZMIANA: SET category_id zamiast SET category
        # ZMIANA: seat_row to tekst 'R1','R2'... – porównujemy po SUBSTRING numerycznym
        cur.execute('''
            UPDATE seats
            SET category_id = %s
            WHERE venue_id = %s
              AND SUBSTRING(seat_row FROM 2)::integer BETWEEN %s AND %s
        ''', (new_category_id, venue_id, row_start, row_end))
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