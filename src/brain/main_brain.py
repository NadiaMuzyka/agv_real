# FILE: src/brain/main_brain.py (VERSIONE CORRETTA)
import time
import sys
import os
import py_trees

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.bt_manager import crea_albero_agv
from modules.redis_interface import RedisInterface 
from modules.logic_controller import LogicController 

def main():
    print("🧠 Avvio BRAIN. Implementazione Logic Controller su Redis Pub/Sub...")
    
    redis_manager = RedisInterface() 
    if not redis_manager.db:
        print("[BRAIN] Errore critico: Uscita per mancata connessione a Redis.")
        return 
   
    # --- INIZIALIZZAZIONE BLACKBOARD ---
    # Creiamo un client per scrivere i dati nella memoria del BT
    blackboard_client = py_trees.blackboard.Client(name="ClientBrain")
    
    # Registriamo le chiavi che i nodi dovranno leggere
    blackboard_client.register_key(key="battery_level", access=py_trees.common.Access.WRITE)
    blackboard_client.register_key(key="person_detected", access=py_trees.common.Access.WRITE)
    blackboard_client.register_key(key="pallet_list_empty", access=py_trees.common.Access.WRITE)
    blackboard_client.register_key(key="emergency_state", access=py_trees.common.Access.WRITE)
    blackboard_client.register_key(key="line_error", access=py_trees.common.Access.WRITE)
    blackboard_client.register_key(key="current_target", access=py_trees.common.Access.WRITE)
    blackboard_client.register_key(key="mission_queue", access=py_trees.common.Access.WRITE)
    
    # Valori iniziali di default
    blackboard_client.battery_level = 100.0
    blackboard_client.person_detected = False
    blackboard_client.pallet_list_empty = False
    blackboard_client.emergency_state = False
    blackboard_client.line_error = 0.0
    blackboard_client.current_target = None
    blackboard_client.mission_queue = []
         
    # --- INIZIALIZZAZIONE LOGIC CONTROLLER ---
    logic_controller = LogicController(redis_manager) 
    
    # Creazione e setup del Behavior Tree  (blackboard e logic controller)
    behavior_tree = crea_albero_agv() 
    tree_executor = py_trees.trees.BehaviourTree(behavior_tree)
    tree_executor.setup(timeout=15) 

    SENSORS_KEY = "agv_sensors"
    print("[BRAIN] Ingresso nel ciclo principale...")
    try:
        while True:
            # --- LETTURA SENSORI REALI ---
            sensor_data = redis_manager.get_sensor_data(SENSORS_KEY)
            if sensor_data:
                blackboard_client.emergency_state = sensor_data.get("emergency", False)
                if blackboard_client.emergency_state:
                    print(f"[BRAIN] 🚨 RILEVATA EMERGENZA DA BODY! (Bumper: {sensor_data.get('bumper')})")

            # --- AGGIORNAMENTO SIMULATO (SOLO PER IL TEST) ---
            # Diamo al BT dati sufficienti per iniziare a lavorare e generare un comando V/W
            blackboard_client.battery_level = 90.0 # Batteria OK
            blackboard_client.person_detected = False
            blackboard_client.line_error = 0.1 # Simula un errore di linea per innescare il LineFollower
            
            if not blackboard_client.current_target and not blackboard_client.mission_queue:
                blackboard_client.current_target = {'id': 'HOME', 'prio': 100} 
            
            tree_executor.tick()
            
            # Il Brain invia comandi solo quando il BT fa un tick e ne ha bisogno.
            time.sleep(0.1) 

    except KeyboardInterrupt:
        print("Spegnimento Brain...")

if __name__ == "__main__":
    main()
    


