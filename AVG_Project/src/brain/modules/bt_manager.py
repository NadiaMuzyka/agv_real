# FILE: src/brain/modules/bt_manager.py (VERSIONE CORRETTA PER REDIS)
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
# (Classi CheckBattery, CheckBatteryLow, StopAndWait rimangono INVARIATE)
# ...

# --- 3. NODI AZIONE SPECIFICI ---
# (Classi WaitForRecharge, PlanMission, GetNextTask, SafetyCheck, PerformAction rimangono INVARIATE)
# ...

# --- LineFollowerAction: Modificata per usare LogicController ---
class LineFollowerAction(py_trees.behaviour.Behaviour):
    def __init__(self, name, blackboard, logic_controller): # RINOMINATO client_body in logic_controller
        super().__init__(name)
        self.bb = blackboard
        self.lc = logic_controller # Nuova istanza del LogicController

    def update(self):
        if not self.bb.current_target: return py_trees.common.Status.FAILURE
        if self.bb.arrived_at_target: 
             self.lc.execute_stop() 
             return py_trees.common.Status.SUCCESS
        
        # Chiama il Logic Controller per calcolare V/W e scrivere su Redis
        self.lc.execute_line_follow(self.bb.line_error) 
        
        return py_trees.common.Status.RUNNING

# --- GoToCharger: Modificata per usare LogicController ---
class GoToCharger(py_trees.behaviour.Behaviour):
    def __init__(self, name, blackboard, logic_controller): # AGGIUNTO logic_controller
        super().__init__(name)
        self.bb = blackboard
        self.lc = logic_controller

    def update(self):
        if self.bb.current_target and self.bb.current_target['id'] == 'CHARGER' and self.bb.arrived_at_target:
            return py_trees.common.Status.SUCCESS

        if not self.bb.current_target or self.bb.current_target['id'] != 'CHARGER':
            print(f"[{self.name}] Imposto destinazione: STAZIONE DI RICARICA")
            self.bb.current_target = {'id': 'CHARGER'}
            self.bb.arrived_at_target = False
        
        self.lc.execute_stop()
        return py_trees.common.Status.RUNNING

# --- 4. COSTRUZIONE ALBERO (CORRETTA) ---
# RINOMINATO client_body in logic_controller e passato ai nodi di movimento

def create_agv_tree(blackboard, logic_controller):
    # ROOT: Selector (Fallback)
    root = py_trees.composites.Selector("RootSelector", memory=False)

    # --- RAMO 1: RICARICA (Priorità Alta) ---
    recharge_sequence = py_trees.composites.Sequence("RechargeSequence", memory=True)
    check_low = CheckBatteryLow("IsBatteryLow", blackboard, threshold=20)
    nav_charger_selector = py_trees.composites.Selector("NavChargerWithWait", memory=False)
    move_sequence = py_trees.composites.Sequence("MoveSequenceToCharger", memory=False)
    move_sequence.add_child(SafetyCheck("SafetyCharger", blackboard))
    # PASSAGGIO CORRETTO: logic_controller
    move_sequence.add_child(GoToCharger("SetChargerTarget", blackboard, logic_controller)) 
    move_sequence.add_child(LineFollowerAction("MoveToCharger", blackboard, logic_controller))
    wait_node = StopAndWait("ObstacleDetectedWait")
    nav_charger_selector.add_children([move_sequence, wait_node])
    wait_charge = WaitForRecharge("ChargingProcess", blackboard)
    recharge_sequence.add_children([check_low, nav_charger_selector, wait_charge])


    # --- RAMO 2: LAVORO NORMALE (Priorità Bassa) ---
    work_sequence = py_trees.composites.Sequence("WorkSequence", memory=True)
    check_bat_ok = CheckBattery("CheckBatOK", blackboard, threshold=20)
    planner = py_trees.composites.Selector("PlanningPhase", memory=False) 
    planner.add_children([PlanMission("GlobalPlanner", blackboard), GetNextTask("TaskDispatcher", blackboard)])
    nav_work_seq = py_trees.composites.Sequence("NavWorkSequence", memory=False)
    nav_work_seq.add_child(SafetyCheck("SafetyWork", blackboard))
    move_logic = py_trees.composites.Selector("MoveLogicWork", memory=False)
    # PASSAGGIO CORRETTO: logic_controller
    move_logic.add_child(LineFollowerAction("LineFollowerWork", blackboard, logic_controller)) 
    nav_work_seq.add_child(move_logic)
    action = PerformAction("LoadUnload", blackboard)
    work_sequence.add_children([check_bat_ok, planner, nav_work_seq, action])

    root.add_children([recharge_sequence, work_sequence])
    return root