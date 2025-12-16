# FILE: src/brain/modules/logic_controller.py
import time
from modules.redis_interface import RedisInterface 

class LogicController:
    """ Traduce l'intento del BT in comandi di alto livello e li pubblica su Redis. """
    
    def __init__(self, redis_interface: RedisInterface):
        self.db = redis_interface

    def execute_line_follow(self, line_error: float):
        """ Invia l'errore di linea al Body, delegando il controllo PID al basso livello. """
        # Pubblica un comando di tipo "LINE_FOLLOW" con l'errore
        command = {
            "type": "LINE_FOLLOW",
            "error": line_error,
            "target_speed": 0.5 # Velocità desiderata
        }
        self.db.set_command(self.db.COMMAND_CHANNEL, command)
        
    def execute_stop(self):
        """ Invia il comando di stop. """
        command = {
            "type": "STOP",
            "v": 0.0, 
            "w": 0.0
        }
        self.db.set_command(self.db.COMMAND_CHANNEL, command)