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