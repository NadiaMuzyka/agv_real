# FILE: src/body/main_body.py

import time
import os
import sys
import json

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
    print("🦾 [BODY] Avvio del Controllore (Ascolto Redis Pub/Sub)...")
    
    redis_iface = RedisInterface()
    manager = LowLevelManager()
    bumper = BumperSensor()

    if not redis_iface.db:
        print("[BODY] Errore critico: Il Body non può ricevere comandi senza Redis.")
        return

    # 1. Iscrizione al canale dei comandi (Pub/Sub)
    pubsub = redis_iface.subscribe_to_commands()
    if not pubsub:
        print("[BODY] Errore nell'iscrizione al canale Pub/Sub.")
        return

    last_command = {"v": -1.0, "w": -1.0} 
    emergency_state = False
    
    # Variabili per memorizzare l'ultimo comando ricevuto via Pub/Sub
    current_v = 0.0
    current_w = 0.0

    # Ciclo di esecuzione principale
    while True:
        # --- 0. READ SENSORS & CHECK SAFETY ---
        is_bumper_pressed = bumper.read()
        
        if is_bumper_pressed:
            if not emergency_state:
                print("[BODY] 🚨 EMERGENCY: Bumper pressed! Stopping immediately.")
            emergency_state = True

        # Publish Sensor Data
        sensor_data = {
            "bumper": is_bumper_pressed,
            "emergency": emergency_state
        }
        redis_iface.set_sensor_data(SENSORS_KEY, sensor_data)

        # --- 1. READ MESSAGES (Pub/Sub) ---
        # Usiamo un timeout basso per non bloccare il loop dei sensori
        message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.01) 
        
        if message and message['type'] == 'message':
            channel = message['channel']
            try:
                data = json.loads(message['data'])
                
                # Gestione Reset (Interrupt-like)
                if channel == RedisInterface.RESET_CHANNEL:
                    if data.get("reset", False) and emergency_state:
                        print("[BODY] ✅ RESET: Emergency state cleared manually.")
                        emergency_state = False
                
                # Gestione Comandi di Velocità
                elif channel == RedisInterface.COMMAND_CHANNEL:
                    current_v = data.get("v", 0.0)
                    current_w = data.get("w", 0.0)

            except json.JSONDecodeError:
                print(f"[BODY] Errore nella decodifica del messaggio su {channel}.")

        # --- 2. APPLY SAFETY & ACT ---
        final_v = current_v
        final_w = current_w
        
        # SAFETY OVERRIDE
        if emergency_state:
            final_v = 0.0
            final_w = 0.0
        
        # ACT (Invia al Controllore di Basso Livello solo se il comando è cambiato)
        if final_v != last_command["v"] or final_w != last_command["w"]:
            manager.execute_command(final_v, final_w)
            last_command["v"] = final_v
            last_command["w"] = final_w
            
        time.sleep(0.05)  # Loop a 20HzS

if __name__ == "__main__":
    main()