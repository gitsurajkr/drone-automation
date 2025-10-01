from datetime import datetime

class TelemetryData:
    def __init__(self, vehicle):
        self.vehicle = vehicle

    async def snapshot(self):
        if self.vehicle is None:
            return None

        # Grab both relative and global frames so we can expose both AGL and MSL altitudes.
        # Prefer the relative frame (global_relative_frame) for the primary 'alt' value when available.
        loc_rel = getattr(self.vehicle.location, "global_relative_frame", None)
        loc_global = getattr(self.vehicle.location, "global_frame", None)
        att = getattr(self.vehicle, "attitude", None)
        vel = getattr(self.vehicle, "velocity", None)
        gps = getattr(self.vehicle, "gps_0", None)
        bat = getattr(self.vehicle, "battery", None)
        armed = getattr(self.vehicle, "armed", None)
        mode = getattr(self.vehicle.mode, "name", None)
        heading = getattr(self.vehicle, "heading", None)
        gs = getattr(self.vehicle, "groundspeed", None)
        aspeed = getattr(self.vehicle, "airspeed", None)
        vz = getattr(self.vehicle, "climb_rate", None)
        rc_channels = getattr(self.vehicle, "rc_channels", None)
        last_heartbeat = getattr(self.vehicle, "last_heartbeat", None)
        system_status = getattr(self.vehicle, "system_status", None)
        home = getattr(self.vehicle, "home_location", None)

        # Optional fields
        flight_time = getattr(self.vehicle, "flight_time", None)
        status_text = getattr(self.vehicle, "last_status", None)

        ekf_ok = getattr(self.vehicle, "ekf_ok", None)
        # ekf_variances = {
        #     "pos_horiz": getattr(self.vehicle, "pos_horiz_variance", None),
        #     "pos_vert": getattr(self.vehicle, "pos_vert_variance", None),
        #     "vel_horiz": getattr(self.vehicle, "vel_horiz_variance", None),
        #     "vel_vert": getattr(self.vehicle, "vel_vert_variance", None),
        #     "compass": getattr(self.vehicle, "compass_variance", None),
        #     "terrain_alt": getattr(self.vehicle, "terrain_alt_variance", None)
        # }

        def fmt(val):
            # Support both float and int values for rounding.
            if isinstance(val, (float, int)):
                try:
                    return round(float(val), 2)
                except Exception:
                    return val
            return val

        rc_data = None
        if rc_channels:
            try:
                rc_data = {str(k): fmt(v) for k, v in rc_channels.items()}
            except Exception:
                rc_data = str(rc_channels) 

        data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "location": {
                "lat": fmt((loc_rel or loc_global).lat) if (loc_rel or loc_global) else None,
                "lon": fmt((loc_rel or loc_global).lon) if (loc_rel or loc_global) else None,
                "alt": fmt(loc_rel.alt) if loc_rel and hasattr(loc_rel, "alt") else (fmt(loc_global.alt) if loc_global and hasattr(loc_global, "alt") else None),
                "alt_rel": fmt(loc_rel.alt) if loc_rel and hasattr(loc_rel, "alt") else None,
                "alt_global": fmt(loc_global.alt) if loc_global and hasattr(loc_global, "alt") else None,
            },
            "attitude": {
                "roll": fmt(att.roll) if att else None,
                "pitch": fmt(att.pitch) if att else None,
                "yaw": fmt(att.yaw) if att else None
            },
            "velocity": {
                "vx": fmt(vel[0]) if vel else None,
                "vy": fmt(vel[1]) if vel else None,
                "vz": fmt(vel[2]) if vel else None
            },
            "battery": {
                "voltage": fmt(bat.voltage) if bat else None,
                "current": fmt(bat.current) if bat else None,
                "level": fmt(bat.level) if bat else None
            },
            "gps": {
                "satellites_visible": gps.satellites_visible if gps else None,
                "fix_type": gps.fix_type if gps else None,
                "eph": fmt(gps.eph) if gps and hasattr(gps, "eph") else None,
                "epv": fmt(gps.epv) if gps and hasattr(gps, "epv") else None
            },
            "heading": heading if heading else None,
            "groundspeed": fmt(gs) if gs else None,
            "airspeed": fmt(aspeed) if aspeed is not None else 0.0,
            "climb_rate": fmt(vz) if vz is not None else 0.0,
            "rc_channels": rc_data if rc_data is not None else {},
            "home_position": {
                "lat": fmt(home.lat) if home and hasattr(home, "lat") else 0.0,
                "lon": fmt(home.lon) if home and hasattr(home, "lon") else 0.0,
                "alt": fmt(home.alt) if home and hasattr(home, "alt") else 0.0
            },
            "flight_time": fmt(flight_time) if flight_time is not None else 0.0,
            "status_text": status_text if status_text is not None else "",
            "ekf": {
                "ok": ekf_ok,
                # "variances": {k: fmt(v) if v else None for k, v in ekf_variances.items()}
            },
            "armed": armed,
            "mode": mode,
            "last_heartbeat": fmt(last_heartbeat) if last_heartbeat else None,
            "system_status": str(system_status)
        }
        return data

    def print_stats(self, data, indent=0):
        pad = "  " * indent
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    print(f"{pad}{k}:")
                    self.print_stats(v, indent + 1)
                else:
                    print(f"{pad}{k}: {v}")
        else:
            print(f"{pad}{data}")
