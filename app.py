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


# READ: Wyświetlanie wszystkich wydarzeń
@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Łączymy wydarzenia z miejscami, by pokazać nazwę hali [cite: 72, 79, 80]
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
# CREATE: Dodawanie nowego wydarzenia [cite: 72, 77, 80, 84]
@app.route('/dodaj', methods=['POST'])
def add_event():
    name = request.form['name']
    venue_id = request.form['venue_id']
    date_start = request.form['date_start']
    date_end = request.form['date_end']  # Nowe pole [cite: 88]
    description = request.form['description']  # Nowe pole [cite: 92]

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

# UPDATE: Zmiana nazwy wydarzenia
@app.route('/edytuj/<int:event_id>', methods=['POST'])
def update_event(event_id):
    # Pobieramy komplet danych z formularza
    name = request.form['name']
    date_start = request.form['date_start']
    date_end = request.form['date_end']
    description = request.form['description']

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Aktualizujemy wszystkie kolumny dla danego ID [cite: 75]
        cur.execute('''
            UPDATE events 
            SET name = %s, date_start = %s, date_end = %s, description = %s 
            WHERE id = %s
        ''', (name, date_start, date_end, description, event_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Błąd edycji: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))


# DELETE: Usuwanie wydarzenia [cite: 72, 75]
@app.route('/usun/<int:event_id>')
def delete_event(event_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # KROK 1: Najpierw usuwamy bilety powiązane z tym koncertem
        cur.execute('DELETE FROM tickets WHERE event_id = %s', (event_id,))

        # KROK 2: Dopiero teraz możemy bezpiecznie usunąć koncert
        cur.execute('DELETE FROM events WHERE id = %s', (event_id,))

        conn.commit()  # Zatwierdzamy obie zmiany naraz (Model ACID) [cite: 55]
    except Exception as e:
        conn.rollback()
        print(f"Błąd: {e}")
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
