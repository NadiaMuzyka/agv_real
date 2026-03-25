# FILE: src/body/modules/controllers/low_level_manager.py

from time import time


class LowLevelManager:
    """
    Controllore di Basso Livello.
    Riceve comandi di alto livello (es. LINE_FOLLOW) e calcola V/W tramite PID.
    """
    def __init__(self, sim=None):
        print("[LOW-LEVEL] Controllore Inizializzato (Modalità Debug/Stampa)")
        self.last_print_time = 0
        self.sim = sim
        print("🛠️ LowLevelManager inizializzato con successo!")
        
        # PID Constants
        self.kp = 0.8
        self.ki = 0.01
        self.kd = 0.1
        
        # PID State
        self.prev_error = 0.0
        self.integral_error = 0.0
        self.last_time = None

    def calculate_pid(self, error: float) -> float:
        current_time = time()
        
        if self.last_time is None:
            self.last_time = current_time
            return -self.kp * error 
            
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
        
        return -(p_term + i_term + d_term)

    def execute_command(self, command_data: dict):
        """ Intercetta il comando e decide come muovere i motori. """
        
        cmd_type = command_data.get("type", "UNKNOWN")
        V = 0.0
        W = 0.0

        if cmd_type == "LINE_FOLLOW":
            error = command_data.get("error", 0.0)
            target_speed = command_data.get("target_speed", 0.0)
            
            # Calcolo PID locale
            W = self.calculate_pid(error)
            V = target_speed
            
        elif cmd_type == "STOP":
            V = 0.0
            W = 0.0
            # Reset PID
            self.prev_error = 0.0
            self.integral_error = 0.0
            self.last_time = None
            
        elif "v" in command_data and "w" in command_data:
            # Fallback per comandi diretti V/W (legacy)
            V = command_data.get("v", 0.0)
            W = command_data.get("w", 0.0)

        # --- SIMULAZIONE ATTUAZIONE ---
        current_time = time()
        if (V == 0.0 and W == 0.0) or (current_time - self.last_print_time > 1.0):
            if V == 0.0 and W == 0.0:
                print(f"[{self.__class__.__name__}] STOP (V:{V:.2f}, W:{W:.2f})")
            else:
                print(f"[{self.__class__.__name__}] MOVIMENTO (Type:{cmd_type}, V:{V:.2f}, W:{W:.2f})")
            
            self.last_print_time = current_time