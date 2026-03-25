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
    
    # --- INIZIALIZZAZIONE LOGIC CONTROLLER ---
    logic_controller = LogicController(redis_manager) 
       
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
    blackboard_client.register_key(key="current_position", access=py_trees.common.Access.WRITE)

    # Registriamo la chiave per il Logic Controller, che sarà un oggetto condiviso
    blackboard_client.register_key(key="logic_controller", access=py_trees.common.Access.WRITE)
    blackboard_client.logic_controller = logic_controller
    
    # Valori iniziali di default della blackboard
    blackboard_client.battery_level = 100.0
    blackboard_client.person_detected = False
    blackboard_client.pallet_list_empty = False
    blackboard_client.emergency_state = False
    blackboard_client.line_error = 0.0
    blackboard_client.current_target = None
    blackboard_client.mission_queue = []
    blackboard_client.current_position = "ER"

    # Creazione e setup del Behavior Tree  
    behavior_tree = crea_albero_agv() 
    tree_executor = py_trees.trees.BehaviourTree(behavior_tree)
    tree_executor.setup(timeout=15) 

    print("[BRAIN] Ingresso nel ciclo principale...")
    try:
        while True:
            #lettura dei dati percepiti ed elaborati daisensori da Resdis
            sensor_data = logic_controller.read_sensors_data_from_redis()
            
            #aggiornamento della blackboard con i dati dei sensori provenienti da Redis
            logic_controller.update_blackboard_from_sensors(sensor_data, blackboard_client)
            
            #tick del BT
            tree_executor.tick()
            
            # Il Brain invia comandi solo quando il BT fa un tick e ne ha bisogno.
            time.sleep(0.1) 

    except KeyboardInterrupt:
        print("Spegnimento Brain...")

if __name__ == "__main__":
    main()