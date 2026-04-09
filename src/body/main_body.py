import time
import math
import json
import os

from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.color_sensor import ColorSensor
from modules.actuators.wheel_actuator import WheelsActuator
from modules.redis_interface import RedisInterface 
from modules.controllers.low_level_manager import LowLevelManager

#NOTA: per eseguire mettere docker compose up --build body

# --- COSTANTI ---
SENSORS_KEY = "agv_sensors"

def is_color_match(rgb, target, tolerance=40):
    if not rgb:
        return False
    return all(abs(c - t) <= tolerance for c, t in zip(rgb, target))

def main():
    print("🦾 [BODY] Avvio del Controllore - Modalità Line Follower (PID 3 Sensori)...")
    
    # 1. Inizializzazione Connessioni (Coppelia & Redis)
    connector = CoppeliaConnector()
    sim = connector.get_sim()
    
    redis_iface = RedisInterface()
    if not redis_iface.db:
        print("[BODY] Errore critico: Redis non raggiungibile.")
        return

    if not sim:
        print("[BODY] Errore critico: Impossibile connettersi a CoppeliaSim.")
        return

    # 2. Inizializzazione Moduli
    manager = LowLevelManager(sim) 
    wheels = WheelsActuator(sim)
    left_sensor = ColorSensor(sim, "/Robot/leftColorSensor")
    central_sensor = ColorSensor(sim, "/Robot/centralColorSensor") 
    right_sensor = ColorSensor(sim, "/Robot/rightColorSensor")

    # 3. Iscrizione ai comandi dal Brain (per ora gestito autonomamente)
    pubsub = redis_iface.subscribe_to_commands()
    
    print("🚀 Loop principale avviato (20Hz).")
    
    last_error = 0.0
    
    try:
        while True:
            # --- 0. SENSING ---
            rgb_left = left_sensor.read()
            rgb_center = central_sensor.read()
            rgb_right = right_sensor.read()
            
            # Colori target
            color_line = (22, 22, 22)
            color_obstacle = (99, 255, 22)
            
            # Controllo Ostacolo (controlliamo i 3 sensori o solo centrale)
            if is_color_match(rgb_center, color_obstacle, 40):
                print(f"🛑 OSTACOLO RILEVATO! Colore: {rgb_center}. Avvio manovra evasiva...")
                wheels.stop()
                current_command_data = {"type": "STOP"}
                manager.execute_command(current_command_data) # Resetta stato PID
                time.sleep(0.5)
                
                # 2. Ruota di 90 gradi a destra
                print("🔄 Giro di 90 gradi a destra...")
                w_target = -0.5
                duration = (math.pi / 2) / abs(w_target)
                wheels.move(0.0, w_target)
                time.sleep(duration)
                
                # 3. Avanza per superarlo
                print("➡️ Avanzo per superare l'ostacolo...")
                wheels.move(0.1, 0.0)
                time.sleep(2.0)
                
                print("✅ Manovra finita. Riprendo esplorazione.")
                wheels.stop()
                time.sleep(1.0)
                continue
                
            # Logica Line Follower - Calcolo errore
            on_line_l = is_color_match(rgb_left, color_line, 50)
            on_line_c = is_color_match(rgb_center, color_line, 50)
            on_line_r = is_color_match(rgb_right, color_line, 50)
            
            error = 0.0
            if on_line_l and on_line_c:
                error = -0.5  # Leggermente a destra, curvi dolce a sinistra
            elif on_line_r and on_line_c:
                error = 0.5   # Leggermente a sinistra, curvi dolce a destra
            elif on_line_l:
                error = -1.0  # Decisamente a destra, curvi forte a sx
            elif on_line_r:
                error = 1.0   # Decisamente a sinistra, curvi forte a dx
            elif on_line_c:
                error = 0.0   # Perfettamente al centro
            else:
                # Nessun sensore vede la linea. Esagera l'ultimo errore noto per riprendere la rotta
                error = 1.5 if last_error > 0 else (-1.5 if last_error < 0 else 0.0)
                
            last_error = error

            current_command_data = {
                "type": "LINE_FOLLOW",
                "error": error,
                "target_speed": 0.1 # Velocità di crociera
            }
            
            # --- 1. COMUNICAZIONE (Verso Redis) ---
            sensor_data = {
                "color_left": rgb_left,
                "color_center": rgb_center,
                "color_right": rgb_right,
                "timestamp": time.time()
            }
            redis_iface.set_sensor_data(SENSORS_KEY, sensor_data)
            
            '''
            # Ricezione Comandi da Redis ignorata per via del comportamento autonomo in basso livello
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.001) 
            # ...
            '''

            # --- 2. ACTUATION (Esecuzione Motori) ---
            V, W = manager.execute_command(current_command_data)
            wheels.move(V, W)
                
            time.sleep(0.05) # Manteniamo i 20Hz per stabilità
            
    except KeyboardInterrupt:
        print("\n🛑 Arresto manuale del Body.")
        wheels.stop()
    except Exception as e:
        print(f"❌ Errore nel loop: {e}")
        wheels.stop()

if __name__ == "__main__":
    main()