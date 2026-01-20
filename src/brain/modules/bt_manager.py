import py_trees
from py_trees.common import Status

# =============================================================================
# 1. NODI DI SICUREZZA
# =============================================================================

class ControllaPersona(py_trees.behaviour.Behaviour):
    """
    Controlla se ci sono persone o ostacoli nel raggio di azione del robot.
    Restituisce SUCCESS se viene rilevata una persona.
    """
    def __init__(self):
        super(ControllaPersona, self).__init__(name="Persona Rilevata")
    
    def setup(self):
        # TODO: implementare YOLO o sensori per la rilevazione persona
        print("Setup ControllaPersona")
        return True

    def initialize(self):
        pass

    def update(self):
        # Qui andrebbe la logica reale di rilevamento
        return Status.SUCCESS 

class StopMotori(py_trees.behaviour.Behaviour):
    """
    Invia il comando di arresto immediato ai motori.
    """
    def __init__(self):
        super(StopMotori, self).__init__(name="Stop Motori")
    
    def setup(self):
        print("Setup StopMotori")
        return True

    def initialize(self):
        pass

    def update(self):
        print("Motori fermati")
        # Restituisce SUCCESS dopo aver inviato il comando di stop
        return Status.SUCCESS 

class Aspetta(py_trees.behaviour.Behaviour):
    """
    Esegue un'attesa (es. 5 secondi) prima di riprendere.
    """
    def __init__(self):
        super(Aspetta, self).__init__(name="Aspetta")
    
    def setup(self):
        print("Setup Aspetta")
        return True

    def initialize(self):
        pass

    def update(self):
        # Qui andrebbe la logica di timer
        return Status.SUCCESS 

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

    def initialize(self):
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

    def initialize(self):
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

    def initialize(self):
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

    def initialize(self):
        pass

    def update(self):
        return Status.SUCCESS

# =============================================================================
# 3. NODI DI GESTIONE MISSIONE
# =============================================================================

class ListaPalletVuota(py_trees.behaviour.Behaviour):
    """
    Condizione: Verifica se la lista dei pallet da processare è vuota.
    Restituisce SUCCESS se non ci sono più lavori da fare.
    """
    def __init__(self):
        super(ListaPalletVuota, self).__init__(name="Lista Pallet Vuota")
    
    def setup(self):
        print("Setup ListaPalletVuota")
        return True

    def initialize(self):
        pass

    def update(self):
        return Status.SUCCESS 

class PianoNonGenerato(py_trees.behaviour.Behaviour):
    """
    Condizione: Verifica se manca un piano di navigazione per i pallet attuali.
    Restituisce SUCCESS se bisogna generare un nuovo piano.
    """
    def __init__(self):
        super(PianoNonGenerato, self).__init__(name="Piano Non Generato")
    
    def setup(self):
        print("Setup PianoNonGenerato")
        return True

    def initialize(self):
        pass

    def update(self):
        return Status.SUCCESS 

class RiceviListaPallet(py_trees.behaviour.Behaviour):
    """
    Azione: Riceve la lista dei task e le priorità dal sistema centrale.
    """
    def __init__(self):
        super(RiceviListaPallet, self).__init__(name="Ricevi Lista Pallet")
    
    def setup(self):
        print("Setup RiceviListaPallet")
        return True

    def initialize(self):
        pass

    def update(self):
        return Status.SUCCESS

class GeneraPianoOttimale(py_trees.behaviour.Behaviour):
    """
    Azione: Elabora l'ordine ottimale di visita dei nodi (algoritmo di scheduling).
    """
    def __init__(self):
        super(GeneraPianoOttimale, self).__init__(name="Genera Piano Ottimale")
    
    def setup(self):
        print("Setup GeneraPianoOttimale")
        return True

    def initialize(self):
        pass

    def update(self):
        return Status.SUCCESS

class EstraiProssimoNodo(py_trees.behaviour.Behaviour):
    """
    Azione: Estrae il prossimo nodo target dalla lista pianificata.
    """
    def __init__(self):
        super(EstraiProssimoNodo, self).__init__(name="Estrai Prossimo Nodo")
    
    def setup(self):
        print("Setup EstraiProssimoNodo")
        return True

    def initialize(self):
        pass

    def update(self):
        return Status.SUCCESS

class NavigaVersoNodo(py_trees.behaviour.Behaviour):
    """
    Azione: Esegue la navigazione (Line Follower / Path Planning) verso il nodo corrente.
    """
    def __init__(self):
        super(NavigaVersoNodo, self).__init__(name="Naviga Verso Nodo")
    
    def setup(self):
        print("Setup NavigaVersoNodo")
        return True

    def initialize(self):
        pass

    def update(self):
        return Status.SUCCESS

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

    def initialize(self):
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

    def initialize(self):
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

    def initialize(self):
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

    def initialize(self):
        pass

    def update(self):
        return Status.SUCCESS

# =============================================================================
# COSTRUZIONE DELL'ALBERO DI COMPORTAMENTO
# =============================================================================

def crea_albero_agv():
    """
    Costruisce e restituisce la struttura completa del Behavior Tree.
    """
    # Elemento Root: Selettore Principale (Priorità: Sicurezza -> Energia -> Missione)
    root = py_trees.composites.Selector("Selettore Principale")

    # --- RAMO 1: SICUREZZA PERSONA ---
    # Sequenza: Se c'è una persona -> Ferma -> Aspetta
    sequenza_sicurezza = py_trees.composites.Sequence("Sicurezza Persona")
    controllo_persona = ControllaPersona()
    stop_motori = StopMotori()
    aspetta = Aspetta()
    sequenza_sicurezza.add_children([controllo_persona, stop_motori, aspetta])

    # --- RAMO 2: GESTIONE ENERGIA ---
    # Sequenza: Se batteria bassa -> Calcola Ricarica -> Vai -> Ricarica
    sequenza_energia = py_trees.composites.Sequence("Gestione Energia")
    controllo_batteria = ControlloBatteria()
    calcola_percorso_ricarica = CalcolaPercorsoRicarica()
    vai_a_ricarica = VaiAStazioneRicarica()
    ricarica_batteria = RicaricaBatteria()
    sequenza_energia.add_children([controllo_batteria, calcola_percorso_ricarica, vai_a_ricarica, ricarica_batteria])

    # --- RAMO 3: GESTIONE MISSIONE ---
    # Selettore: Sceglie tra Missione Finita, Pianificazione o Esecuzione
    selettore_missione = py_trees.composites.Selector("Gestione Missione")

    # 3.1: Missione Conclusa (Se lista vuota -> Torna alla base)
    sequenza_conclusione = py_trees.composites.Sequence("Missione Conclusa")
    lista_vuota = ListaPalletVuota()
    # Usiamo le stesse classi di ricarica per tornare alla base a fine turno
    calcola_rientro = CalcolaPercorsoRicarica() 
    vai_a_base = VaiAStazioneRicarica()
    sequenza_conclusione.add_children([lista_vuota, calcola_rientro, vai_a_base])

    # 3.2: Generazione Piano (Se non c'è piano -> Crea)
    sequenza_pianificazione = py_trees.composites.Sequence("Generazione Piano")
    piano_non_generato = PianoNonGenerato()
    ricevi_lista = RiceviListaPallet()
    genera_piano = GeneraPianoOttimale()
    sequenza_pianificazione.add_children([piano_non_generato, ricevi_lista, genera_piano])

    # 3.3: Esecuzione Step (Navigazione + Azione)
    sequenza_esecuzione = py_trees.composites.Sequence("Esecuzione Step")

    # 3.3.1: Navigazione Grafo
    sequenza_navigazione = py_trees.composites.Sequence("Navigazione Grafo")
    estrai_nodo = EstraiProssimoNodo()
    naviga_nodo = NavigaVersoNodo()
    sequenza_navigazione.add_children([estrai_nodo, naviga_nodo])

    # 3.3.2: Operazione sul Nodo (Ritiro O Consegna)
    selettore_operazione = py_trees.composites.Selector("Operazione Nodo")

    # Ramo Ritiro
    sequenza_ritiro = py_trees.composites.Sequence("Ritiro")
    e_prelievo = ENodoDiPrelievo()
    esegui_prelievo = EseguiPrelievo()
    sequenza_ritiro.add_children([e_prelievo, esegui_prelievo])

    # Ramo Consegna
    sequenza_consegna = py_trees.composites.Sequence("Consegna")
    e_consegna = ENodoDiConsegna()
    esegui_consegna = EseguiConsegna()
    sequenza_consegna.add_children([e_consegna, esegui_consegna])

    # Assemblaggio sotto-alberi
    selettore_operazione.add_children([sequenza_ritiro, sequenza_consegna])
    sequenza_esecuzione.add_children([sequenza_navigazione, selettore_operazione])

    # Assemblaggio finale Missione
    selettore_missione.add_children([sequenza_conclusione, sequenza_pianificazione, sequenza_esecuzione])

    # Assemblaggio Root
    root.add_children([sequenza_sicurezza, sequenza_energia, selettore_missione])

    return root