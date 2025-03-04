# mechanics.py

def calc_slip_ratio(tyre_speed_ms, car_speed_ms):
    eps = 1e-3
    if car_speed_ms < eps:
        return 0.0
    return (tyre_speed_ms - car_speed_ms) / car_speed_ms

def extract_features(telemetry_dict):
    car_speed_kmh = telemetry_dict.get("car_speed", 0.0)
    car_speed_ms = car_speed_kmh / 3.6

    fl_ms = telemetry_dict.get("tyre_speed_fl", 0.0)
    fr_ms = telemetry_dict.get("tyre_speed_fr", 0.0)
    rl_ms = telemetry_dict.get("tyre_speed_rl", 0.0)
    rr_ms = telemetry_dict.get("tyre_speed_rr", 0.0)

    fl_slip = calc_slip_ratio(fl_ms, car_speed_ms)
    fr_slip = calc_slip_ratio(fr_ms, car_speed_ms)
    rl_slip = calc_slip_ratio(rl_ms, car_speed_ms)
    rr_slip = calc_slip_ratio(rr_ms, car_speed_ms)
    avg_slip = (abs(fl_slip) + abs(fr_slip) + abs(rl_slip) + abs(rr_slip)) / 4.0

    throttle_pct = telemetry_dict.get("throttle", 0.0)
    brake_pct = telemetry_dict.get("brake", 0.0)
    rpm = telemetry_dict.get("rpm", 0.0)
    gear = float(telemetry_dict.get("current_gear", 0))

    return {
        "car_speed_kmh": car_speed_kmh,
        "avg_slip_ratio": avg_slip,
        "throttle_pct": throttle_pct,
        "brake_pct": brake_pct,
        "rpm": rpm,
        "gear": gear
    }
