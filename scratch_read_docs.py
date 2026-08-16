import sys
import os

# Add core to sys.path
sys.path.append("/Users/carlosrivas/Dev/Kenbun/core")

from tools.memory.postgres_client import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        # Check current database and user
        cur.execute("SELECT current_database(), current_user")
        db, user = cur.fetchone()
        print(f"Connected to DB: {db} as User: {user}")
        
        # List all tables in the public schema
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [r['table_name'] for r in cur.fetchall()]
        print(f"Tables in public schema: {tables}")
