# FILE: src/body/modules/redis_interface.py
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
        except redis.exceptions.ConnectionError:
            self.db = None
            print(f"[{self.__class__.__name__}] ERRORE: Impossibile connettersi a Redis.")

    def get_command(self, key: str) -> dict:
        """ Legge i comandi V/W scritti dal Brain (Message Broker). """
        if self.db:
            data = self.db.get(key)
            if data:
                return json.loads(data)
        return {"v": 0.0, "w": 0.0}

    def set_sensor_data(self, key: str, data: dict):
        """ Metodo placeholder per scrivere i dati dei sensori (Belief State futuro). """
        if self.db:
            self.db.set(key, json.dumps(data))