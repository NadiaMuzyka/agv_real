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
    # Registriamo la chiave per il Logic Controller, che sarà un oggetto condiviso
    blackboard_client.register_key(key="logic_controller", access=py_trees.common.Access.WRITE)
    blackboard_client.logic_controller = logic_controller

    # Creazione e setup del Behavior Tree  
    behavior_tree = crea_albero_agv(logic_controller) 
    tree_executor = py_trees.trees.BehaviourTree(behavior_tree)
    tree_executor.setup(timeout=15) 

    print("[BRAIN] Ingresso nel ciclo principale...")
    try:
        while True:
            #lettura dei dati percepiti ed elaborati daisensori da Resdis
            sensor_data = logic_controller.read_sensors_data_from_redis()
            
            #aggiornamento della blackboard con i dati dei sensori provenienti da Redis
            logic_controller.update_blackboard_from_sensors(sensor_data)
            
            #tick del BT
            tree_executor.tick()
            
            # Il Brain invia comandi solo quando il BT fa un tick e ne ha bisogno.
            time.sleep(0.1) 

    except KeyboardInterrupt:
        print("Spegnimento Brain...")

if __name__ == "__main__":
    main()