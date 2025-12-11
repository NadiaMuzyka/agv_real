# FILE: src/brain/main_brain.py (VERSIONE CORRETTA)
import time
import sys
import os
import py_trees

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.bt_manager import create_agv_tree, RobotBlackboard
from modules.redis_interface import RedisInterface 
from modules.logic_controller import LogicController 

def main():
    print("🧠 Avvio BRAIN. Implementazione Logic Controller su Redis Pub/Sub...")
    
    redis_manager = RedisInterface() 
    if not redis_manager.db:
        print("[BRAIN] Errore critico: Uscita per mancata connessione a Redis.")
        return 
        
    blackboard = RobotBlackboard()
    logic_controller = LogicController(redis_manager) 
    
    behavior_tree = create_agv_tree(blackboard, logic_controller) 
    tree_executor = py_trees.trees.BehaviourTree(behavior_tree)
    tree_executor.setup(timeout=15) 

    try:
        while True:
            # --- AGGIORNAMENTO SIMULATO (INPUT AL BT) ---
            blackboard.battery_level = 90.0
            blackboard.line_error = 0.1 # Simula un errore di linea costante per innescare il movimento
            
            if not blackboard.current_target and not blackboard.mission_queue:
                blackboard.current_target = {'id': 'HOME', 'prio': 100} 
            
            tree_executor.tick()
            
            # Il Brain invia comandi solo quando il BT fa un tick e ne ha bisogno.
            time.sleep(0.1) 

    except KeyboardInterrupt:
        print("Spegnimento Brain...")

if __name__ == "__main__":
    main()