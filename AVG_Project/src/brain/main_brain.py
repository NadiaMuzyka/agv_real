import time
import sys
import os
import random
import py_trees

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
from modules.bt_manager import create_agv_tree, RobotBlackboard

class BodyClient:
    def __init__(self):
        self.battery = 100.0
        self.steps = 0
        self.is_moving = False
        self.current_location = "HOME" # Dove si trova il robot fisicamente

    def send_command(self, v, w):
        self.is_moving = (v > 0 or w > 0)

    def get_sensors(self, target_id):
        self.steps += 1
        
        # --- LOGICA ARRIVO SIMULATA ---
        arrived = False
        if self.is_moving:
            # Arriviamo ogni 50 step per fare i test più veloci
            if self.steps % 50 == 0:
                arrived = True
                self.current_location = target_id # Aggiorna la posizione
                print(f"[SIMULATOR] -> Arrivato a: {target_id} (Step {self.steps})")
        
        # --- LOGICA BATTERIA SIMULATA ---
        # Se siamo alla stazione di ricarica, la batteria sale
        if self.current_location == 'CHARGER':
            self.battery += 5.0 # Ricarica veloce
            if self.battery > 100: self.battery = 100
            # print(f"[SIMULATOR] Ricarica in corso... {self.battery}%")
        else:
            # Altrimenti scende (consumo)
            self.battery -= 1.5 # Consumo più veloce per testare
            if self.battery < 0: self.battery = 0

        # --- OSTACOLI ---
        person = False
        if 80 < self.steps < 90: person = True

        return {
            "battery": self.battery,
            "person": person,
            "line_error": random.uniform(-0.1, 0.1),
            "arrived": arrived
        }

def main():
    print("Avvio BRAIN con Logica Ricarica...")
    blackboard = RobotBlackboard()
    client = BodyClient()
    
    behavior_tree = create_agv_tree(blackboard, client)
    tree_executor = py_trees.trees.BehaviourTree(behavior_tree)
    tree_executor.setup(timeout=15)

    try:
        while True:
            # Passiamo l'ID del target attuale al simulatore per sapere dove stiamo andando
            target_id = blackboard.current_target['id'] if blackboard.current_target else "IDLE"
            
            sensors = client.get_sensors(target_id)
            
            blackboard.battery_level = sensors["battery"]
            blackboard.person_detected = sensors["person"]
            blackboard.line_error = sensors["line_error"]
            
            if sensors["arrived"] and blackboard.current_target:
                 blackboard.arrived_at_target = True

            tree_executor.tick()
            
            # Debug stato
            status = "WORKING"
            if blackboard.is_recharging: status = "RECHARGING"
            if blackboard.person_detected: status = "EMERGENCY"
            
            # print(f"[{status}] Bat: {int(blackboard.battery_level)}% | Target: {target_id}")
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("Spegnimento...")

if __name__ == "__main__":
    main()