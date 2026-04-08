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
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.READ)
        #flag per indicare che siamo sotto il 20% e dobbiamo ricaricare,
        #questo serve per evitare di rientrare in questa condizione ad ogni tick del BT
        #verrà settato a True quando la batteria scende sotto il 20% e a False quando la ricarica è completa
        self.blackboard.register_key(key="is_charging", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup ControlloBatteria")
        return True

    def initialise(self):
        pass

    def update(self):
        livello_batteria = self.blackboard.battery_level
        # Se la batteria è sotto il 20% attivo "Modalità Ricarica"
        if livello_batteria < 20:
            self.blackboard.logic_controller.set_energy_mode("CHARGE_MODE")
        if livello_batteria >= 100.0:
            self.blackboard.logic_controller.set_energy_mode("NORMAL_MODE")

        # Restituisco SUCCESS se siamo in modalità ricarica, altrimenti FAILURE
        if self.blackboard.is_charging:
            if livello_batteria < 20:
                print(f"[ControlloBatteria] Batteria critica: {livello_batteria}%. Attivo modalità ricarica.")
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
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.READ)

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
        # Se stavo già andando a ricaricare non devo ricalcolare il percorso
        if self.blackboard.path_to_target and self.blackboard.path_to_target[-1] == self.nodo_ricarica:
            print("[CalcolaPercorsoRicarica] Già in missione verso la stazione di ricarica, non ricalcolo il percorso.")
            return Status.SUCCESS
        else:
            esito = LogicController.find_path(nodo_partenza, self.nodo_ricarica)
            match esito:
                case True:
                    return Status.SUCCESS
                case False:
                    return Status.FAILURE

class VaiAStazioneRicarica(py_trees.behaviour.Behaviour):
    """
    Gestisce la navigazione verso la stazione di ricarica.
    Invia i comandi al Body e aspetta che i sensori confermino lo spostamento.
    """
    def __init__(self):
        super(VaiAStazioneRicarica, self).__init__(name="Vai A Stazione Ricarica")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        
        # Lettura stato attuale
        self.blackboard.register_key(key="current_position", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="am_i_in_a_node", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="next_node", access=py_trees.common.Access.READ)
        
        # Scrittura per aggiornare il percorso
        self.blackboard.register_key(key="next_node", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key(key="path_to_target", access=py_trees.common.Access.WRITE)

    def setup(self):
        print("Setup VaiAStazioneRicarica")
        return True

    def initialise(self):
        pass

    def update(self):
        try:
            lc = self.blackboard.logic_controller
            pos_attuale = self.blackboard.current_position
            in_nodo = self.blackboard.am_i_in_a_node
            percorso_rimanente = self.blackboard.path_to_target
            prossimo_nodo = self.blackboard.next_node
        except KeyError:
            return py_trees.common.Status.FAILURE

        # 1. CONDIZIONE DI VITTORIA: Siamo arrivati alla base?
        if in_nodo and pos_attuale == "ER":
            print(f"[{self.name}] 📍 Arrivati alla Stazione di Ricarica (ER)!")
            return py_trees.common.Status.SUCCESS

        # 2. SIAMO IN UN NODO INTERMEDIO E DOBBIAMO RIPARTIRE
        if in_nodo:
            # Se siamo arrivati al 'next_node' che avevamo puntato, dobbiamo aggiornare la rotta
            if pos_attuale == prossimo_nodo and len(percorso_rimanente) > 0:
                nuovo_prossimo_nodo = percorso_rimanente.pop(0)
                
                self.blackboard.next_node = nuovo_prossimo_nodo
                self.blackboard.path_to_target = percorso_rimanente
                lc.update_path_in_redis(nuovo_prossimo_nodo, percorso_rimanente)
                prossimo_nodo = nuovo_prossimo_nodo # Aggiorniamo la variabile locale per il comando qui sotto

            # Inviamo il comando di movimento verso il prossimo nodo
            print(f"[{self.name}] Partenza dal nodo {pos_attuale} verso {prossimo_nodo}...")
            comando = {
                "type": "MOVE_TO",
                "next_node": prossimo_nodo,
                "current_position": pos_attuale,
                "am_i_in_a_node": in_nodo
            }
            lc.db.set_command(lc.db.COMMAND_CHANNEL, comando)
            
            # Nota: NON settiamo am_i_in_a_node = False qui. Sarà il Body a farlo!
            return py_trees.common.Status.RUNNING

        # 3. SIAMO IN VIAGGIO (am_i_in_a_node == False)
        # Il robot si sta muovendo fisicamente tra un nodo e l'altro.
        # L'albero restituisce semplicemente RUNNING aspettando che il Body dica di essere arrivato.
        else:
            return py_trees.common.Status.RUNNING         


class RicaricaBatteria(py_trees.behaviour.Behaviour):
    """
    Azione: Invia il comando di START_CHARGE al Body e attende che il sensore
    della batteria raggiunga il 100%. Poi invia STOP_CHARGE e dichiara SUCCESS.
    """
    def __init__(self, name="Ricarica Batteria"):
        super().__init__(name)
        # Inizializziamo il Client della Blackboard
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="battery_level", access=py_trees.common.Access.READ)
        
        # Variabile di stato del nodo definita nell'__init__
        self.fase = "INNESCO"

    def setup(self):
        print(f"Setup {self.name}")
        return True

    def initialise(self):
        # Fondamentale: ogni volta che il robot va a ricaricarsi (anche a distanza di giorni),
        # il nodo deve ripartire dall'innesco.
        self.fase = "INNESCO"

    def update(self):
        # 1. Lettura "fresca" ad ogni tick
        try:
            lc = self.blackboard.logic_controller
            livello_attuale = self.blackboard.battery_level
        except KeyError:
            return Status.FAILURE

        # 2. FASE 1: Innesco (Invio Comando)
        if self.fase == "INNESCO":
            print(f"[{self.name}] 🔌 Invio comando al Body: Connettersi ai pin di ricarica (START_CHARGE)...")
            
            comando = {"type": "START_CHARGE"}
            lc.db.set_command(lc.db.COMMAND_CHANNEL, comando)
            
            self.fase = "ATTESA"
            return Status.RUNNING
            
        # 3. FASE 2: Attesa (Lettura Sensori)
        elif self.fase == "ATTESA":
            
            # Condizione di Vittoria: Batteria Piena
            if livello_attuale >= 100.0:
                print(f"[{self.name}] ✅ Ricarica completata (100%). Disconnessione dai pin...")
                
                # Ordiniamo al Body di staccare la spina
                comando_stop = {"type": "STOP_CHARGE"}
                lc.db.set_command(lc.db.COMMAND_CHANNEL, comando_stop)
                
                return Status.SUCCESS
                
            # Condizione di Attesa: Stiamo ancora caricando
            else:
                # Nota: Questo spammerà un po' il terminale, ma è ottimo per vedere 
                # che la comunicazione col Body simulato funziona!
                print(f"[{self.name}] In ricarica... livello sensore: {livello_attuale}%")
                return Status.RUNNING