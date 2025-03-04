# gtdata.py

import struct
from datetime import datetime

class GTData:
    def __init__(self, ddata):
        # Lista delle chiavi attese
        keys = [
            "timestamp",
            "package_id",
            "car_id",
            "best_lap",
            "last_lap",
            "current_lap",
            "total_laps",
            "current_gear",
            "suggested_gear",
            "gear_1",
            "gear_2",
            "gear_3",
            "gear_4",
            "gear_5",
            "gear_6",
            "gear_7",
            "gear_8",
            "fuel_capacity",
            "current_fuel",
            "car_speed",
            "tyre_speed_fl",
            "tyre_speed_fr",
            "tyre_speed_rl",
            "tyre_speed_rr",
            "position_x",
            "position_y",
            "position_z",
            "velocity_x",
            "velocity_y",
            "velocity_z",
            "rotation_pitch",
            "rotation_yaw",
            "rotation_roll",
            "angular_velocity_x",
            "angular_velocity_y",
            "angular_velocity_z",
            "oil_temp",
            "water_temp",
            "tyre_temp_fl",
            "tyre_temp_fr",
            "tyre_temp_rl",
            "tyre_temp_rr",
            "oil_pressure",
            "ride_height",
            "suspension_fl",
            "suspension_fr",
            "suspension_rl",
            "suspension_rr",
            "current_position",
            "total_positions",
            "throttle",
            "rpm",
            "rpm_rev_warning",
            "brake",
            "boost",
            "rpm_rev_limiter",
            "estimated_top_speed",
            "clutch",
            "clutch_engaged",
            "rpm_after_clutch",
            "is_paused",
            "in_race"
        ]
        # Inizializziamo tutti gli attributi con valore di default (None)
        for key in keys:
            setattr(self, key, None)
        # Impostiamo il timestamp
        self.timestamp = datetime.now().isoformat()

        # Se i dati non sono validi, esci subito (gli attributi resteranno None)
        if not ddata or len(ddata) < 296:
            return

        try:
            # Identificatori
            self.package_id, = struct.unpack('i', ddata[0x70:0x70 + 4])
            self.car_id, = struct.unpack('i', ddata[0x124:0x124 + 4])

            # Giri: convertiamo i millisecondi in secondi
            best_lap_ms, = struct.unpack('i', ddata[0x78:0x78 + 4])
            last_lap_ms, = struct.unpack('i', ddata[0x7C:0x7C + 4])
            self.best_lap = best_lap_ms / 1000.0
            self.last_lap = last_lap_ms / 1000.0
            self.current_lap, = struct.unpack('h', ddata[0x74:0x74 + 2])
            self.total_laps, = struct.unpack('h', ddata[0x76:0x76 + 2])

            # Marce
            gear_byte = struct.unpack('B', ddata[0x90:0x90 + 1])[0]
            self.current_gear = gear_byte & 0x0F
            self.suggested_gear = gear_byte >> 4
            self.gear_1, = struct.unpack('f', ddata[0x104:0x104 + 4])
            self.gear_2, = struct.unpack('f', ddata[0x108:0x108 + 4])
            self.gear_3, = struct.unpack('f', ddata[0x10C:0x10C + 4])
            self.gear_4, = struct.unpack('f', ddata[0x110:0x110 + 4])
            self.gear_5, = struct.unpack('f', ddata[0x114:0x114 + 4])
            self.gear_6, = struct.unpack('f', ddata[0x118:0x118 + 4])
            self.gear_7, = struct.unpack('f', ddata[0x11C:0x11C + 4])
            self.gear_8, = struct.unpack('f', ddata[0x120:0x120 + 4])

            # Carburante
            self.fuel_capacity, = struct.unpack('f', ddata[0x48:0x48 + 4])
            self.current_fuel, = struct.unpack('f', ddata[0x44:0x44 + 4])

            # Velocità: car_speed (da m/s a km/h)
            car_speed_ms, = struct.unpack('f', ddata[0x4C:0x4C + 4])
            self.car_speed = car_speed_ms * 3.6

            # Velocità ruote in m/s
            self.tyre_speed_fl, = struct.unpack('f', ddata[0xA4:0xA4 + 4])
            self.tyre_speed_fr, = struct.unpack('f', ddata[0xA8:0xA8 + 4])
            self.tyre_speed_rl, = struct.unpack('f', ddata[0xAC:0xAC + 4])
            self.tyre_speed_rr, = struct.unpack('f', ddata[0xB0:0xB0 + 4])

            # Posizione
            self.position_x, = struct.unpack('f', ddata[0x04:0x04 + 4])
            self.position_y, = struct.unpack('f', ddata[0x08:0x08 + 4])
            self.position_z, = struct.unpack('f', ddata[0x0C:0x0C + 4])

            # Velocità 3D
            self.velocity_x, = struct.unpack('f', ddata[0x10:0x10 + 4])
            self.velocity_y, = struct.unpack('f', ddata[0x14:0x14 + 4])
            self.velocity_z, = struct.unpack('f', ddata[0x18:0x18 + 4])

            # Rotazione (gradi)
            self.rotation_pitch, = struct.unpack('f', ddata[0x1C:0x1C + 4])
            self.rotation_yaw, = struct.unpack('f', ddata[0x20:0x20 + 4])
            self.rotation_roll, = struct.unpack('f', ddata[0x24:0x24 + 4])

            # Velocità angolare (gradi/s)
            self.angular_velocity_x, = struct.unpack('f', ddata[0x2C:0x2C + 4])
            self.angular_velocity_y, = struct.unpack('f', ddata[0x30:0x30 + 4])
            self.angular_velocity_z, = struct.unpack('f', ddata[0x34:0x34 + 4])

            # Temperature (°C)
            self.oil_temp, = struct.unpack('f', ddata[0x5C:0x5C + 4])
            self.water_temp, = struct.unpack('f', ddata[0x58:0x58 + 4])
            self.tyre_temp_fl, = struct.unpack('f', ddata[0x60:0x60 + 4])
            self.tyre_temp_fr, = struct.unpack('f', ddata[0x64:0x64 + 4])
            self.tyre_temp_rl, = struct.unpack('f', ddata[0x68:0x68 + 4])
            self.tyre_temp_rr, = struct.unpack('f', ddata[0x6C:0x6C + 4])

            # Pressione
            self.oil_pressure, = struct.unpack('f', ddata[0x54:0x54 + 4])

            # Altezza da terra (m->mm)
            raw_rh, = struct.unpack('f', ddata[0x38:0x38 + 4])
            self.ride_height = raw_rh * 1000.0

            # Sospensione
            self.suspension_fl, = struct.unpack('f', ddata[0xC4:0xC4 + 4])
            self.suspension_fr, = struct.unpack('f', ddata[0xC8:0xC8 + 4])
            self.suspension_rl, = struct.unpack('f', ddata[0xCC:0xCC + 4])
            self.suspension_rr, = struct.unpack('f', ddata[0xD0:0xD0 + 4])

            # Altro
            self.current_position, = struct.unpack('h', ddata[0x84:0x84 + 2])
            self.total_positions, = struct.unpack('h', ddata[0x86:0x86 + 2])

            # Throttle e Brake [0..255] -> [0..100]%
            thr_byte = struct.unpack('B', ddata[0x91:0x91 + 1])[0]
            self.throttle = thr_byte / 2.55

            self.rpm, = struct.unpack('f', ddata[0x3C:0x3C + 4])
            self.rpm_rev_warning, = struct.unpack('H', ddata[0x88:0x88 + 2])

            brk_byte = struct.unpack('B', ddata[0x92:0x92 + 1])[0]
            self.brake = brk_byte / 2.55

            raw_boost, = struct.unpack('f', ddata[0x50:0x50 + 4])
            self.boost = raw_boost - 1.0

            self.rpm_rev_limiter, = struct.unpack('H', ddata[0x8A:0x8A + 2])
            self.estimated_top_speed, = struct.unpack('h', ddata[0x8C:0x8C + 2])

            self.clutch, = struct.unpack('f', ddata[0xF4:0xF4 + 4])
            self.clutch_engaged, = struct.unpack('f', ddata[0xF8:0xF8 + 4])
            self.rpm_after_clutch, = struct.unpack('f', ddata[0xFC:0xFC + 4])

            byte_pi = struct.unpack('B', ddata[0x8E:0x8E + 1])[0]
            self.is_paused = (byte_pi & 0b10) != 0
            self.in_race = (byte_pi & 0b01) != 0
        except Exception as e:
            print(f"[GTData] Errore nella decodifica: {e}")

    def to_dict(self):
        keys = [
            "timestamp",
            "package_id",
            "car_id",
            "best_lap",
            "last_lap",
            "current_lap",
            "total_laps",
            "current_gear",
            "suggested_gear",
            "gear_1",
            "gear_2",
            "gear_3",
            "gear_4",
            "gear_5",
            "gear_6",
            "gear_7",
            "gear_8",
            "fuel_capacity",
            "current_fuel",
            "car_speed",
            "tyre_speed_fl",
            "tyre_speed_fr",
            "tyre_speed_rl",
            "tyre_speed_rr",
            "position_x",
            "position_y",
            "position_z",
            "velocity_x",
            "velocity_y",
            "velocity_z",
            "rotation_pitch",
            "rotation_yaw",
            "rotation_roll",
            "angular_velocity_x",
            "angular_velocity_y",
            "angular_velocity_z",
            "oil_temp",
            "water_temp",
            "tyre_temp_fl",
            "tyre_temp_fr",
            "tyre_temp_rl",
            "tyre_temp_rr",
            "oil_pressure",
            "ride_height",
            "suspension_fl",
            "suspension_fr",
            "suspension_rl",
            "suspension_rr",
            "current_position",
            "total_positions",
            "throttle",
            "rpm",
            "rpm_rev_warning",
            "brake",
            "boost",
            "rpm_rev_limiter",
            "estimated_top_speed",
            "clutch",
            "clutch_engaged",
            "rpm_after_clutch",
            "is_paused",
            "in_race"
        ]
        return { key: getattr(self, key, None) for key in keys }

