from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)


# Funkcja tworząca połączenie z bazą
def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="system_biletowy",
        user="postgres",
        password="admin"  # WPISZ SWOJE HASŁO TUTAJ
    )
    return conn


# 1. Test połączenia - prosta informacja czy baza "odpowiada"
@app.route('/test')
def test_db():
    try:
        conn = get_db_connection()
        conn.close()
        return "Połączenie z bazą PostgreSQL udane!"
    except Exception as e:
        return f"Błąd połączenia: {str(e)}"


# 2. Wykonywanie zapytania i zwracanie wyników (Lista koncertów)
@app.route('/wydarzenia')
def get_events():
    conn = get_db_connection()
    cur = conn.cursor()

    # Zapytanie SQL (Query) - pobieramy nazwę koncertu i adres miejsca
    cur.execute('''
                SELECT e.name, v.name, v.address
                FROM events e
                         JOIN venues v ON e.venue_id = v.id;
                ''')

    # Pobieranie wyników
    rows = cur.fetchall()

    cur.close()
    conn.close()

    # Przetworzenie wyników na czytelną listę
    wyniki = []
    for r in rows:
        wyniki.append({
            "koncert": r[0],
            "miejsce": r[1],
            "adres": r[2]
        })

    return jsonify(wyniki)


if __name__ == '__main__':
    app.run(debug=True)