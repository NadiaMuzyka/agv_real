# FILE: src/brain/modules/bt_manager.py (Versione Test Probabilistico)

import py_trees
import time
from py_trees.composites import Sequence, Selector, Parallel
import random

# --- CLASSE PROBABILISTICA (PER IL TEST DEL PROFESSORE) ---
class ProbabilisticCheck(py_trees.behaviour.Behaviour):
    """ Simula un Check Condizionale basato su probabilità. """
    def __init__(self, name, probability_success=0.5):
        super().__init__(name)
        self.probability = probability_success

    def update(self):
        rand_val = random.random()
        
        if rand_val < self.probability:
            print(f"[{self.name}] --> SUCCESS (Prob: {self.probability:.2f}, Risultato: {rand_val:.2f})")
            return py_trees.common.Status.SUCCESS
        else:
            print(f"[{self.name}] --> FAILURE (Prob: {self.probability:.2f}, Risultato: {rand_val:.2f})")
            return py_trees.common.Status.FAILURE
            
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
        self.emergency_state = False

# --- 2. NODI DI CONTROLLO E UTILITY ---
# NOTA: I Check originali sono qui sotto, ma vengono SOSTITUITI nel create_agv_tree dai ProbabilisticCheck.

class StopAction(py_trees.behaviour.Behaviour):
    """ Invia il comando di STOP ai cingoli (tramite Logic Controller). """
    def __init__(self, name, logic_controller):
        super().__init__(name)
        self.lc = logic_controller

    def update(self):
        self.lc.execute_stop()
        # Non deve RUNNING o SUCCESS, altrimenti l'albero scende.
        # Restituiamo RUNNING per mantenere l'emergenza attiva.
        return py_trees.common.Status.RUNNING 

class StopAndWait(py_trees.behaviour.Behaviour):
    """ Ferma il robot e ritorna RUNNING. (Usato per rami bloccanti) """
    def __init__(self, name):
        super().__init__(name)
    def update(self):
        return py_trees.common.Status.RUNNING

class GoToCharger(py_trees.behaviour.Behaviour):
    """ Imposta il target verso la stazione di ricarica. """
    def __init__(self, name, blackboard, logic_controller):
        super().__init__(name)
        self.bb = blackboard
        self.lc = logic_controller

    def update(self):
        if self.bb.current_target and self.bb.current_target.get('id') == 'CHARGER' and self.bb.arrived_at_target:
            return py_trees.common.Status.SUCCESS

        if not self.bb.current_target or self.bb.current_target.get('id') != 'CHARGER':
            print(f"[{self.name}] Imposto destinazione: STAZIONE DI RICARICA")
            self.bb.current_target = {'id': 'CHARGER'}
            self.bb.arrived_at_target = False
        
        self.lc.execute_stop() # Invia un primo stop di sicurezza
        return py_trees.common.Status.RUNNING

class WaitForRecharge(py_trees.behaviour.Behaviour):
    """ Aspetta finché la batteria non si ricarica al 100% (Da implementare con il Battery Sensor). """
    def __init__(self, name, blackboard):
        super().__init__(name)
        self.bb = blackboard

    def update(self):
        # NOTA: Nel test probabilistico questo ritorna sempre RUNNING, 
        # ma in un'implementazione reale leggerebbe self.bb.battery_level.
        # Per il test, lo lasciamo in RUNNING.
        if self.bb.battery_level >= 100:
            return py_trees.common.Status.SUCCESS
        print(f"[{self.name}] In attesa di ricarica ({self.bb.battery_level}%)")
        return py_trees.common.Status.RUNNING

# --- 3. NODI AZIONE MISSIONE ---

class GetNextTask(py_trees.behaviour.Behaviour):
    """ Preleva la prossima missione dalla coda e la imposta come target corrente. """
    def __init__(self, name, blackboard):
        super().__init__(name)
        self.bb = blackboard

    def update(self):
        if self.bb.current_target: return py_trees.common.Status.SUCCESS
        if self.bb.mission_queue:
            # Popola la missione
            self.bb.current_target = self.bb.mission_queue.pop(0)
            self.bb.arrived_at_target = False
            print(f"[{self.name}] Nuova Destinazione: ID {self.bb.current_target.get('id')}")
            return py_trees.common.Status.SUCCESS
        return py_trees.common.Status.FAILURE # Coda vuota

class LineFollowerAction(py_trees.behaviour.Behaviour):
    """ Esegue il movimento e il Line Following (finché non si arriva a destinazione). """
    def __init__(self, name, blackboard, logic_controller):
        super().__init__(name)
        self.bb = blackboard
        self.lc = logic_controller

    def update(self):
        if not self.bb.current_target: return py_trees.common.Status.FAILURE
        
        # 1. Se è arrivato (condizione letta da April Tag o GPS simulato)
        if self.bb.arrived_at_target: 
             self.lc.execute_stop() 
             return py_trees.common.Status.SUCCESS
        
        # 2. Continua a muoversi (Line Following)
        # Il Body si occuperà dell'override Bumper/Sicurezza.
        self.lc.execute_line_follow(self.bb.line_error) 
        
        return py_trees.common.Status.RUNNING # Non ha ancora finito

class PerformAction(py_trees.behaviour.Behaviour):
    """ Esegue l'azione di Pick-up/Drop al target. """
    def __init__(self, name, blackboard):
        super().__init__(name)
        self.bb = blackboard
        self.timer = 0
    def initialise(self):
        self.timer = 0
        if self.bb.current_target:
            target_name = self.bb.current_target.get('id')
            print(f"[{self.name}] Eseguo azione su {target_name}...")
    def update(self):
        if not self.bb.current_target: return py_trees.common.Status.FAILURE
        
        self.timer += 1
        if self.timer < 5: return py_trees.common.Status.RUNNING # Simula tempo di attuazione
        
        print(f"[{self.name}] Azione completata su {self.bb.current_target.get('id')}.")
        
        # Resetta lo stato solo se non era la ricarica
        if self.bb.current_target.get('id') != 'CHARGER':
            self.bb.current_target = None 
            self.bb.arrived_at_target = False
            
        return py_trees.common.Status.SUCCESS


# --- 4. COSTRUZIONE ALBERO ---
def create_agv_tree(blackboard, logic_controller):
    
    # ROOT: Selector (Fallback) - Priorità da Sinistra a Destra
    root = py_trees.composites.Selector("RootSelector", memory=False)
    # 1. Sicurezza (Massima Priorità)
    # 2. Gestione Energetica
    # 3. Missione/Lavoro (Minima Priorità)

    # --- RAMO 0: SICUREZZA E PERSONE (GESTITO DAL BRAIN) ---
    # La gestione del Bumper è nel Body, ma il BT deve gestire il rallentamento per le persone (YOLO)
    safety_sequence = py_trees.composites.Sequence("Safety&PeopleSequence", memory=False)
    
    # TEST: Rilevamento Persone (Probabilità 15%)
    # Questo Check può includere la logica YOLO per la presenza di persone
    check_person = ProbabilisticCheck("PersonDetected_TEST", probability_success=0.15) 
    
    # Azione: Rallentamento/Stop se persone (Manteniamo RUNNING per l'azione)
    slow_down_action = StopAndWait("SafetySlowDown_RUNNING")
    
    safety_sequence.add_children([check_person, slow_down_action])

    # --- RAMO 1: RICARICA (Priorità Alta) ---
    recharge_sequence = py_trees.composites.Sequence("RechargeSequence", memory=True)
    
    # TEST: Batteria Bassa (Probabilità 30%)
    check_low = ProbabilisticCheck("IsBatteryLow_TEST", probability_success=0.30)
    
    nav_charger_selector = py_trees.composites.Selector("NavChargerSelector", memory=False)
    
    # Sequenza: Imposta target -> Muoviti -> Raggiungi (LineFollowerAction)
    move_sequence = py_trees.composites.Sequence("MoveToCharger", memory=False)
    move_sequence.add_child(GoToCharger("SetChargerTarget", blackboard, logic_controller))
    move_sequence.add_child(LineFollowerAction("MoveToCharger", blackboard, logic_controller))
    
    # Alternativa se bloccato (per ora semplice Stop)
    nav_charger_selector.add_children([move_sequence, StopAndWait("ObstacleWaitCharger")])
    
    wait_charge = WaitForRecharge("ChargingProcess", blackboard) # Ritorna RUNNING finché non carica

    recharge_sequence.add_children([check_low, nav_charger_selector, wait_charge])


    # --- RAMO 2: LAVORO NORMALE (Priorità Bassa) ---
    work_sequence = py_trees.composites.Sequence("WorkSequence", memory=True)

    # TEST: Batteria OK (Probabilità 70% di continuare)
    check_bat_ok = ProbabilisticCheck("CheckBatOK_TEST", probability_success=0.70)

    # Pianificazione: Se non ho un target attuale, pianifica o prendine uno dalla coda
    planner = py_trees.composites.Selector("PlanningPhase", memory=False) 
    
    # TEST: Probabilità di dover pianificare (es. Coda missioni vuota)
    plan_mission_test = ProbabilisticCheck("PlanMission_TEST", probability_success=0.10) 
    
    # MISSIONE DI ESEMPIO INIZIALE (per avviare la simulazione)
    if not blackboard.mission_queue:
        raw_tasks = [{'id': 101, 'prio': 10}, {'id': 102, 'prio': 50}]
        blackboard.mission_queue = sorted(raw_tasks, key=lambda x: x['prio'], reverse=True)
    
    planner.add_children([plan_mission_test, GetNextTask("TaskDispatcher", blackboard)])

    # Navigazione Lavoro
    nav_work_seq = py_trees.composites.Sequence("NavWorkSequence", memory=False)
    
    # Il Safety Check qui garantisce che se non ci sono persone, si muove
    # TEST: Sicurezza (Probabilità 95% che sia sicuro muoversi)
    safety_move_test = ProbabilisticCheck("SafetyMove_TEST", probability_success=0.95)
    nav_work_seq.add_child(safety_move_test)
    
    # Nodo di movimento principale (ritorna RUNNING finché non arriva)
    nav_work_seq.add_child(LineFollowerAction("LineFollowerWork", blackboard, logic_controller))

    # Azione al Target (Pick-up/Drop)
    action = PerformAction("LoadUnload", blackboard)

    work_sequence.add_children([check_bat_ok, planner, nav_work_seq, action])

    # ROOT: Assemblaggio finale
    root.add_children([safety_sequence, recharge_sequence, work_sequence])
    
    return root