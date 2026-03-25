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
    
    def setup(self):
        print("Setup ControlloBatteria")
        return True

    def initialise(self):
        pass

    def update(self):
        # Restituisce SUCCESS se batteria < 20%, altrimenti FAILURE
        return Status.SUCCESS 

class CalcolaPercorsoRicarica(py_trees.behaviour.Behaviour):
    """
    Calcola il percorso ottimale verso la stazione di ricarica più vicina.
    """
    def __init__(self):
        super(CalcolaPercorsoRicarica, self).__init__(name="Calcola Percorso Ricarica")
    
    def setup(self):
        print("Setup CalcolaPercorsoRicarica")
        return True

    def initialise(self):
        pass

    def update(self):
        return Status.SUCCESS

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