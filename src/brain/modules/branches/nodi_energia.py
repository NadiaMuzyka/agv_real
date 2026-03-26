import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 2. NODI DI GESTIONE ENERGIA
# =============================================================================

class ControlloBatteria(py_trees.behaviour.Behaviour):
    """
    Verifica il livello della batteria.
    Restituisce SUCCESS se la batteria è CRITICA (< 20%), attivando la sequenza di ricarica.
    """
    def __init__(self):
        super(ControlloBatteria, self).__init__(name="Controllo Batteria < 20%")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup ControlloBatteria")
        return True

    def initialise(self):
        pass

    def update(self):
        # Controlla se il livello della batteria è inferiore al 20%
        if self.blackboard.battery_level < 20.0:
            print(f"[ControlloBatteria] Batteria critica: {self.blackboard.battery_level:.2f}%")
            return Status.SUCCESS
        else:
                return Status.FAILURE

class CalcolaPercorsoRicarica(py_trees.behaviour.Behaviour):
    """
    Calcola il percorso ottimale verso la stazione di ricarica più vicina.
    """
    def __init__(self, nodo_ricarica="ER"):
        super(CalcolaPercorsoRicarica, self).__init__(name="Calcola Percorso Ricarica")
        self.nodo_ricarica = nodo_ricarica

        # Blackboard per leggere la posizione attuale e scrivere il percorso da seguire
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)

    def setup(self):
        print("Setup CalcolaPercorsoRicarica")
        return True

    def initialise(self):
        pass

    def update(self):
        LogicController = self.blackboard.logic_controller
        # Legge la posizione attuale dalla blackboard
        try:
            nodo_partenza = self.blackboard.current_position
        except KeyError:
            print("[CalcolaPercorsoRicarica] Errore: Posizione 'current_position' non trovata sulla blackboard.")
            return Status.FAILURE
        
        esito = LogicController.find_path(nodo_partenza, self.nodo_ricarica)
        match esito:
            case True:
                return Status.SUCCESS
            case False:
                return Status.FAILURE


class VaiAStazioneRicarica(py_trees.behaviour.Behaviour):
    """
    Gestisce la navigazione fisica verso la stazione di ricarica.
    """
    def __init__(self):
        super(VaiAStazioneRicarica, self).__init__(name="Vai A Stazione Ricarica")
    
    def setup(self):
        print("Setup VaiAStazioneRicarica")
        return True

    def initialise(self):
        pass

    def update(self):
        return Status.SUCCESS

class RicaricaBatteria(py_trees.behaviour.Behaviour):
    """
    Gestisce il processo di ricarica (attesa fino al 100%).
    """
    def __init__(self):
        super(RicaricaBatteria, self).__init__(name="Ricarica Batteria")
    
    def setup(self):
        print("Setup RicaricaBatteria")
        return True

    def initialise(self):
        pass

    def update(self):
        return Status.SUCCESS
    






class VaiAStazioneRicarica(py_trees.behaviour.Behaviour):
    """
    Gestisce la navigazione simulata verso la stazione di ricarica attraversando i nodi.
    """
    def __init__(self):
        super(VaiAStazioneRicarica, self).__init__(name="Vai A Stazione Ricarica")
        
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        # Legge il percorso calcolato dal nodo precedente
        self.blackboard.register_key(key="target_path", access=py_trees.common.Access.READ)
        # Aggiorna la posizione attuale man mano che si muove
        self.blackboard.register_key(key="current_node", access=py_trees.common.Access.WRITE)
        
        self.percorso_rimanente = []
    
    def setup(self):
        print("Setup VaiAStazioneRicarica")
        return True

    def initialise(self):
        # Carica il percorso dalla blackboard quando il nodo viene attivato
        try:
            self.percorso_rimanente = list(self.blackboard.target_path)
            print(f"[{self.name}] Inizio viaggio lungo il percorso: {self.percorso_rimanente}")
        except KeyError:
            print(f"[{self.name}] Errore: 'target_path' mancante.")
            self.percorso_rimanente = []

    def update(self):
        if not self.percorso_rimanente:
            return Status.FAILURE

        # Estrae il prossimo nodo da raggiungere
        nodo_raggiunto = self.percorso_rimanente.pop(0)
        self.blackboard.current_node = nodo_raggiunto
        print(f"[{self.name}] In movimento... Raggiunto nodo: {nodo_raggiunto}")

        # Se ci sono ancora nodi, il viaggio è "IN CORSO"
        if len(self.percorso_rimanente) > 0:
            return Status.RUNNING
        else:
            # Siamo arrivati a destinazione!
            print(f"[{self.name}] Destinazione raggiunta!")
            return Status.SUCCESS


class RicaricaBatteria(py_trees.behaviour.Behaviour):
    """
    Gestisce il processo di ricarica incrementando il livello della batteria
    fino al raggiungimento del 100%.
    """
    def __init__(self, step_ricarica=25.0):
        super(RicaricaBatteria, self).__init__(name="Ricarica Batteria")
        self.step_ricarica = step_ricarica # Quanta batteria recupera per ogni "tick"
        
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        # Legge E SCRIVE il livello della batteria per ricaricarla
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.WRITE)
    
    def setup(self):
        print("Setup RicaricaBatteria")
        return True

    def initialise(self):
        print(f"[{self.name}] Inizio ricarica della batteria...")

    def update(self):
        try:
            # Controlla il livello attuale
            if self.blackboard.battery_level < 100.0:
                # Incrementa la batteria
                self.blackboard.battery_level += self.step_ricarica
                
                # Assicuriamoci che non superi il 100%
                if self.blackboard.battery_level >= 100.0:
                    self.blackboard.battery_level = 100.0
                    print(f"[{self.name}] Ricarica completata: 100%.")
                    return Status.SUCCESS
                else:
                    print(f"[{self.name}] In ricarica... livello attuale: {self.blackboard.battery_level}%")
                    return Status.RUNNING
            else:
                return Status.SUCCESS
        except KeyError:
            print(f"[{self.name}] Errore: 'battery_level' non trovato.")
            return Status.FAILURE