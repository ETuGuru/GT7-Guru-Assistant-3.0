# gtdata.py
# Implementazione della classe GTData per la gestione della telemetria di Gran Turismo 7
# Offset corretti basati sul repository di snipem/gt7dashboard

import struct
from datetime import datetime
import logging

class GTData:
    """
    Classe per gestire i dati di telemetria di Gran Turismo 7.
    Decodifica un pacchetto di 296 byte (0x128) e ne estrae tutte le informazioni.
    """
    
    # Definizione delle costanti per gli offset
    OFFSET_POSITION_X = 0x04
    OFFSET_POSITION_Y = 0x08
    OFFSET_POSITION_Z = 0x0C
    OFFSET_VELOCITY_X = 0x10
    OFFSET_VELOCITY_Y = 0x14
    OFFSET_VELOCITY_Z = 0x18
    OFFSET_ROTATION_PITCH = 0x1C
    OFFSET_ROTATION_YAW = 0x20
    OFFSET_ROTATION_ROLL = 0x24
    OFFSET_ANGULAR_VELOCITY_X = 0x2C
    OFFSET_ANGULAR_VELOCITY_Y = 0x30
    OFFSET_ANGULAR_VELOCITY_Z = 0x34
    OFFSET_RIDE_HEIGHT = 0x38
    OFFSET_RPM = 0x3C
    OFFSET_CURRENT_FUEL = 0x44
    OFFSET_FUEL_CAPACITY = 0x48
    OFFSET_SPEED = 0x4C
    OFFSET_BOOST = 0x50
    OFFSET_OIL_PRESSURE = 0x54
    OFFSET_WATER_TEMP = 0x58
    OFFSET_OIL_TEMP = 0x5C
    OFFSET_TYRE_TEMP_FL = 0x60
    OFFSET_TYRE_TEMP_FR = 0x64
    OFFSET_TYRE_TEMP_RL = 0x68
    OFFSET_TYRE_TEMP_RR = 0x6C
    OFFSET_PACKAGE_ID = 0x70
    OFFSET_CURRENT_LAP = 0x74
    OFFSET_TOTAL_LAPS = 0x76
    OFFSET_BEST_LAP = 0x78
    OFFSET_LAST_LAP = 0x7C
    OFFSET_TIME_ON_TRACK = 0x80
    OFFSET_CURRENT_POSITION = 0x84
    OFFSET_TOTAL_POSITIONS = 0x86
    OFFSET_RPM_REV_WARNING = 0x88
    OFFSET_RPM_REV_LIMITER = 0x8A
    OFFSET_ESTIMATED_TOP_SPEED = 0x8C
    OFFSET_FLAGS = 0x8E
    OFFSET_GEAR = 0x90
    OFFSET_THROTTLE = 0x91
    OFFSET_BRAKE = 0x92
    OFFSET_TYRE_SPEED_FL = 0xA4
    OFFSET_TYRE_SPEED_FR = 0xA8
    OFFSET_TYRE_SPEED_RL = 0xAC
    OFFSET_TYRE_SPEED_RR = 0xB0
    OFFSET_TYRE_DIAMETER_FL = 0xB4
    OFFSET_TYRE_DIAMETER_FR = 0xB8
    OFFSET_TYRE_DIAMETER_RL = 0xBC
    OFFSET_TYRE_DIAMETER_RR = 0xC0
    OFFSET_SUSPENSION_FL = 0xC4
    OFFSET_SUSPENSION_FR = 0xC8
    OFFSET_SUSPENSION_RL = 0xCC
    OFFSET_SUSPENSION_RR = 0xD0
    OFFSET_CLUTCH = 0xF4
    OFFSET_CLUTCH_ENGAGED = 0xF8
    OFFSET_RPM_AFTER_CLUTCH = 0xFC
    OFFSET_GEAR_1 = 0x104
    OFFSET_GEAR_2 = 0x108
    OFFSET_GEAR_3 = 0x10C
    OFFSET_GEAR_4 = 0x110
    OFFSET_GEAR_5 = 0x114
    OFFSET_GEAR_6 = 0x118
    OFFSET_GEAR_7 = 0x11C
    OFFSET_GEAR_8 = 0x120
    OFFSET_CAR_ID = 0x124
    
    def __init__(self, ddata):
        """
        Inizializza un nuovo oggetto GTData e decodifica i dati telemetrici dal pacchetto.
        
        Args:
            ddata (bytes): Pacchetto di dati telemetrici di 296 byte
        """
        # Timestamp per la telemetria
        self.timestamp = datetime.now().isoformat()
        
        # Initialize previous velocity values for G-force calculations
        self.prev_velocity_x = 0.0
        self.prev_velocity_y = 0.0
        self.prev_velocity_z = 0.0
        
        # Se non ci sono dati, restituisce un oggetto vuoto
        if not ddata or len(ddata) < 296:
            logging.warning(f"Pacchetto dati non valido: lunghezza {len(ddata) if ddata else 0} byte (attesi 296)")
            return
            
        try:
            # === POSIZIONE E MOVIMENTO ===
            
            # Posizione 3D (metri)
            self.position_x = self._unpack_float(ddata, self.OFFSET_POSITION_X)
            self.position_y = self._unpack_float(ddata, self.OFFSET_POSITION_Y)
            self.position_z = self._unpack_float(ddata, self.OFFSET_POSITION_Z)
            
            # Velocità 3D (m/s)
            self.velocity_x = self._unpack_float(ddata, self.OFFSET_VELOCITY_X)
            self.velocity_y = self._unpack_float(ddata, self.OFFSET_VELOCITY_Y)
            self.velocity_z = self._unpack_float(ddata, self.OFFSET_VELOCITY_Z)
            
            # G-forces calculation (acceleration/9.81)
            # Using velocity delta to calculate acceleration
            # Assuming approximately 60 updates per second (1/60 = 0.0167 seconds between updates)
            time_delta = 0.0167  # seconds between telemetry updates
            
            # Calculate accelerations (change in velocity over time)
            accel_x = (self.velocity_x - self.prev_velocity_x) / time_delta
            accel_y = (self.velocity_y - self.prev_velocity_y) / time_delta
            accel_z = (self.velocity_z - self.prev_velocity_z) / time_delta
            
            # Convert accelerations to G-forces (1G = 9.81 m/s²)
            self.lateral_g = self._validate_float(accel_x / 9.81, -5.0, 5.0)      # side-to-side (from velocity_x)
            self.vertical_g = self._validate_float(accel_y / 9.81, -5.0, 5.0)     # up/down (from velocity_y)
            self.longitudinal_g = self._validate_float(accel_z / 9.81, -5.0, 5.0) # forward/backward (from velocity_z)
            
            # Store current velocities as previous for next update
            self.prev_velocity_x = self.velocity_x
            self.prev_velocity_y = self.velocity_y
            self.prev_velocity_z = self.velocity_z
            
            # Rotazioni (radianti)
            self.rotation_pitch = self._unpack_float(ddata, self.OFFSET_ROTATION_PITCH)
            self.rotation_yaw = self._unpack_float(ddata, self.OFFSET_ROTATION_YAW)
            self.rotation_roll = self._unpack_float(ddata, self.OFFSET_ROTATION_ROLL)
            
            # Velocità angolari (radianti/s)
            self.angular_velocity_x = self._unpack_float(ddata, self.OFFSET_ANGULAR_VELOCITY_X)
            self.angular_velocity_y = self._unpack_float(ddata, self.OFFSET_ANGULAR_VELOCITY_Y)
            self.angular_velocity_z = self._unpack_float(ddata, self.OFFSET_ANGULAR_VELOCITY_Z)
            
            # === DATI VEICOLO BASE ===
            
            # Altezza da terra (m, convertito in mm)
            height_raw = self._unpack_float(ddata, self.OFFSET_RIDE_HEIGHT)
            self.ride_height = self._validate_float(height_raw * 1000, 0, 500)
            
            # RPM e limiti
            self.rpm = self._validate_float(self._unpack_float(ddata, self.OFFSET_RPM), 0, 20000)
            self.rpm_rev_warning = self._validate_int(self._unpack_short(ddata, self.OFFSET_RPM_REV_WARNING), 0, 20000)
            self.rpm_rev_limiter = self._validate_int(self._unpack_short(ddata, self.OFFSET_RPM_REV_LIMITER), 0, 20000)
            
            # Carburante (litri)
            self.current_fuel = self._validate_float(self._unpack_float(ddata, self.OFFSET_CURRENT_FUEL), 0, 200)
            self.fuel_capacity = self._validate_float(self._unpack_float(ddata, self.OFFSET_FUEL_CAPACITY), 0, 200)
            
            # Velocità veicolo (m/s, convertito in km/h)
            speed_ms = self._unpack_float(ddata, self.OFFSET_SPEED)
            self.car_speed = self._validate_float(speed_ms * 3.6, 0, 600)
            
            # Boost (pressione relativa, valore assoluto -1)
            boost_raw = self._unpack_float(ddata, self.OFFSET_BOOST)
            self.boost = self._validate_float(boost_raw - 1.0, -1, 3.0)
            
            # Temperature e pressioni
            self.oil_pressure = self._validate_float(self._unpack_float(ddata, self.OFFSET_OIL_PRESSURE), 0, 20)
            self.water_temp = self._validate_float(self._unpack_float(ddata, self.OFFSET_WATER_TEMP), 0, 200)
            self.oil_temp = self._validate_float(self._unpack_float(ddata, self.OFFSET_OIL_TEMP), 0, 200)
            
            # Temperature pneumatici (°C)
            self.tyre_temp_FL = self._validate_float(self._unpack_float(ddata, self.OFFSET_TYRE_TEMP_FL), 0, 200)
            self.tyre_temp_FR = self._validate_float(self._unpack_float(ddata, self.OFFSET_TYRE_TEMP_FR), 0, 200)
            self.tyre_temp_RL = self._validate_float(self._unpack_float(ddata, self.OFFSET_TYRE_TEMP_RL), 0, 200)
            self.tyre_temp_RR = self._validate_float(self._unpack_float(ddata, self.OFFSET_TYRE_TEMP_RR), 0, 200)
            
            # === IDENTIFICATORI E TEMPI ===
            
            # ID pacchetto e vettura
            self.package_id = self._unpack_int(ddata, self.OFFSET_PACKAGE_ID)
            self.car_id = self._unpack_int(ddata, self.OFFSET_CAR_ID)
            
            # Tempi giro (millisecondi)
            self.current_lap = self._validate_int(self._unpack_short(ddata, self.OFFSET_CURRENT_LAP), 0, 999999)
            self.total_laps = self._validate_int(self._unpack_short(ddata, self.OFFSET_TOTAL_LAPS), 0, 999)
            self.best_lap = self._validate_int(self._unpack_int(ddata, self.OFFSET_BEST_LAP), 0, 999999999)
            self.last_lap = self._validate_int(self._unpack_int(ddata, self.OFFSET_LAST_LAP), 0, 999999999)
            
            # Tempo in pista (millisecondi, convertito in secondi)
            time_ms = self._unpack_int(ddata, self.OFFSET_TIME_ON_TRACK)
            self.time_on_track = self._validate_float(time_ms / 1000.0, 0, 86400)
            
            # Posizione e contatori gara
            self.current_position = self._validate_int(self._unpack_short(ddata, self.OFFSET_CURRENT_POSITION), 0, 999)
            self.total_positions = self._validate_int(self._unpack_short(ddata, self.OFFSET_TOTAL_POSITIONS), 0, 999)
            
            # Velocità stimata
            self.estimated_top_speed = self._validate_int(self._unpack_short(ddata, self.OFFSET_ESTIMATED_TOP_SPEED), 0, 999)
            
            # Stati di gioco
            status_byte = self._unpack_byte(ddata, self.OFFSET_FLAGS)
            self.is_paused = (status_byte & 0b10) != 0
            self.in_race = (status_byte & 0b01) != 0
            
            # === CONTROLLI VEICOLO ===
            
            # Marce
            gear_byte = self._unpack_byte(ddata, self.OFFSET_GEAR)
            self.current_gear = self._validate_int(gear_byte & 0b00001111, 0, 10)
            self.suggested_gear = self._validate_int(gear_byte >> 4, 0, 10)
            
            # Controlli (throttle/brake normalizzati a 0-100%)
            throttle_raw = self._unpack_byte(ddata, self.OFFSET_THROTTLE)
            self.throttle = self._validate_float(throttle_raw / 2.55, 0, 100)
            
            brake_raw = self._unpack_byte(ddata, self.OFFSET_BRAKE)
            self.brake = self._validate_float(brake_raw / 2.55, 0, 100)
            
            # === PNEUMATICI E SOSPENSIONI ===
            
            # Diametri pneumatici (metri)
            self.tyre_diameter_FL = self._validate_float(self._unpack_float(ddata, self.OFFSET_TYRE_DIAMETER_FL), 0.1, 1.0)
            self.tyre_diameter_FR = self._validate_float(self._unpack_float(ddata, self.OFFSET_TYRE_DIAMETER_FR), 0.1, 1.0)
            self.tyre_diameter_RL = self._validate_float(self._unpack_float(ddata, self.OFFSET_TYRE_DIAMETER_RL), 0.1, 1.0)
            self.tyre_diameter_RR = self._validate_float(self._unpack_float(ddata, self.OFFSET_TYRE_DIAMETER_RR), 0.1, 1.0)
            
            # Velocità ruote (rad/s, convertito in km/h)
            tyre_speed_fl_rad = self._unpack_float(ddata, self.OFFSET_TYRE_SPEED_FL)
            tyre_speed_fr_rad = self._unpack_float(ddata, self.OFFSET_TYRE_SPEED_FR)
            tyre_speed_rl_rad = self._unpack_float(ddata, self.OFFSET_TYRE_SPEED_RL)
            tyre_speed_rr_rad = self._unpack_float(ddata, self.OFFSET_TYRE_SPEED_RR)
            
            self.tyre_speed_FL = abs(3.6 * self.tyre_diameter_FL * tyre_speed_fl_rad)
            self.tyre_speed_FR = abs(3.6 * self.tyre_diameter_FR * tyre_speed_fr_rad)
            self.tyre_speed_RL = abs(3.6 * self.tyre_diameter_RL * tyre_speed_rl_rad)
            self.tyre_speed_RR = abs(3.6 * self.tyre_diameter_RR * tyre_speed_rr_rad)
            
            # Calcolo slip ratio (velocità ruota / velocità auto)
            if self.car_speed > 0:
                self.tyre_slip_ratio_FL = '{:6.2f}'.format(self.tyre_speed_FL / self.car_speed)
                self.tyre_slip_ratio_FR = '{:6.2f}'.format(self.tyre_speed_FR / self.car_speed)
                self.tyre_slip_ratio_RL = '{:6.2f}'.format(self.tyre_speed_RL / self.car_speed)
                self.tyre_slip_ratio_RR = '{:6.2f}'.format(self.tyre_speed_RR / self.car_speed)
            else:
                self.tyre_slip_ratio_FL = '0.00'
                self.tyre_slip_ratio_FR = '0.00'
                self.tyre_slip_ratio_RL = '0.00'
                self.tyre_slip_ratio_RR = '0.00'
            
            # Sospensioni
            self.suspension_FL = self._validate_float(self._unpack_float(ddata, self.OFFSET_SUSPENSION_FL), -1.0, 1.0)
            self.suspension_FR = self._validate_float(self._unpack_float(ddata, self.OFFSET_SUSPENSION_FR), -1.0, 1.0)
            self.suspension_RL = self._validate_float(self._unpack_float(ddata, self.OFFSET_SUSPENSION_RL), -1.0, 1.0)
            self.suspension_RR = self._validate_float(self._unpack_float(ddata, self.OFFSET_SUSPENSION_RR), -1.0, 1.0)
            
            # === FRIZIONE E TRASMISSIONE ===
            
            # Frizione e RPM correlati
            self.clutch = self._validate_float(self._unpack_float(ddata, self.OFFSET_CLUTCH), 0.0, 1.0)
            self.clutch_engaged = self._validate_float(self._unpack_float(ddata, self.OFFSET_CLUTCH_ENGAGED), 0.0, 1.0)
            self.rpm_after_clutch = self._validate_float(self._unpack_float(ddata, self.OFFSET_RPM_AFTER_CLUTCH), 0, 20000)
            
            # Rapporti del cambio
            self.gear_1 = self._validate_float(self._unpack_float(ddata, self.OFFSET_GEAR_1), 0, 100)
            self.gear_2 = self._validate_float(self._unpack_float(ddata, self.OFFSET_GEAR_2), 0, 100)
            self.gear_3 = self._validate_float(self._unpack_float(ddata, self.OFFSET_GEAR_3), 0, 100)
            self.gear_4 = self._validate_float(self._unpack_float(ddata, self.OFFSET_GEAR_4), 0, 100)
            self.gear_5 = self._validate_float(self._unpack_float(ddata, self.OFFSET_GEAR_5), 0, 100)
            self.gear_6 = self._validate_float(self._unpack_float(ddata, self.OFFSET_GEAR_6), 0, 100)
            self.gear_7 = self._validate_float(self._unpack_float(ddata, self.OFFSET_GEAR_7), 0, 100)
            self.gear_8 = self._validate_float(self._unpack_float(ddata, self.OFFSET_GEAR_8), 0, 100)
            
        except Exception as e:
            logging.error(f"Errore durante la decodifica dei dati: {str(e)}")

    # === METODI DI PARSING ===
    
    def _unpack_byte(self, data, offset):
        """
        Estrae un byte dal pacchetto di dati.
        
        Args:
            data (bytes): Pacchetto di dati
            offset (int): Offset nel pacchetto
            
        Returns:
            int: Valore byte estratto
        """
        try:
            return struct.unpack('B', data[offset:offset + 1])[0]
        except:
            logging.warning(f"Errore durante l'estrazione di un byte all'offset 0x{offset:X}")
            return 0
    
    def _unpack_short(self, data, offset):
        """
        Estrae un valore short (2 byte) dal pacchetto di dati.
        
        Args:
            data (bytes): Pacchetto di dati
            offset (int): Offset nel pacchetto
            
        Returns:
            int: Valore short estratto
        """
        try:
            return struct.unpack('h', data[offset:offset + 2])[0]
        except:
            logging.warning(f"Errore durante l'estrazione di uno short all'offset 0x{offset:X}")
            return 0
    
    def _unpack_ushort(self, data, offset):
        """
        Estrae un valore unsigned short (2 byte) dal pacchetto di dati.
        
        Args:
            data (bytes): Pacchetto di dati
            offset (int): Offset nel pacchetto
            
        Returns:
            int: Valore unsigned short estratto
        """
        try:
            return struct.unpack('H', data[offset:offset + 2])[0]
        except:
            logging.warning(f"Errore durante l'estrazione di uno unsigned short all'offset 0x{offset:X}")
            return 0
    
    def _unpack_int(self, data, offset):
        """
        Estrae un valore int (4 byte) dal pacchetto di dati.
        
        Args:
            data (bytes): Pacchetto di dati
            offset (int): Offset nel pacchetto
            
        Returns:
            int: Valore int estratto
        """
        try:
            return struct.unpack('i', data[offset:offset + 4])[0]
        except:
            logging.warning(f"Errore durante l'estrazione di un int all'offset 0x{offset:X}")
            return 0
    
    def _unpack_uint(self, data, offset):
        """
        Estrae un valore unsigned int (4 byte) dal pacchetto di dati.
        
        Args:
            data (bytes): Pacchetto di dati
            offset (int): Offset nel pacchetto
            
        Returns:
            int: Valore unsigned int estratto
        """
        try:
            return struct.unpack('I', data[offset:offset + 4])[0]
        except:
            logging.warning(f"Errore durante l'estrazione di un unsigned int all'offset 0x{offset:X}")
            return 0
    
    def _unpack_float(self, data, offset):
        """
        Estrae un valore float (4 byte) dal pacchetto di dati.
        
        Args:
            data (bytes): Pacchetto di dati
            offset (int): Offset nel pacchetto
            
        Returns:
            float: Valore float estratto
        """
        try:
            return struct.unpack('f', data[offset:offset + 4])[0]
        except:
            logging.warning(f"Errore durante l'estrazione di un float all'offset 0x{offset:X}")
            return 0.0
    
    # === METODI DI VALIDAZIONE ===
    
    def _validate_int(self, value, min_value, max_value):
        """
        Valida un valore intero e lo limita all'intervallo specificato.
        
        Args:
            value (int): Valore da validare
            min_value (int): Valore minimo consentito
            max_value (int): Valore massimo consentito
            
        Returns:
            int: Valore validato
        """
        if value is None:
            return 0
        if not isinstance(value, (int, float)):
            try:
                value = int(value)
            except:
                return 0
        return max(min_value, min(value, max_value))
    
    def _validate_float(self, value, min_value, max_value):
        """
        Valida un valore float e lo limita all'intervallo specificato.
        
        Args:
            value (float): Valore da validare
            min_value (float): Valore minimo consentito
            max_value (float): Valore massimo consentito
            
        Returns:
            float: Valore validato
        """
        if value is None:
            return 0.0
        if not isinstance(value, (int, float)):
            try:
                value = float(value)
            except:
                return 0.0
        return max(min_value, min(value, max_value))
    
    def to_dict(self):
        """
        Converte l'oggetto GTData in un dizionario per la serializzazione.
        
        Returns:
            dict: Dizionario con tutti gli attributi dell'oggetto
        """
        return {key: getattr(self, key, None) for key in self.__dict__}
    
    def __str__(self):
        """
        Restituisce una rappresentazione in stringa dell'oggetto GTData.
        
        Returns:
            str: Rappresentazione in stringa dell'oggetto
        """
        speed_str = f"{self.car_speed:.1f} km/h" if hasattr(self, 'car_speed') else "N/A"
        rpm_str = f"{self.rpm:.0f} RPM" if hasattr(self, 'rpm') else "N/A"
        gear_str = f"{self.current_gear}" if hasattr(self, 'current_gear') else "N/A"
        lateral_g_str = f"{self.lateral_g:.2f}G" if hasattr(self, 'lateral_g') else "N/A"
        longitudinal_g_str = f"{self.longitudinal_g:.2f}G" if hasattr(self, 'longitudinal_g') else "N/A"
        
        return f"GTData(Speed: {speed_str}, RPM: {rpm_str}, Gear: {gear_str}, Lateral G: {lateral_g_str}, Longitudinal G: {longitudinal_g_str})"

