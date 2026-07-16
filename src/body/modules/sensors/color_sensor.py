from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.generic_sensor import GenericSensor
import threading
import time

SENSORS_KEY = "body_memory"

class ColorSensor(GenericSensor):
    def __init__(self, name):
        # Richiama il costruttore della classe base (GenericSensor)
        super().__init__(name)
        
        # 1. Connessione a CoppeliaSim (Isolata e sicura grazie al Multiton)
        self.connector = CoppeliaConnector(name=f"{self.name}")
        self.sim = self.connector.get_sim()
        
        # Recuperiamo l'handle dell'oggetto da CoppeliaSim
        try:
            self.handle = self.sim.getObject(self.name)
        except Exception as e:
            print(f"[{self.name}] ERRORE: Sensore non trovato in CoppeliaSim. Dettagli: {e}")
            self.handle = None

        
        self.frequenza_lettura = 0.05 # 20 Hz
        self._running = False
        self._thread = None
        self.last_color = 0.0 

    def start(self):
        """Avvia il thread del sensore."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_lettura, daemon=True)
            self._thread.start()
            print(f"[{self.name}] Thread avviato.")

    def _loop_lettura(self):
        """Metodo privato che gira in background nel thread."""
        while self._running:
            self.read() 
            time.sleep(self.frequenza_lettura) 

    def read(self):
        """Legge i dati, struttura il dizionario e aggiorna Redis."""
        color_val = self.get_black_percentage()
        self.last_color = color_val #Aggiorno l'ultimo colore letto, accessibile da fuori (es. PIDController)
        
        return color_val 
    
    def get_black_percentage(self):

        res, p1, p2 = self.sim.handleVisionSensor(self.handle)

        img, res = self.sim.getVisionSensorImg(self.handle)

        count = 0
        total_pixels = res[0] * res[1]

        for i in range(total_pixels):
            r = img[i*3]
            g = img[i*3 + 1]
            b = img[i*3 + 2]
            if r <= 30 and g <= 30 and b <= 30:
                count += 1

        return (count / total_pixels) if total_pixels > 0 else 0

    
    def stop(self):
        """Ferma il thread in modo pulito."""
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] Thread fermato.")