# FILE: src/body/modules/redis_interface.py
import os
import redis
import json

class RedisInterface:
    COMMAND_CHANNEL = "agv_command_channel"
    RESET_CHANNEL = "agv_reset"
    
    def __init__(self):
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.db = None
        
        try:
            self.db = redis.Redis(host=redis_host, port=6379, decode_responses=True)
            self.db.ping()
        except redis.exceptions.ConnectionError:
            self.db = None
            print(f"[{self.__class__.__name__}] ERRORE: Impossibile connettersi a Redis.")

    def subscribe_to_commands(self):
        """ Crea un oggetto PubSub e si iscrive al canale dei comandi e del reset. """
        if not self.db:
            return None

        pubsub = self.db.pubsub()
        pubsub.subscribe(self.COMMAND_CHANNEL)
        pubsub.subscribe(self.RESET_CHANNEL)
        print(f"[{self.__class__.__name__}] Iscritto ai canali {self.COMMAND_CHANNEL} e {self.RESET_CHANNEL}.")
        return pubsub
        
    def set_sensor_data(self, key: str, data: dict):
        """ Metodo placeholder per scrivere i dati dei sensori (Belief State futuro). """
        if self.db:
            self.db.set(key, json.dumps(data))

    def update_sensor_data(self, key: str, partial_data: dict):
        """ 
        Aggiorna SOLO i campi specificati in 'partial_data'.
        Lascia intatti tutti gli altri campi già presenti su Redis.
        """
        if not self.db:
            return

        # 1. Legge cosa c'è attualmente su Redis
        existing_data_str = self.db.get(key)
        
        # 2. Converte la stringa JSON in un dizionario Python
        if existing_data_str:
            try:
                current_data = json.loads(existing_data_str)
            except json.JSONDecodeError:
                # Se per qualche motivo il dato su Redis è corrotto, ripartiamo da zero
                current_data = {}
        else:
            # Se la chiave non esiste ancora su Redis, creiamo un dizionario vuoto
            current_data = {}

        # 3. Unisce i dati vecchi con quelli nuovi!
        # (Se una chiave in partial_data esiste già, viene sovrascritta. Altrimenti viene aggiunta).
        current_data.update(partial_data)

        # 4. Salva il dizionario unito (e aggiornato) di nuovo su Redis
        self.db.set(key, json.dumps(current_data))