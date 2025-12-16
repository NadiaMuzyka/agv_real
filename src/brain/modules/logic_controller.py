# FILE: src/brain/modules/logic_controller.py
import time
from modules.redis_interface import RedisInterface 

class LogicController:
    """ Traduce l'intento del BT in comandi V/W grezzi e li pubblica su Redis. """
    
    def __init__(self, redis_interface: RedisInterface):
        self.db = redis_interface
        
        # PID Constants
        self.kp = 0.8
        self.ki = 0.01
        self.kd = 0.1
        
        # PID State
        self.prev_error = 0.0
        self.integral_error = 0.0
        self.last_time = None

    def calculate_pid(self, error: float) -> float:
        current_time = time.time()
        
        if self.last_time is None:
            self.last_time = current_time
            return -self.kp * error # Fallback to P for first step
            
        dt = current_time - self.last_time
        if dt <= 0:
            return -self.kp * error
            
        # P term
        p_term = self.kp * error
        
        # I term
        self.integral_error += error * dt
        i_term = self.ki * self.integral_error
        
        # D term
        d_term = self.kd * (error - self.prev_error) / dt
        
        # Update state
        self.prev_error = error
        self.last_time = current_time
        
        # Output (negative because positive error usually means turn right/negative W)
        return -(p_term + i_term + d_term)
        
    def execute_line_follow(self, line_error: float):
        """ Calcola V e W e pubblica il comando tramite Message Broker (Pub/Sub). """
        MAX_SPEED = 0.5
        
        angular_speed = self.calculate_pid(line_error)
        
        # Chiama set_command, che ora usa PUBLISH
        self.db.set_command(self.db.COMMAND_CHANNEL, {"v": MAX_SPEED, "w": angular_speed})
        
    def execute_stop(self):
        """ Invia il comando di stop. """
        # Reset PID state on stop
        self.prev_error = 0.0
        self.integral_error = 0.0
        self.last_time = None
        
        self.db.set_command(self.db.COMMAND_CHANNEL, {"v": 0.0, "w": 0.0})