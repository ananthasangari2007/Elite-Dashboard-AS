import os
import psycopg2

def main():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL not set in environment")
        return
    print("Using DSN (masked):", dsn[:60] + "...")
    try:
        conn = psycopg2.connect(dsn, connect_timeout=5)
        print("psycopg2: connected")
        conn.close()
    except Exception as e:
        print("psycopg2 error:", repr(e))

if __name__ == '__main__':
    main()
