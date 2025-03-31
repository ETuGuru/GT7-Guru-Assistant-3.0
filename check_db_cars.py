import sqlite3

def check_cars():
    conn = sqlite3.connect('car_setup.db')
    cursor = conn.cursor()
    cursor.execute("SELECT car_id, car_name FROM cars")
    cars = cursor.fetchall()
    print("\nAuto disponibili nel database:")
    for car_id, car_name in cars:
        print(f"Car ID: {car_id}, Nome: {car_name}")
    conn.close()

if __name__ == "__main__":
    check_cars()

