# FILE: src/body/main_body.py

import time
import os
import sys

# Aggiusta il path per importare i moduli interni
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules/controllers'))

from redis_interface import RedisInterface
from low_level_manager import LowLevelManager
from sensors.bumper_sensor import BumperSensor

# --- COSTANTI ---
COMMAND_KEY = "agv_command"
SENSORS_KEY = "agv_sensors"
RESET_KEY = "agv_reset"

def main():
    print("🦾 [BODY] Avvio del Controllore (Ascolto Redis Message Broker)...")
    
    redis_iface = RedisInterface()
    manager = LowLevelManager()
    bumper = BumperSensor()

    if not redis_iface.db:
        print("[BODY] Errore critico: Il Body non può ricevere comandi senza Redis.")
        return

    last_command = {"v": -1.0, "w": -1.0} 
    emergency_state = False

    while True:
        # 0. READ SENSORS & CHECK SAFETY
        is_bumper_pressed = bumper.read()
        
        # Check reset
        reset_data = redis_iface.get_command(RESET_KEY)
        reset_requested = reset_data.get("reset", False)

        if is_bumper_pressed:
            if not emergency_state:
                print("[BODY] 🚨 EMERGENCY: Bumper pressed! Stopping immediately.")
            emergency_state = True
        elif emergency_state and reset_requested:
            print("[BODY] ✅ RESET: Emergency state cleared manually.")
            emergency_state = False

        # Publish Sensor Data
        sensor_data = {
            "bumper": is_bumper_pressed,
            "emergency": emergency_state
        }
        redis_iface.set_sensor_data(SENSORS_KEY, sensor_data)

        # 1. READ COMMAND (Legge i comandi dal Brain via Redis)
        command = redis_iface.get_command(COMMAND_KEY)
        V = command.get("v", 0.0)
        W = command.get("w", 0.0)
        
        # SAFETY OVERRIDE
        if emergency_state:
            V = 0.0
            W = 0.0
        
        # 2. ACT (Invia al Controllore di Basso Livello solo se il comando è cambiato)
        if V != last_command["v"] or W != last_command["w"]:
            manager.execute_command(V, W)
            last_command["v"] = V
            last_command["w"] = W

        time.sleep(0.1) 

if __name__ == "__main__":
    main()