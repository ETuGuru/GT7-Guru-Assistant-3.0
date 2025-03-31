import sqlite3
import json

def check_database():
    conn = sqlite3.connect('cars_database.db')
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables in database:", tables)
    
    for table in tables:
        print(f"\nTable: {table[0]}")
        cursor.execute(f"PRAGMA table_info({table[0]});")
        columns = cursor.fetchall()
        print("Columns:", columns)
        
        cursor.execute(f"SELECT * FROM {table[0]} LIMIT 1;")
        sample = cursor.fetchone()
        print("Sample row:", sample)
    
    conn.close()

if __name__ == "__main__":
    check_database()

