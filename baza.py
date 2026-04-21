import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="system_biletowy",
    user="postgres",
    password="admin"
)

cur = conn.cursor()

cur.execute("""
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
""")

tables = cur.fetchall()

dbml = ""

for (table,) in tables:
    dbml += f"Table {table} {{\n"

    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
    """, (table,))

    columns = cur.fetchall()

    for col, dtype in columns:
        dbml += f"  {col} {dtype}\n"

    dbml += "}\n\n"

print(dbml)