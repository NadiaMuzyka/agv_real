import time
import json
import os
import signal # Per gestire l'interruzione del processo con Ctrl+C

from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.color_sensor import ColorSensor
from modules.redis_interface import RedisInterface 
from modules.controllers.low_level_manager import LowLevelManager

#NOTA: per eseguire mettere docker compose up --build body

# --- COSTANTI ---
SENSORS_KEY = "agv_sensors"

def main():
    print("🦾 [BODY] Avvio del Controllore - Modalità Color Sensor...")

    def spegnimento_sicuro(signum, frame):
        print("\n[BODY] Ricevuto segnale di spegnimento da Docker (SIGTERM)!")
        raise KeyboardInterrupt()
    
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
    #manager = LowLevelManager(sim) 
    color_sensor = ColorSensor(sim, "/Robot/visionSensor") 

    # 3. Iscrizione ai comandi dal Brain
    pubsub = redis_iface.subscribe_to_commands()
    current_command_data = {"type": "STOP"}

    print("🚀 Loop principale avviato (20Hz).")
    
    try:
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
        #manager = LowLevelManager(sim) 
        floor_sensor = ColorSensor(sim, "/Robot/visionSensor") 

        # 3. Iscrizione ai comandi dal Brain
        pubsub = redis_iface.subscribe_to_commands()
        current_command_data = {"type": "STOP"}

        print("🚀 Loop principale avviato (20Hz).")
    
        while True:
            # --- 0. SENSING ---
            # Legge (r, g, b) normalizzati (0.0 - 1.0)
            rgb = color_sensor.read() 

            print(f"[SENSORS] color Color RGB: {rgb}")
            
            # --- 1. COMUNICAZIONE (Verso Redis) ---
            
            sensor_data = {
                "color_color": rgb,  # Invia la tupla (r, g, b)
                "timestamp": time.time()
            }
            redis_iface.set_sensor_data(SENSORS_KEY, sensor_data)
            '''
            # --- 2. LETTURA COMANDI (Da Redis) ---
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.001) 
            if message and message['type'] == 'message':
                try:
                    current_command_data = json.loads(message['data'])
                except json.JSONDecodeError:
                    print("[BODY] Errore decodifica comando JSON.")


            # --- 3. ACTUATION (Esecuzione Motori) ---
            # Il manager trasforma il comando (es. {"type": "MOVE", "speed": 0.5}) 
            # in velocità per le ruote in CoppeliaSim
            manager.execute_command(current_command_data)
                
            time.sleep(0.05) # Manteniamo i 20Hz per stabilità
            '''
            
    except KeyboardInterrupt:
        print("\n🛑 Arresto manuale del Body.")
    except Exception as e:
        print(f"❌ Errore nel loop: {e}")

if __name__ == "__main__":
    main()