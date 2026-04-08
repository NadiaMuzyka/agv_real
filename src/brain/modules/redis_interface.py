# FILE: src/brain/modules/redis_interface.py

import os
import redis
import json

class RedisInterface:
    COMMAND_CHANNEL = "agv_command_channel" # Canale Pub/Sub
    
    def __init__(self):
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.db = None
        
        try:
            self.db = redis.Redis(host=redis_host, port=6379, decode_responses=True)
            self.db.ping()
            print(f"[{self.__class__.__name__}] Connessione a Redis stabilita con successo.")
        except redis.exceptions.ConnectionError:
            print(f"[{self.__class__.__name__}] ERRORE: Impossibile connettersi a Redis.")
            
    def set_command(self, key: str, data: dict):
        """ Message Broker: Pubblica il comando V/W sul canale Pub/Sub. """
        if self.db:
            json_data = json.dumps(data)
            self.db.publish(self.COMMAND_CHANNEL, json_data)

    def get_sensor_data(self, key: str) -> dict:
        """ Legge lo stato (Belief State futuro). """
        if self.db:
            data = self.db.get(key)
            if data:
                return json.loads(data)
        return {}
    
    # Metodo per aggiornare solo alcuni campi del dato su Redis (SOLO PER TEST, DA RIMUOVERE QUANDO COLLEGHEREMO IL BODY)
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


