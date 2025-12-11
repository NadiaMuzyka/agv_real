# FILE: src/brain/main_brain.py (VERSIONE CORRETTA)
import time
import sys
import os
import random
import py_trees

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.bt_manager import create_agv_tree, RobotBlackboard
from modules.redis_interface import RedisInterface 
from modules.logic_controller import LogicController 

def main():
    print("🧠 Avvio BRAIN. Integrazione Logic Controller su Redis Message Broker...")
    
    # 1. Connessione a Redis
    redis_manager = RedisInterface() 
    if not redis_manager.db:
        print("[BRAIN] Errore critico: Uscita per mancata connessione a Redis.")
        return 
        
    blackboard = RobotBlackboard()
    # 2. Connettiamo il Logic Controller a Redis
    logic_controller = LogicController(redis_manager) 
    
    # 3. Inizializzazione Behavior Tree: Passiamo il Logic Controller
    behavior_tree = create_agv_tree(blackboard, logic_controller) 
    tree_executor = py_trees.trees.BehaviourTree(behavior_tree)
    tree_executor.setup(timeout=15) 

    SENSORS_KEY = "agv_sensors"

    try:
        while True:
            # --- LETTURA SENSORI REALI ---
            sensor_data = redis_manager.get_sensor_data(SENSORS_KEY)
            if sensor_data:
                blackboard.emergency_state = sensor_data.get("emergency", False)
                if blackboard.emergency_state:
                    print(f"[BRAIN] 🚨 RILEVATA EMERGENZA DA BODY! (Bumper: {sensor_data.get('bumper')})")

            # --- AGGIORNAMENTO SIMULATO (SOLO PER IL TEST) ---
            # Diamo al BT dati sufficienti per iniziare a lavorare e generare un comando V/W
            blackboard.battery_level = 90.0 # Batteria OK
            blackboard.person_detected = False
            blackboard.line_error = 0.1 # Simula un errore di linea per innescare il LineFollower
            
            # Placeholder per forzare un target iniziale (per iniziare il ramo WorkSequence)
            if not blackboard.current_target and not blackboard.mission_queue:
                # Questo innesca PlanMission e GetNextTask
                blackboard.current_target = {'id': 'HOME', 'prio': 100} 
            
            # --- 4. ESEGUI BT ---
            tree_executor.tick()
            
            # Il LogicController scrive su Redis (Message Broker) quando chiamato dal BT
            
            time.sleep(0.1) 

    except KeyboardInterrupt:
        print("Spegnimento Brain...")

if __name__ == "__main__":
    main()