import threading
import time
import json
import queue
from modules.connection.redis_interface import RedisInterface
from modules.controllers.manuever_controller import ManueverController


IDLE_STATE = "IDLE"
NODE_STATE = "NODE"
FOLLOWING_STATE = "FOLLOWING"
MANEUVERING_STATE = "MANEUVERING"
REVERSE_STATE = "REVERSE"
TARGET_STATE = "TARGET_STATE"
GO_TARGET_STATE = "GO_TARGET"
ERROR_STATE = "ERROR"

class TaskController:
    def __init__(self, connector, stop_event=None):
        """
        Classe che legge i comandi dal Brain e delega la gestione della manovra
        """

        self.redis_client = RedisInterface()
        if not self.redis_client.db:
            print(f"[{self.name}] Redis non raggiungibile.")
            raise ConnectionError("Redis err")
        
        # Inizializza la body_memory
        self.redis_client.initialize_body_memory()
        self.redis_client.initialize_brain_memory()
        
        # Chiavi Redis per la comunicazione col Brain e col SensorManager
        self.BODY_MEMORY = "body_memory"
        self.BRAIN_MEMORY = "brain_memory"
        self.COMMAND_CHANNEL = "agv_command_channel"
        
        # Stato interno
        self._running = False
        self._thread = None
        self.frequenza_loop = 0.1  # 20 Hz

        self.current_state = IDLE_STATE 
        print(f"🧠 [TaskController] Sto in IDLE")
        self.commands = ["MOVE_TO", "STOP", "PICKUP", "DROP", "SHUTDOWN"]
        self.pubsub = self.redis_client.subscribe_to_commands()
        
        self.maneuver = ManueverController(connector, self.redis_client)

        # Memorizza l'ultimo comando per ignorare i duplicati
        self.last_command = None
        self.stop_event = stop_event 


    def start(self):
        """Avvia il thread del controller di missione."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_navigazione, daemon=True)
            self._thread.start()
            print("🧠 [TaskController] Avviato. Pronto per la navigazione.")

    def _loop_navigazione(self):
        """Loop sequenziale che legge da redis e gestisce le manovre ad alto livello."""
        
        command = None
        command_type = None
        dispatched_command = None  # copia del comando davvero passato a execute_maneuver

        while self._running:
            if not self._running:
                break

            # 1. Legge l'obiettivo dal Brain (NON bloccante)
            message = self.pubsub.get_message()

            #Elaborazione del messaggio
            if message and message['type'] == 'message':
                try:
                    # Parsa il comando da JSON
                    command_data = json.loads(message['data'])
                    command_type = command_data.get("type")
                    command = command_data
                    if command is not None:
                        # Ignora il comando se è identico al precedente
                        if command != self.last_command:
                            #print(f"🧠 [TaskController] Comando duplicato ignorato: {command_type}")
                            # NON resettare a None! Mantieni il comando attivo per il maneuvering
                        #else:
                            print(f"🧠 [TaskController] Comando ricevuto: {command_type} - {command}")
                            self.last_command = command
                except json.JSONDecodeError:
                    print(f"⚠️ [TaskController] Comando non valido (non JSON): {message['data']}")
                    command = None
                    command_type = None

            in_node = self.redis_client.get_sensor_data(self.BRAIN_MEMORY).get("am_i_in_a_node")
            next_node = self.redis_client.get_sensor_data(self.BRAIN_MEMORY).get("next_node")
            target_node = self.redis_client.get_sensor_data(self.BRAIN_MEMORY).get("current_target")
            current_position = self.redis_client.get_sensor_data(self.BRAIN_MEMORY).get("current_position")

            #print(f"🧠 [TaskController] In node: {in_node}")
            #print(f"🧠 [TaskController] Stato attuale: Next node: {next_node}, Target node: {target_node}")
            

            # 2. LOGICA DELLA MACCHINA A STATI
            if self.current_state == IDLE_STATE:
                #Se ho un comando di movimento e sono in un nodo, faccio la manovra
                #Se ho un comando di movimento e non sono in un nodo, seguo la linea

                print(f"[IDLE_STATE] Sono in un nodo? {in_node} ")

                #print(f"🧠 [TaskController] Sto in IDLE.")
                if in_node:
                    print(f"🧠 [TaskController] Ho rilevato un incrocio. Sto in NODE. La mia posizione è: {current_position}")

                    self.current_state = NODE_STATE    

                elif command_type in self.commands:
                    if command_type == "MOVE_TO":
                        print(f"🧠 [TaskController] Devo andare al target. vado in MANEUVERING")
                        self.current_state = MANEUVERING_STATE

                    if command_type == "STOP":
                        #print(f"🧠 [TaskController] Ho ricevuto il comando di stop. Sto in IDLE")
                        self.current_state = IDLE_STATE

                else:
                    print(f"🧠 [TaskController] Nessun comando attivo. Rimango in IDLE")
                
            elif self.current_state == NODE_STATE:

                if current_position == target_node:
                    print("Sto nel nodo target")
                    self.current_state = TARGET_STATE

                if command_type in self.commands:
                    if command_type == "STOP":
                        print(f"🧠 [TaskController] Ho ricevuto il comando di stop. Sto in IDLE")
                        self.current_state = IDLE_STATE

                    elif command_type == "MOVE_TO":
                        print(f"🧠 [TaskController] Devo andare al target. Sto in MANEUVERING")
                        self.current_state = MANEUVERING_STATE

                    elif command_type in ["PICKUP", "DROP"]:
                        print(f"🧠 [TaskController] Non sto nel nodo finale. Devo eseguire una manovra. Vado in manuevering")
                        self.current_state = MANEUVERING_STATE
                else:
                    print(f"🧠 [TaskController] Nessun comando attivo. Rimango in NODE")
                
            elif self.current_state == MANEUVERING_STATE:

                manuever_state = self.redis_client.get_sensor_data(self.BODY_MEMORY).get("maneuver_state")

                # Stop cooperativo: non decido qui cosa significhi "fermarsi"
                # (finire la svolta in corso, fermarsi subito durante
                # l'avanzata, o ignorarlo del tutto durante PICKUP/DROP) —
                # lo decide il ManeuverController nei punti giusti. Qui alzo
                # solo il flag, ad ogni tick finché la manovra non termina.
                if command_type == "STOP" and manuever_state == "IN_PROGRESS":
                    self.maneuver.request_stop()

                if command_type in self.commands:

                    next_node = self.redis_client.get_sensor_data(self.BRAIN_MEMORY).get("next_node")
                    target_node = self.redis_client.get_sensor_data(self.BRAIN_MEMORY).get("current_target")
                    current_position = self.redis_client.get_sensor_data(self.BRAIN_MEMORY).get("current_position")

                    #print(f"🧠 [TaskController] Stato attuale: Next node: {next_node}, Target node: {target_node}")

                    if manuever_state == "COMPLETED" and command_type in ["PICKUP", "DROP"]:
                        # Azzero command_type solo se non è già arrivato un
                        # comando nuovo nel frattempo (confronto con quello
                        # davvero dispacciato): altrimenti, se il comando
                        # successivo arriva pochi istanti prima che scriva
                        # COMPLETED, lo perderei qui.
                        if command == dispatched_command:
                            command_type = None
                        self.redis_client.update_sensor_data(self.BODY_MEMORY, {"maneuver_state": "NONE"})
                        print(f"🧠 [TaskController] Manovra completata. Sto in IDLE")
                        self.current_state = IDLE_STATE

                #Se non sto già eseguendo una manovra, posso iniziarne una nuova
                if manuever_state == "NONE":

                    print(f"🧠 [TaskController] Inizio esecuzione manovra per comando: {command_type}")
                    self.redis_client.update_sensor_data(self.BODY_MEMORY, {"maneuver_state": "IN_PROGRESS"})
                    dispatched_command = command
                    self.maneuver.execute_maneuver(command_type, command)

                elif manuever_state == "COMPLETED":
                    # Stessa cautela: un MOVE_TO già eseguito deve smettere di
                    # essere "attivo" (altrimenti la FSM lo ridispaccia stantio
                    # al prossimo NODE_STATE), ma solo se non è già arrivato un
                    # comando nuovo che lo ha sostituito nel frattempo.
                    if command == dispatched_command:
                        command_type = None
                    self.redis_client.update_sensor_data(self.BODY_MEMORY, {"maneuver_state": "NONE"})
                    print(f"🧠 [TaskController] Manovra completata. Sto in IDLE")
                    self.current_state = IDLE_STATE

                    if dispatched_command and dispatched_command.get("type") == "SHUTDOWN":
                        print("🔌 [TaskController] SHUTDOWN completato (dock incluso). Fermo il Body.")
                        self._running = False
                        if self.stop_event:
                            self.stop_event.set()  # ← sblocca il loop → va in cleanup()

            elif self.current_state == TARGET_STATE:

                if command_type in ["PICKUP", "DROP"]:
                    print(f"🧠 [TaskController] Comando PICKUP/DROP ricevuto. Sto in MANEUVERING")
                    self.current_state = MANEUVERING_STATE
                else:
                    print(f"🧠 [TaskController] Vado in IDLE_STATE")
                    self.current_state = IDLE_STATE                
                
            time.sleep(self.frequenza_loop)


    def stop(self):
        """Ferma tutto in sicurezza."""
        self._running = False
        if self._thread:
            self._thread.join()
        
        
        self.maneuver.stop()
        print("🧠 [TaskController] Navigazione interrotta.")