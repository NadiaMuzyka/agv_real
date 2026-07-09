import threading
import time
import json
import queue
from modules.connection.redis_interface import RedisInterface
from modules.controllers.manuever_controller import ManueverController
from modules.controllers.pid_controller import PIDController


IDLE_STATE = "IDLE"
NODE_STATE = "NODE"
FOLLOWING_STATE = "FOLLOWING"
MANEUVERING_STATE = "MANEUVERING"
REVERSE_STATE = "REVERSE"
TARGET_STATE = "TARGET_STATE"
GO_TARGET_STATE = "GO_TARGET"
ERROR_STATE = "ERROR"

class TaskController:
    def __init__(self, pid: PIDController):
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
        
        self.maneuver = ManueverController(self.redis_client)
        self.pid = pid

        # Memorizza l'ultimo comando per ignorare i duplicati
        self.last_command = None


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

        while self._running:
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

                #print(f"🧠 [TaskController] Sto in IDLE.")
                if in_node:
                    print(f"🧠 [TaskController] Ho rilevato un incrocio. Sto in NODE. La mia posizione è: {current_position}")

                    self.current_state = NODE_STATE    

                elif command_type in self.commands:
                    if command_type == "MOVE_TO" and not in_node:
                        print(f"🧠 [TaskController] Devo continuare a seguire la linea. Sto in FOLLOWING")
                        self.current_state = FOLLOWING_STATE
                    if command_type == "STOP":
                        #print(f"🧠 [TaskController] Ho ricevuto il comando di stop. Sto in IDLE")
                        self.current_state = IDLE_STATE
                    #TODO: potrebbe succedere che gli chiedo di prendere un pacco quando sta in uno stallo.... QUindi non è più error.
                    #Bisogna in tal caso verificare che sia posizionato al contrario
                    elif(command_type in ["PICKUP", "DROP"]):
                        print(f"🧠 [TaskController] Comando PICKUP/DROP ricevuto ma non sono nel nodo finale. Sto in ERROR_STATE")
                        self.current_state = ERROR_STATE
                
                    

            elif self.current_state == NODE_STATE:

                if command_type in self.commands:
                    if command_type == "STOP":
                        print(f"🧠 [TaskController] Ho ricevuto il comando di stop. Sto in IDLE")
                        self.current_state = IDLE_STATE
                    elif command_type == "MOVE_TO":
                        print(f"🧠 [TaskController] Devo eseguire una manovra di svolta. Sto in MANEUVERING")
                        self.current_state = MANEUVERING_STATE
                    elif command_type in ["PICKUP", "DROP"]:
                        print(f"🧠 [TaskController] Non sto nel nodo finale. Sto in ERROR_STATE")
                        self.current_state = ERROR_STATE

                
            elif self.current_state == FOLLOWING_STATE:
                #Se arrivo ad un nodo, passo a NODE_STATE
                #Se ricevo un comando di STOP, mi fermo e passo a IDLE

                pid_active = self.redis_client.get_sensor_data(self.BODY_MEMORY).get("pid_active")

                if not pid_active:
                    print(f"🧠 [TaskController] PID non attivo. Attivo il PID e rimango in FOLLOWING")
                    self.redis_client.update_sensor_data(self.BODY_MEMORY, {"pid_active": True})
                    self.pid.start()

                if in_node:
                    print(f"🧠 [TaskController] Mi sono imbattuto in un incrocio. Sto in NODE")
                    self.redis_client.update_sensor_data(self.BODY_MEMORY, {"pid_active": False})
                    self.pid.stop()
                    self.current_state = NODE_STATE

                elif command_type in self.commands:
                    if command_type == "STOP":
                        #Se ricevo un comando di STOP, mi fermo e rimango in IDLE
                        print(f"🧠 [TaskController] Ho ricevuto il comando di stop")
                        self.redis_client.update_sensor_data(self.BODY_MEMORY, {"pid_active": False})
                        self.pid.stop()
                        self.current_state = IDLE_STATE
                        print(f"🧠 [TaskController] Sto in IDLE")
                    elif(command_type in ["PICKUP", "DROP"]):
                        print(f"🧠 [TaskController] Comando PICKUP/DROP ricevuto ma non sono nel nodo finale. Sto in ERROR_STATE")
                        self.redis_client.update_sensor_data(self.BODY_MEMORY, {"pid_active": False})
                        self.pid.stop()
                        self.current_state = ERROR_STATE
                    elif command_type == "MOVE_TO" and not in_node:
                        self.current_state = FOLLOWING_STATE
                


            elif self.current_state == MANEUVERING_STATE:

                if command_type in self.commands:

                    next_node = self.redis_client.get_sensor_data(self.BRAIN_MEMORY).get("next_node")
                    target_node = self.redis_client.get_sensor_data(self.BRAIN_MEMORY).get("current_target")

                    #print(f"🧠 [TaskController] Stato attuale: Next node: {next_node}, Target node: {target_node}")
            

                    #print(f"🧠 [TaskController] Il prossimo non è il target? {next_node == target_node}")
                    
                    if next_node == target_node:
                        print(f"🧠 [TaskController] Il prossimo nodo è il target. Faccio retromarcia.Sto in REVERSE_STATE")
                        self.current_state = REVERSE_STATE
                        continue

                manuever_state = self.redis_client.get_sensor_data(self.BODY_MEMORY).get("maneuver_state")
                
                #Se non sto già eseguendo una manovra, posso iniziarne una nuova
                if manuever_state == "NONE":

                    print(f"🧠 [TaskController] Inizio esecuzione manovra per comando: {command_type}")
                    self.redis_client.update_sensor_data(self.BODY_MEMORY, {"maneuver_state": "IN_PROGRESS"})
                    time.sleep(0.1) #Piccola pausa per assicurarsi che il PID abbia letto lo stato aggiornato
                    self.maneuver.execute_maneuver(command_type, command)
                    
                #Se la sto eseguendo, gestisco i comandi che mi arrivano durante l'esecuzione
                elif manuever_state == "IN_PROGRESS":

                    if command_type == "STOP":
                        #Se ricevo un comando di STOP, mi fermo e vado in ERROR (perché non posso interrompere una manovra a metà)
                        
                        #TODO:Gestire meglio questa situazione

                        print(f"🧠 [TaskController] Ho ricevuto il comando di interruzione della manovra. Sto in ERROR")
                        self.current_state = ERROR_STATE

                elif manuever_state == "COMPLETED":
                    self.redis_client.update_sensor_data(self.BODY_MEMORY, {"maneuver_state": "NONE"})
                    print(f"🧠 [TaskController] Manovra completata. Sto in IDLE")
                    self.current_state = IDLE_STATE


    
            elif self.current_state == REVERSE_STATE:
                
                manuever_state = self.redis_client.get_sensor_data(self.BODY_MEMORY).get("maneuver_state")
                
                #Se non sto già eseguendo una manovra, posso iniziarne una nuova
                if manuever_state == "NONE":

                    print(f"🧠 [TaskController] Inizio retromarcia")
                    self.redis_client.update_sensor_data(self.BODY_MEMORY, {"maneuver_state": "IN_PROGRESS"})
                    time.sleep(0.1) #Piccola pausa 
                    self.maneuver.execute_maneuver(command_type, command, retro = True, pid=self.pid)
                    
                #Se la sto eseguendo, gestisco i comandi che mi arrivano durante l'esecuzione
                elif manuever_state == "IN_PROGRESS":

                    if command_type == "STOP":
                        #Se ricevo un comando di STOP, mi fermo e vado in ERROR (perché non posso interrompere una manovra a metà)
                        
                        #TODO:Gestire meglio questa situazione

                        print(f"🧠 [TaskController] Ho ricevuto il comando di interruzione della manovra. Sto in ERROR")
                        self.current_state = ERROR_STATE

                elif manuever_state == "COMPLETED":
                    self.redis_client.update_sensor_data(self.BODY_MEMORY, {"maneuver_state": "NONE"})
                    print(f"🧠 [TaskController] Ho finito di girare. Vado in GO TOTARGET STATE")
                    self.current_state = GO_TARGET_STATE

            elif self.current_state == GO_TARGET_STATE:

                #print(f"🧠 [TaskController] Sto facendo retromarcia fino al target")

                #1) supera l'incrocio
                #2) continua a seguire la linea finché non arrivo al nodo target

                pid_active = self.redis_client.get_sensor_data(self.BODY_MEMORY).get("pid_active")

                if not pid_active:
                    print(f"🧠 [TaskController] PID non attivo. Attivo il PID e rimango in FOLLOWING")
                    self.redis_client.update_sensor_data(self.BODY_MEMORY, {"pid_active": True})
                    self.pid.start(reverse=True)


                if in_node and target_node == current_position:
                    
                    print(f"🧠 [TaskController] Sono arrivato al nodo target.")
                    self.redis_client.update_sensor_data(self.BODY_MEMORY, {"pid_active": False})
                    self.pid.stop()
                    self.current_state = TARGET_STATE




            elif self.current_state == TARGET_STATE:
                print(f"🧠 [TaskController] Sono nel nodo target. Aspetto comandi di PICKUP/DROP")


            time.sleep(self.frequenza_loop)

                


    def stop(self):
        """Ferma tutto in sicurezza."""
        self._running = False
        if self._thread:
            self._thread.join()
        self.pid.stop()
        self.maneuver.stop()
        print("🧠 [TaskController] Navigazione interrotta.")