import os
import redis
import json
import threading

class RedisInterface:
    _instance = None
    _lock = threading.Lock()  # Protegge la creazione dell'istanza in ambienti multithread
    
    COMMAND_CHANNEL = "agv_command_channel"
    RESET_CHANNEL = "agv_reset"
    
    def __new__(cls):
        # Se l'istanza non esiste, la creiamo in modo thread-safe
        if cls._instance is None:
            with cls._lock:
                # Doppia verifica (double-checked locking)
                if cls._instance is None:
                    cls._instance = super(RedisInterface, cls).__new__(cls)
                    # Flag per assicurarci che __init__ giri una sola volta
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # Impedisce la sovrascrittura della connessione se l'istanza esiste già
        if self._initialized:
            return
            
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.db = None
        
        try:
            self.db = redis.Redis(host=redis_host, port=6379, decode_responses=True)
            self.db.ping()
            self._initialized = True
            print(f"[{self.__class__.__name__}] Connessione a Redis stabilita con successo.")
        except redis.exceptions.ConnectionError:
            self.db = None
            print(f"[{self.__class__.__name__}] ERRORE: Impossibile connettersi a Redis.")

    def subscribe_to_commands(self):
        if not self.db:
            return None
        pubsub = self.db.pubsub()
        pubsub.subscribe(self.COMMAND_CHANNEL, self.RESET_CHANNEL)
        print(f"[{self.__class__.__name__}] Iscritto ai canali {self.COMMAND_CHANNEL} e {self.RESET_CHANNEL}.")
        return pubsub
        
    def set_sensor_data(self, key: str, data: dict):
        if self.db:
            self.db.set(key, json.dumps(data))

    def update_sensor_data(self, key: str, partial_data: dict):
        if not self.db:
            return

        existing_data_str = self.db.get(key)
        if existing_data_str:
            try:
                current_data = json.loads(existing_data_str)
            except json.JSONDecodeError:
                current_data = {}
        else:
            current_data = {}

        current_data.update(partial_data)
        self.db.set(key, json.dumps(current_data))

    def get_sensor_data(self, key: str) -> dict:
        """ Legge lo stato (Belief State futuro). """
        if self.db:
            data = self.db.get(key)
            if data:
                return json.loads(data)
        return {}

    def initialize_body_memory(self):
        """Inizializza la body_memory con i valori di default."""
        if not self.db:
            print(f"[{self.__class__.__name__}] ❌ Redis non disponibile per l'inizializzazione!")
            return
        
        initial_state = {
            "maneuver_state": "NONE",  # Può essere "NONE", "IN_PROGRESS", "COMPLETED"
            "pid_active": False
        }
        
        self.set_sensor_data("body_memory", initial_state)
        print(f"[{self.__class__.__name__}] ✅ Body memory inizializzata con stato di default.")

    def set_command(self, channel: str, command):
        """ Pubblica un comando sul canale specificato. """
        if not self.db:
            print(f"[{self.__class__.__name__}] ❌ Redis non disponibile!")
            return False
        
        try:
            # Se il comando è un dizionario, lo converte in JSON
            if isinstance(command, dict):
                command_json = json.dumps(command)
            else:
                command_json = str(command)
            
            # Pubblica il comando sul canale
            num_subscribers = self.db.publish(channel, command_json)
            print(f"[{self.__class__.__name__}] Comando pubblicato su {channel}: {command_json} (subscribers: {num_subscribers})")
            return True
        except Exception as e:
            print(f"[{self.__class__.__name__}] ❌ Errore nella pubblicazione del comando: {e}")
            return False