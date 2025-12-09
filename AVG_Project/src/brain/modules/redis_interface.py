# FILE: src/brain/modules/redis_interface.py
import os
import redis
import json

class RedisInterface:
    """ Gestisce la connessione e la comunicazione con Redis (agv_redis). """
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
        """ Scrive il comando (Message Broker, tipo di comunicazione utilizzata: key-value). """
        if self.db:
            self.db.set(key, json.dumps(data))

    def get_sensor_data(self, key: str) -> dict:
        """ Legge lo stato (Belief State futuro). """
        if self.db:
            data = self.db.get(key)
            if data:
                return json.loads(data)
        return {}