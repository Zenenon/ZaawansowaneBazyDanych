from flask import Flask, render_template, request, redirect, url_for
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)


def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="system_biletowy",
        user="postgres",
        password="admin"
    )


#Wyświetlanie wszystkich wydarzeń
@app.route('/')
def index():
    cleanup_expired_reservations()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
                SELECT e.id, e.name, v.name as venue_name, e.date_start, e.date_end, e.description
                FROM events e
                         JOIN venues v ON e.venue_id = v.id
                ORDER BY e.date_start;
                ''')
    wydarzenia = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', wydarzenia=wydarzenia)
#Dodawanie nowego wydarzenia
@app.route('/dodaj', methods=['POST'])
def add_event():
    name = request.form['name']
    venue_id = request.form['venue_id']
    date_start = request.form['date_start']
    date_end = request.form['date_end']
    description = request.form['description']

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO events (name, venue_id, date_start, date_end, description) VALUES (%s, %s, %s, %s, %s)',
        (name, venue_id, date_start, date_end, description)
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))


#Usuwanie wydarzenia
@app.route('/usun/<int:event_id>')
def delete_event(event_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        #usuwamy bilety powiązane z tym koncertem
        cur.execute('DELETE FROM tickets WHERE event_id = %s', (event_id,))

        #teraz możemy bezpiecznie usunąć koncert
        cur.execute('DELETE FROM events WHERE id = %s', (event_id,))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))

def cleanup_expired_reservations():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Aplikacja wymusza aktualizację stanów w bazie
        # To jest proste i szybkie zapytanie dla bazy
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


if __name__ == '__main__':
    app.run(debug=True)
