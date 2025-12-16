# FILE: src/body/modules/controllers/low_level_manager.py

from time import time


class LowLevelManager:
    """
    Controllore di Basso Livello.
    Simula l'esecuzione dei comandi V/W tramite stampa.
    """
    def __init__(self):
        print("[LOW-LEVEL] Controllore Inizializzato (Modalità Debug/Stampa)")
        self.last_print_time = 0

    def execute_command(self, V: float, W: float):
        """ Intercetta il comando V/W e ne simula l'esecuzione. """
            
        # Stampa solo se è passato abbastanza tempo (es. 1 secondo) O se è un comando di STOP critico
        current_time = time()
        if (V == 0.0 and W == 0.0) or (current_time - self.last_print_time > 1.0):
            if V == 0.0 and W == 0.0:
                print(f"[{self.__class__.__name__}] Comando ricevuto: STOP (V:{V:.2f}, W:{W:.2f})")
            else:
                print(f"[{self.__class__.__name__}] Comando ricevuto: MOVIMENTO (V:{V:.2f}, W:{W:.2f})")
            
            self.last_print_time = current_time