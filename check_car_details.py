import sqlite3

def check_car_details(car_id):
    conn = sqlite3.connect('car_setup.db')
    cursor = conn.cursor()
    
    # Recupera il nome dell'auto
    cursor.execute("SELECT car_name FROM cars WHERE car_id = ?", (car_id,))
    car_name = cursor.fetchone()
    
    # Recupera i parametri specifici
    cursor.execute("""
        SELECT param_name, param_value 
        FROM car_parameters 
        WHERE car_id = ? 
        AND param_name IN ('tipo_gomme', 'circuito')
    """, (car_id,))
    params = cursor.fetchall()
    
    print(f"\nDettagli per auto ID {car_id}:")
    print(f"Nome: {car_name[0] if car_name else 'Non trovato'}")
    print("\nParametri:")
    for param_name, value in params:
        print(f"{param_name}: {value}")
        
    conn.close()

def check_db_structure():
    conn = sqlite3.connect('car_setup.db')
    cursor = conn.cursor()
    
    print("\nVerifica struttura database:")
    
    # Verifica esistenza tabella
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='car_parameters'
    """)
    if cursor.fetchone():
        print("Tabella car_parameters presente")
        
        # Mostra struttura tabella
        cursor.execute("PRAGMA table_info(car_parameters)")
        columns = cursor.fetchall()
        print("\nStruttura tabella car_parameters:")
        for col in columns:
            print(f"Colonna: {col[1]}, Tipo: {col[2]}")
    else:
        print("Tabella car_parameters non trovata!")
        
    # Verifica i valori distinti di param_name
    cursor.execute("""
        SELECT DISTINCT param_name 
        FROM car_parameters 
        ORDER BY param_name
    """)
    param_names = cursor.fetchall()
    print("\nParametri presenti nel database:")
    for param in param_names:
        print(f"- {param[0]}")
        
    conn.close()

if __name__ == "__main__":
    check_db_structure()
    check_car_details("334")  # Renault Clio V6
    check_car_details("3562") # F3500-A
