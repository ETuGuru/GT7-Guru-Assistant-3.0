import sqlite3
import threading
from datetime import datetime
from car_parameter_templates import DEFAULT_PARAMETERS

class CarSetupManager:
    def __init__(self, db_path='car_setups.db'):
        self.db_path = db_path
        self.conn = None
        self.lock = threading.Lock()
        self.initialize_database()
    
    def initialize_database(self):
        """Creates the database and tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            
            # Create cars table
            c.execute('''
                CREATE TABLE IF NOT EXISTS cars (
                    car_id INTEGER PRIMARY KEY,
                    manufacturer TEXT,
                    model TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create car parameters table with min/max values
            c.execute('''
                CREATE TABLE IF NOT EXISTS car_parameters (
                    parameter_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    car_id INTEGER,
                    parameter_name TEXT,
                    display_name TEXT,
                    current_value REAL,
                    min_value REAL,
                    max_value REAL,
                    unit TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (car_id) REFERENCES cars(car_id),
                    UNIQUE(car_id, parameter_name)
                )
            ''')
            
            # Create indices for better performance
            c.execute('CREATE INDEX IF NOT EXISTS idx_car_parameters_car_id ON car_parameters(car_id)')
            
            conn.commit()
    
    def initialize_car_parameters(self, car_id):
        """Initializes default parameters for a new car"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # Check if parameters already exist
                c.execute('SELECT COUNT(*) FROM car_parameters WHERE car_id = ?', (car_id,))
                if c.fetchone()[0] > 0:
                    return  # Parameters already exist
                
                # Initialize with defaults from template
                for param in DEFAULT_PARAMETERS:
                    c.execute('''
                        INSERT INTO car_parameters 
                        (car_id, parameter_name, display_name, current_value, min_value, max_value, unit)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        car_id,
                        param['name'],
                        param['display_name'],
                        param['current_value'],
                        param['min_value'],
                        param['max_value'],
                        param['unit']
                    ))
                
                conn.commit()
    
    def update_car(self, car_id, manufacturer=None, model=None):
        """Updates or inserts car information and initializes parameters if new"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # Check if car exists
                c.execute('SELECT car_id FROM cars WHERE car_id = ?', (car_id,))
                exists = c.fetchone() is not None
                
                # Update or insert car info
                c.execute('''
                    INSERT OR REPLACE INTO cars (car_id, manufacturer, model, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (car_id, manufacturer, model))
                
                conn.commit()
                
                # If new car, initialize parameters
                if not exists:
                    self.initialize_car_parameters(car_id)
    
    def update_parameter(self, car_id, parameter_name, current_value):
        """Updates a parameter value with validation"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # Get parameter constraints
                c.execute('''
                    SELECT min_value, max_value 
                    FROM car_parameters 
                    WHERE car_id = ? AND parameter_name = ?
                ''', (car_id, parameter_name))
                result = c.fetchone()
                
                if result is None:
                    raise ValueError(f"Parameter {parameter_name} not found for car {car_id}")
                
                min_value, max_value = result
                
                # Validate value if min/max are set
                if min_value is not None and current_value < min_value:
                    current_value = min_value
                if max_value is not None and current_value > max_value:
                    current_value = max_value
                
                # Update the parameter
                c.execute('''
                    UPDATE car_parameters 
                    SET current_value = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE car_id = ? AND parameter_name = ?
                ''', (current_value, car_id, parameter_name))
                
                conn.commit()
    
    def get_car_parameters(self, car_id):
        """Retrieves all parameters for a specific car"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''
                    SELECT parameter_name, display_name, current_value, min_value, max_value, unit 
                    FROM car_parameters 
                    WHERE car_id = ?
                    ORDER BY parameter_id
                ''', (car_id,))
                return c.fetchall()
    
    def get_car_info(self, car_id):
        """Retrieves car information"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('SELECT * FROM cars WHERE car_id = ?', (car_id,))
                return c.fetchone()
    
    def update_parameter_limits(self, car_id, parameter_name, min_value=None, max_value=None):
        """Updates the min/max limits for a parameter"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # Update limits
                c.execute('''
                    UPDATE car_parameters 
                    SET min_value = ?, max_value = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE car_id = ? AND parameter_name = ?
                ''', (min_value, max_value, car_id, parameter_name))
                
                # If current value is outside new limits, adjust it
                if min_value is not None or max_value is not None:
                    c.execute('''
                        SELECT current_value 
                        FROM car_parameters 
                        WHERE car_id = ? AND parameter_name = ?
                    ''', (car_id, parameter_name))
                    current_value = c.fetchone()[0]
                    
                    if min_value is not None and current_value < min_value:
                        current_value = min_value
                    if max_value is not None and current_value > max_value:
                        current_value = max_value
                    
                    c.execute('''
                        UPDATE car_parameters 
                        SET current_value = ?
                        WHERE car_id = ? AND parameter_name = ?
                    ''', (current_value, car_id, parameter_name))
                
                conn.commit()
