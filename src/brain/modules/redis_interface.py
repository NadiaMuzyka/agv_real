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
    
    #metodo da eliminare , usato i fase di test
    def set_sensor_data(self, key: str, data: dict):
        """ Metodo di test: scrive dati di sensori su Redis. """
        if self.db:
            json_data = json.dumps(data)
            self.db.set(key, json_data)


