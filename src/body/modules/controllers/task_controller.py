import threading
import time
import json
import queue
from modules.connection.redis_interface import RedisInterface
from modules.controllers.pid_controller import PIDController

IDLE_STATE = "IDLE"
NODE_STATE = "NODE"
FOLLOWING_STATE = "FOLLOWING"
MANEUVERING_STATE = "MANEUVERING"
REVERSE_STATE = "REVERSE"
TARGET_STATE = "TARGET_STATE"
REVERSE_STOP_STATE = "REVERSE_STOP"
ERROR_STATE = "ERROR"

class TaskController:
    def __init__(self):
        """
        Classe che legge i comandi dal Brain e delega la gestione della manovra
        """

        self.redis_client = RedisInterface()
        if not self.redis_client.db:
            print(f"[{self.name}] Redis non raggiungibile.")
            raise ConnectionError("Redis err")
        
        
        # Chiavi Redis per la comunicazione col Brain e col SensorManager
        self.BODY_MEMORY = "body_memory"
        self.BRAIN_MEMORY = "brain_memory"
        self.COMMAND_CHANNEL = "agv_command_channel"
        
        # Stato interno
        self._running = False
        self._thread = None
        self.frequenza_loop = 0.05  # 20 Hz

        self.current_state = IDLE_STATE 
        self.commands = ["MOVE_TO", "STOP", "PICKUP", "DROP"]
        self.maneuver = False #Qui andrà l'istanza
        self.pubsub = self.redis_client.subscribe_to_commands()
        
        # Coda per i comandi
        self.commands_queue = queue.Queue()


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
            if message and message['type'] == 'message':
                try:
                    # Parsa il comando da JSON
                    command_data = json.loads(message['data'])
                    command_type = command_data.get("type")
                    command = command_data
                    if command is not None:
                        print(f"🧠 [TaskController] Comando ricevuto: {command_type} - {command}")
                except json.JSONDecodeError:
                    print(f"⚠️ [TaskController] Comando non valido (non JSON): {message['data']}")
                    command = None
                    command_type = None
            else:
                print(f"🧠 [TaskController] Nessun comando ricevuto. Continuo a monitorare...")

            in_node = self.redis_client.get_sensor_data(self.BRAIN_MEMORY).get("am_i_in_a_node", False)

            # 2. LOGICA DELLA MACCHINA A STATI
            if self.current_state == IDLE_STATE:
                #Se ho un comando di movimento e sono in un nodo, faccio la manovra
                #Se ho un comando di movimento e non sono in un nodo, seguo la linea

                print(f"🧠 [TaskController] Sto in IDLE")

                if command_type in self.commands:
                    if command_type == "STOP":
                        #Se ricevo un comando di STOP, mi fermo e rimango in IDLE
                        pass
                    else:
                        print(f"🧠 [TaskController] Transizione a FOLLOWING")
                        self.current_state = FOLLOWING_STATE

            elif self.current_state == NODE_STATE:
                #Se ricevo un comando di movimento, passo a State MANEUVERING
                #Se ricevo un comando di delivery, passo a DELIVERY_STATE
                #Se ricevo un comando di STOP, mi fermo e passo a IDLE

                print(f"🧠 [TaskController] Sto in NODE")

                
            elif self.current_state == FOLLOWING_STATE:
                #Se arrivo ad un nodo, passo a NODE_STATE
                #Se ricevo un comando di STOP, mi fermo e passo a IDLE

                print(f"🧠 [TaskController] Sto in FOLLOWING")

                if command_type in self.commands:
                    if command_type == "STOP":
                        print(f"🧠 [TaskController] Transizione a IDLE")
                        self.current_state = IDLE_STATE

                
                


            time.sleep(self.frequenza_loop)

    def stop(self):
        """Ferma tutto in sicurezza."""
        self._running = False
        if self._thread:
            self._thread.join()
        self.pid.stop()
        self.maneuver.stop()
        self.actuator.stop()
        print("🧠 [TaskController] Navigazione interrotta.")