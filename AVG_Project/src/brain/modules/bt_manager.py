import py_trees
import time
from py_trees.composites import Sequence, Selector

# --- 1. BLACKBOARD ---
class RobotBlackboard:
    def __init__(self):
        self.battery_level = 100
        self.mission_queue = [] 
        self.current_target = None
        self.person_detected = False
        self.line_error = 0.0
        self.arrived_at_target = False
        self.is_recharging = False

# --- 2. NODI DI CONTROLLO E UTILITY ---

class CheckBattery(py_trees.behaviour.Behaviour):
    """ Restituisce SUCCESS se la batteria è CARICA (> soglia) """
    def __init__(self, name, blackboard, threshold=20):
        super().__init__(name)
        self.bb = blackboard
        self.threshold = threshold

    def update(self):
        if self.bb.battery_level > self.threshold:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE

class CheckBatteryLow(py_trees.behaviour.Behaviour):
    """ Restituisce SUCCESS se la batteria è BASSA (< soglia), attivando la ricarica """
    def __init__(self, name, blackboard, threshold=20):
        super().__init__(name)
        self.bb = blackboard
        self.threshold = threshold

    def update(self):
        # Se stiamo già ricaricando, rimaniamo in questo ramo finché non è al 100%
        if self.bb.is_recharging:
            if self.bb.battery_level >= 100:
                print(f"[{self.name}] Ricarica Completata! Torno al lavoro.")
                self.bb.is_recharging = False
                self.bb.current_target = None 
                self.bb.arrived_at_target = False
                return py_trees.common.Status.FAILURE # Esci dal ramo ricarica
            return py_trees.common.Status.SUCCESS # Continua a ricaricare

        # Se la batteria scende sotto la soglia, attiva la ricarica
        if self.bb.battery_level < self.threshold:
            print(f"[{self.name}] BATTERIA BASSA ({self.bb.battery_level:.1f}%)! Richiesta ricarica.")
            self.bb.is_recharging = True
            return py_trees.common.Status.SUCCESS
        
        return py_trees.common.Status.FAILURE

class StopAndWait(py_trees.behaviour.Behaviour):
    """ Ferma il robot e restituisce RUNNING (Smart Wait) """
    def __init__(self, name):
        super().__init__(name)
    def update(self):
        return py_trees.common.Status.RUNNING

# --- 3. NODI AZIONE SPECIFICI ---

class GoToCharger(py_trees.behaviour.Behaviour):
    """ Imposta il target verso la stazione di ricarica """
    def __init__(self, name, blackboard):
        super().__init__(name)
        self.bb = blackboard

    def update(self):
        if self.bb.current_target and self.bb.current_target['id'] == 'CHARGER' and self.bb.arrived_at_target:
            return py_trees.common.Status.SUCCESS

        if not self.bb.current_target or self.bb.current_target['id'] != 'CHARGER':
            print(f"[{self.name}] Imposto destinazione: STAZIONE DI RICARICA")
            self.bb.current_target = {'id': 'CHARGER'}
            self.bb.arrived_at_target = False
        
        return py_trees.common.Status.RUNNING

class WaitForRecharge(py_trees.behaviour.Behaviour):
    """ Aspetta finché la batteria non si ricarica """
    def __init__(self, name, blackboard):
        super().__init__(name)
        self.bb = blackboard

    def update(self):
        if self.bb.battery_level >= 100:
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.RUNNING

class PlanMission(py_trees.behaviour.Behaviour):
    def __init__(self, name, blackboard):
        super().__init__(name)
        self.bb = blackboard

    def update(self):
        if self.bb.mission_queue: return py_trees.common.Status.FAILURE
        if not self.bb.current_target:
            print(f"[{self.name}] Generazione nuove missioni...")
            raw_tasks = [{'id': 101, 'prio': 10}, {'id': 102, 'prio': 50}, {'id': 103, 'prio': 30}]
            self.bb.mission_queue = sorted(raw_tasks, key=lambda x: x['prio'], reverse=True)
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE

class GetNextTask(py_trees.behaviour.Behaviour):
    def __init__(self, name, blackboard):
        super().__init__(name)
        self.bb = blackboard

    def update(self):
        if self.bb.current_target: return py_trees.common.Status.SUCCESS
        if self.bb.mission_queue:
            self.bb.current_target = self.bb.mission_queue.pop(0)
            self.bb.arrived_at_target = False
            print(f"[{self.name}] Nuova Destinazione: Pallet {self.bb.current_target['id']}")
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE

class SafetyCheck(py_trees.behaviour.Behaviour):
    def __init__(self, name, blackboard):
        super().__init__(name)
        self.bb = blackboard
    def update(self):
        if self.bb.person_detected:
            print(f"[{self.name}] EMERGENZA: Persona rilevata!")
            return py_trees.common.Status.FAILURE
        return py_trees.common.Status.SUCCESS

class LineFollowerAction(py_trees.behaviour.Behaviour):
    def __init__(self, name, blackboard, client_body):
        super().__init__(name)
        self.bb = blackboard
        self.client = client_body

    def update(self):
        if not self.bb.current_target: return py_trees.common.Status.FAILURE
        if self.bb.arrived_at_target: return py_trees.common.Status.SUCCESS
        # Qui invieremmo i comandi al body tramite self.client.send_command(v, w)
        self.client.send_command(0.5, 0.0) # Simula movimento
        return py_trees.common.Status.RUNNING

class PerformAction(py_trees.behaviour.Behaviour):
    def __init__(self, name, blackboard):
        super().__init__(name)
        self.bb = blackboard
        self.timer = 0
    def initialise(self):
        self.timer = 0
        if self.bb.current_target:
            target_name = self.bb.current_target['id']
            print(f"[{self.name}] Eseguo azione su {target_name}...")
    def update(self):
        if not self.bb.current_target: return py_trees.common.Status.FAILURE
        self.timer += 1
        if self.timer < 5: return py_trees.common.Status.RUNNING
        
        print(f"[{self.name}] Azione completata.")
        if self.bb.current_target['id'] != 'CHARGER':
            self.bb.current_target = None 
            self.bb.arrived_at_target = False
        return py_trees.common.Status.SUCCESS


# --- 4. COSTRUZIONE ALBERO (CORRETTA) ---

def create_agv_tree(blackboard, client_body):
    # ROOT: Selector (Fallback)
    root = py_trees.composites.Selector("RootSelector", memory=False)

    # --- RAMO 1: RICARICA (Priorità Alta) ---
    recharge_sequence = py_trees.composites.Sequence("RechargeSequence", memory=True)
    
    check_low = CheckBatteryLow("IsBatteryLow", blackboard, threshold=20)
    
    # Navigazione Ricarica
    nav_charger_selector = py_trees.composites.Selector("NavChargerWithWait", memory=False)
    
    # A. Prova a muoverti
    move_sequence = py_trees.composites.Sequence("MoveSequenceToCharger", memory=False)
    move_sequence.add_child(SafetyCheck("SafetyCharger", blackboard))
    move_sequence.add_child(GoToCharger("SetChargerTarget", blackboard))
    move_sequence.add_child(LineFollowerAction("MoveToCharger", blackboard, client_body))
    
    # B. Se bloccato, aspetta
    wait_node = StopAndWait("ObstacleDetectedWait")
    
    nav_charger_selector.add_children([move_sequence, wait_node])
    
    wait_charge = WaitForRecharge("ChargingProcess", blackboard)

    recharge_sequence.add_children([check_low, nav_charger_selector, wait_charge])


    # --- RAMO 2: LAVORO NORMALE (Priorità Bassa) ---
    work_sequence = py_trees.composites.Sequence("WorkSequence", memory=True)

    check_bat_ok = CheckBattery("CheckBatOK", blackboard, threshold=20)

    planner = py_trees.composites.Selector("PlanningPhase", memory=False) 
    planner.add_children([PlanMission("GlobalPlanner", blackboard), GetNextTask("TaskDispatcher", blackboard)])

    # --- FIX QUI: Usiamo un nome e una variabile diversa per la sequenza di lavoro ---
    nav_work_seq = py_trees.composites.Sequence("NavWorkSequence", memory=False)
    nav_work_seq.add_child(SafetyCheck("SafetyWork", blackboard))
    
    move_logic = py_trees.composites.Selector("MoveLogicWork", memory=False)
    move_logic.add_child(LineFollowerAction("LineFollowerWork", blackboard, client_body))
    
    nav_work_seq.add_child(move_logic)
    # --- FINE FIX ---

    action = PerformAction("LoadUnload", blackboard)

    work_sequence.add_children([check_bat_ok, planner, nav_work_seq, action])

    # ROOT
    root.add_children([recharge_sequence, work_sequence])
    
    return root