import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 4. NODI OPERATIVI (RITIRO E CONSEGNA)
# =============================================================================

class ENodoDiPrelievo(py_trees.behaviour.Behaviour):
    """
    Condizione: Verifica se il nodo attuale è un punto di ritiro (Pickup).
    """
    def __init__(self):
        super(ENodoDiPrelievo, self).__init__(name="È Nodo di Prelievo")
    
    def setup(self):
        print("Setup ENodoDiPrelievo")
        return True

    def initialise(self):
        pass

    def update(self):
        return Status.SUCCESS

class EseguiPrelievo(py_trees.behaviour.Behaviour):
    """
    Azione: Attiva gli attuatori (es. muletto) per prelevare il pallet.
    """
    def __init__(self):
        super(EseguiPrelievo, self).__init__(name="Esegui Prelievo")
    
    def setup(self):
        print("Setup EseguiPrelievo")
        return True

    def initialise(self):
        pass

    def update(self):
        return Status.SUCCESS

class ENodoDiConsegna(py_trees.behaviour.Behaviour):
    """
    Condizione: Verifica se il nodo attuale è un punto di consegna (Delivery).
    """
    def __init__(self):
        super(ENodoDiConsegna, self).__init__(name="È Nodo di Consegna")
    
    def setup(self):
        print("Setup ENodoDiConsegna")
        return True

    def initialise(self):
        pass

    def update(self):
        return Status.SUCCESS

class EseguiConsegna(py_trees.behaviour.Behaviour):
    """
    Azione: Attiva gli attuatori per depositare il pallet.
    """
    def __init__(self):
        super(EseguiConsegna, self).__init__(name="Esegui Consegna")
    
    def setup(self):
        print("Setup EseguiConsegna")
        return True

    def initialise(self):
        pass

    def update(self):
        return Status.SUCCESS