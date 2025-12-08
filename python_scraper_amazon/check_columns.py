import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='n8n',
    user='n8n_user',
    password='B3rn4rd0'
)
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'amazon_offers'
    ORDER BY ordinal_position
""")
print("COLUNAS EXISTENTES NA TABELA amazon_offers:")
print("-" * 70)
for r in cur.fetchall():
    print(f'{r[0]:30} | {r[1]:20} | {r[2]}')
conn.close()
