# FILE: src/brain/modules/logic_controller.py
from modules.redis_interface import RedisInterface 

class LogicController:
    """ Traduce l'intento del BT in comandi V/W grezzi e li invia a Redis. """
    COMMAND_KEY = "agv_command"
    
    def __init__(self, redis_interface: RedisInterface):
        self.db = redis_interface
        
    def execute_line_follow(self, line_error: float):
        """ Calcola V e W e pubblica il comando tramite Message Broker. """
        MAX_SPEED = 0.5
        KP = 0.8          
        angular_speed = -KP * line_error
        
        self.db.set_command(self.COMMAND_KEY, {"v": MAX_SPEED, "w": angular_speed})
        
    def execute_stop(self):
        """ Invia il comando di stop. """
        self.db.set_command(self.COMMAND_KEY, {"v": 0.0, "w": 0.0})