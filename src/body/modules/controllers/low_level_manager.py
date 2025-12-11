# FILE: src/body/modules/controllers/low_level_manager.py

class LowLevelManager:
    """
    Controllore di Basso Livello.
    Simula l'esecuzione dei comandi V/W tramite stampa.
    """
    def __init__(self):
        print("[LOW-LEVEL] Controllore Inizializzato (Modalità Debug/Stampa)")

    def execute_command(self, V: float, W: float):
        """ Intercetta il comando V/W e ne simula l'esecuzione. """
        
        if V == 0.0 and W == 0.0:
            print(f"[{self.__class__.__name__}] Comando ricevuto: STOP (V:{V:.2f}, W:{W:.2f})")
        else:
            print(f"[{self.__class__.__name__}] Comando ricevuto: MOVIMENTO (V:{V:.2f}, W:{W:.2f})")