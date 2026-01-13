import py_trees
from py_trees.common import Status

# root element
root = py_trees.composites.Selector("Root Selector")

# child elements
sequencePersona = py_trees.composites.Sequence("Sicurezza Persona")

sequenceEnergia = py_trees.composites.Sequence("Gestione Energia")

selectorMissione = py_trees.composites.Selector("Gestione Missione")

sequenceMission = py_trees.composites.Sequence("Missione Conclusa")

sequencePiano = py_trees.composites.Sequence("Generazione Piano")

sequenceStep = py_trees.composites.Sequence("Esecuzione Step")

sequenceGrafo = py_trees.composites.Sequence("Navigazione Grafo")

selectorNodo = py_trees.composites.Selector("Operazione Nodo")

sequenceRitiro = py_trees.composites.Sequence("Ritiro")

sequenceConsegna = py_trees.composites.Sequence("Consegna")

class ControllaPersona(py_trees.behaviours.Behaviour):
    def __init__(self):
        super(ControllaPersona, self).__init__(name="Persona Rilevata")
    
    def setup(self):
        # todo implementare yolo con la rilevazione persona (collegamento al nodo)
        print("Setup ControllaPersona")
        return True

    def initialize(self):
        pass

    def update(self):
        return Status.SUCCESS  # Placeholder for actual detection logic
    
class Stopmotori(py_trees.behaviours.Behaviour):
    def __init__(self):
        super(Stopmotori, self).__init__(name="Stop Motori")
    
    def setup(self):
        print("Setup Stopmotori")
        return True

    def initialize(self):
        pass

    def update(self):
        print("Motori fermati")
        return Status.SUCCESS  # Placeholder for actual motor stop logic
    
