from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime, timedelta
from db import get_db
from cleanup import start_cleanup

app = Flask(__name__)
app.secret_key = 'pwr_projekt_secret'

# Cleanup odpala się raz przy starcie – nie przy każdym requeście
start_cleanup(interval_seconds=60)


# ---------------------------------------------------------------------------
# SHOP
# ---------------------------------------------------------------------------

@app.route('/shop')
def shop_index():
    with get_db() as (conn, cur):
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
    return render_template('shop_index.html', events=events)


@app.route('/shop/event/<int:event_id>')
def shop_event_details(event_id):
    with get_db() as (conn, cur):
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
        row = cur.fetchone()
        event_name = row['name'] if row else '—'

    return render_template('shop_event.html', tickets=tickets,
                           event_name=event_name, event_id=event_id)


@app.route('/shop/reserve/<int:ticket_id>')
def reserve_ticket(ticket_id):
    reserved_until = datetime.now() + timedelta(minutes=10)

    with get_db() as (conn, cur):
        cur.execute('''
            UPDATE tickets
            SET status = 'reserved', reserved_until = %s
            WHERE id = %s AND status = 'available'
            RETURNING event_id
        ''', (reserved_until, ticket_id))

        if cur.fetchone():
            conn.commit()
            session.setdefault('cart', [])
            session['cart'].append(ticket_id)
            session.modified = True

    return redirect(request.referrer or url_for('shop_index'))


@app.route('/shop/cart')
def view_cart():
    if not session.get('cart'):
        return render_template('shop_cart.html', tickets=[])

    with get_db() as (conn, cur):
        cur.execute('''
            SELECT t.id, t.price, e.name as event_name,
                   s.seat_row, s.seat_number, t.reserved_until
            FROM tickets t
                JOIN events e ON t.event_id = e.id
                JOIN seats s ON t.seat_id = s.id
            WHERE t.id = ANY(%s) AND t.status = 'reserved'
        ''', (session['cart'],))
        tickets = cur.fetchall()

    return render_template('shop_cart.html', tickets=tickets)


@app.route('/shop/buy', methods=['POST'])
def buy_tickets():
    if not session.get('cart'):
        return redirect(url_for('shop_index'))

    with get_db() as (conn, cur):
        cur.execute('''
            UPDATE tickets
            SET status = 'sold', reserved_until = NULL
            WHERE id = ANY(%s) AND status = 'reserved'
        ''', (session['cart'],))
        conn.commit()

    session['cart'] = []
    return "<h3>Dziękujemy za zakup! Twoje bilety zostały wygenerowane.</h3><a href='/shop'>Powrót</a>"


# ---------------------------------------------------------------------------
# GŁÓWNY PANEL
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    with get_db() as (conn, cur):
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
            ORDER BY e.date_start
        ''')
        wydarzenia = cur.fetchall()

        cur.execute('SELECT id, name FROM venues ORDER BY name')
        venues = cur.fetchall()

        cur.execute('SELECT id, name FROM performers ORDER BY name')
        all_performers = cur.fetchall()

    return render_template('index.html', wydarzenia=wydarzenia,
                           venues=venues, all_performers=all_performers)


@app.route('/events_management')
def events_management():
    with get_db() as (conn, cur):
        cur.execute('SELECT * FROM events ORDER BY date_start DESC')
        wydarzenia = cur.fetchall()
    return render_template('events.html', wydarzenia=wydarzenia)


@app.route('/create_event', methods=['POST'])
def create_event():
    name          = request.form['name']
    venue_id      = request.form['venue_id']
    date_start    = request.form['date_start']
    date_end      = request.form.get('date_end') or None
    description   = request.form.get('description') or ''
    performer_ids = request.form.getlist('performers')

    with get_db() as (conn, cur):
        try:
            cur.execute('''
                INSERT INTO events (name, venue_id, date_start, date_end, description)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            ''', (name, venue_id, date_start, date_end, description))
            event_id = cur.fetchone()['id']

            for p_id in performer_ids:
                cur.execute(
                    'INSERT INTO event_performers (event_id, performer_id) VALUES (%s, %s)',
                    (event_id, p_id)
                )

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
            print(f"BŁĄD create_event: {e}")
            raise

    return redirect(url_for('index'))


@app.route('/usun/<int:event_id>')
def delete_event(event_id):
    with get_db() as (conn, cur):
        cur.execute('DELETE FROM tickets WHERE event_id = %s', (event_id,))
        cur.execute('DELETE FROM events WHERE id = %s', (event_id,))
        conn.commit()
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# WYKONAWCY I LOKALIZACJE
# ---------------------------------------------------------------------------

@app.route('/performers', methods=['GET', 'POST'])
def manage_performers():
    with get_db() as (conn, cur):
        if request.method == 'POST':
            cur.execute('INSERT INTO performers (name) VALUES (%s)', (request.form['name'],))
            conn.commit()
            return redirect(url_for('manage_performers'))

        cur.execute('SELECT * FROM performers ORDER BY name')
        data = cur.fetchall()
    return render_template('performers.html', performers=data)


@app.route('/venues', methods=['GET', 'POST'])
def manage_venues():
    with get_db() as (conn, cur):
        if request.method == 'POST':
            name             = request.form['name']
            address          = request.form['address']
            rows             = int(request.form['rows'])
            cols             = int(request.form['cols'])
            default_category = request.form.get('default_category', 'Standard')

            try:
                cur.execute(
                    'INSERT INTO venues (name, address) VALUES (%s, %s) RETURNING id',
                    (name, address)
                )
                venue_id = cur.fetchone()['id']

                cur.execute(
                    'INSERT INTO seat_categories (venue_id, name) VALUES (%s, %s) RETURNING id',
                    (venue_id, default_category)
                )
                category_id = cur.fetchone()['id']

                for r in range(1, rows + 1):
                    for c in range(1, cols + 1):
                        cur.execute(
                            'INSERT INTO seats (venue_id, seat_row, seat_number, category_id) VALUES (%s, %s, %s, %s)',
                            (venue_id, str(r), c, category_id)
                        )

                conn.commit()
                return redirect(url_for('manage_venues'))
            except Exception as e:
                print(f"Błąd tworzenia sali: {e}")
                raise

        cur.execute('SELECT * FROM venues ORDER BY id')
        venues = cur.fetchall()

        cur.execute('SELECT id, name, venue_id FROM seat_categories ORDER BY name')
        existing_categories = cur.fetchall()

    return render_template('venues.html', venues=venues,
                           existing_categories=existing_categories)


@app.route('/add_seats', methods=['POST'])
def add_seats():
    venue_id    = request.form['venue_id']
    rows        = int(request.form['rows'])
    numbers     = int(request.form['numbers'])
    category_id = int(request.form['category_id'])

    with get_db() as (conn, cur):
        for r in range(1, rows + 1):
            for n in range(1, numbers + 1):
                cur.execute(
                    'INSERT INTO seats (venue_id, seat_row, seat_number, category_id) VALUES (%s, %s, %s, %s)',
                    (venue_id, str(r), n, category_id)
                )
        conn.commit()
    return redirect(url_for('manage_venues'))


@app.route('/prepare_event', methods=['POST'])
def prepare_event():
    venue_id = request.form['venue_id']
    with get_db() as (conn, cur):
        cur.execute(
            'SELECT id, name FROM seat_categories WHERE venue_id = %s ORDER BY name',
            (venue_id,)
        )
        categories = cur.fetchall()

        cur.execute('SELECT name FROM venues WHERE id = %s', (venue_id,))
        venue_name = cur.fetchone()['name']

    return render_template('create_event_final.html', categories=categories,
                           venue_id=venue_id, venue_name=venue_name)


@app.route('/confirm_event', methods=['POST'])
def confirm_event():
    venue_id = request.form['venue_id']
    name     = request.form['name']

    with get_db() as (conn, cur):
        cur.execute(
            'INSERT INTO events (name, venue_id, date_start) VALUES (%s, %s, NOW()) RETURNING id',
            (name, venue_id)
        )
        event_id = cur.fetchone()[0]

        for key in request.form:
            if key.startswith('price_'):
                category_id = int(key.replace('price_', ''))
                price = request.form[key]
                cur.execute(
                    'INSERT INTO event_category_prices (event_id, category_id, price) VALUES (%s, %s, %s)',
                    (event_id, category_id, price)
                )
                cur.execute('''
                    INSERT INTO tickets (event_id, seat_id, price, status)
                    SELECT %s, s.id, 0, 'available'
                    FROM seats s
                    WHERE s.venue_id = %s AND s.category_id = %s
                ''', (event_id, venue_id, category_id))

        conn.commit()
    return redirect(url_for('index'))


@app.route('/api/categories/<int:venue_id>')
def get_categories(venue_id):
    with get_db() as (conn, cur):
        cur.execute(
            'SELECT id, name FROM seat_categories WHERE venue_id = %s ORDER BY name',
            (venue_id,)
        )
        categories = cur.fetchall()
    return jsonify(categories)


@app.route('/edit_performer/<int:performer_id>', methods=['POST'])
def edit_performer(performer_id):
    with get_db() as (conn, cur):
        cur.execute('UPDATE performers SET name = %s WHERE id = %s',
                    (request.form['name'], performer_id))
        conn.commit()
    return redirect(url_for('manage_performers'))


@app.route('/delete_performer/<int:performer_id>')
def delete_performer(performer_id):
    with get_db() as (conn, cur):
        cur.execute('DELETE FROM performers WHERE id = %s', (performer_id,))
        conn.commit()
    return redirect(url_for('manage_performers'))


@app.route('/edit_venue/<int:venue_id>', methods=['POST'])
def edit_venue(venue_id):
    with get_db() as (conn, cur):
        cur.execute('UPDATE venues SET name = %s, address = %s WHERE id = %s',
                    (request.form['name'], request.form['address'], venue_id))
        conn.commit()
    return redirect(url_for('manage_venues'))


@app.route('/delete_venue/<int:venue_id>')
def delete_venue(venue_id):
    with get_db() as (conn, cur):
        cur.execute('DELETE FROM venues WHERE id = %s', (venue_id,))
        conn.commit()
    return redirect(url_for('manage_venues'))


@app.route('/clear_seats/<int:venue_id>')
def clear_seats(venue_id):
    with get_db() as (conn, cur):
        cur.execute('DELETE FROM seats WHERE venue_id = %s', (venue_id,))
        conn.commit()
    return redirect(url_for('manage_venues'))


@app.route('/venue_layout/<int:venue_id>')
def venue_layout(venue_id):
    with get_db() as (conn, cur):
        cur.execute('SELECT name FROM venues WHERE id = %s', (venue_id,))
        venue = cur.fetchone()

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

        cur.execute(
            'SELECT id, name FROM seat_categories WHERE venue_id = %s ORDER BY name',
            (venue_id,)
        )
        categories = cur.fetchall()

    return render_template('venue_layout.html', venue=venue, venue_id=venue_id,
                           layout=layout, categories=categories)


@app.route('/update_seats_batch/<int:venue_id>', methods=['POST'])
def update_seats_batch(venue_id):
    row_start       = request.form['row_start']
    row_end         = request.form['row_end']
    new_category_id = int(request.form['new_category_id'])

    with get_db() as (conn, cur):
        cur.execute('''
            UPDATE seats
            SET category_id = %s
            WHERE venue_id = %s
              AND SUBSTRING(seat_row FROM 2)::integer BETWEEN %s AND %s
        ''', (new_category_id, venue_id, row_start, row_end))
        conn.commit()
    return redirect(url_for('venue_layout', venue_id=venue_id))


if __name__ == '__main__':
    app.run(debug=True)