from modules.sensors.generic_sensor import GenericSensor
from modules.redis_interface import RedisInterface 
import threading
import time
import os

SENSORS_KEY = "body_memory"

class ColorSensor(GenericSensor):
    def __init__(self, sim, name):
        # Richiama il costruttore della classe base (GenericSensor)
        super().__init__(name)
        self.sim = sim
        self.name = name # Assicurati di avere questo attributo, o cambialo in base a GenericSensor
        
        # In CoppeliaSim, 'name' sarà il percorso o il nome dell'oggetto
        self.handle = self.sim.getObject(name)

        # Connessione a Redis (usa il Singleton)
        self.redis_client = RedisInterface()
        if not self.redis_client.db:
            print(f"[{self.name}] Redis non raggiungibile.")
            raise ConnectionError("Redis err")
        
        self.frequenza_lettura = 0.1 # 10 Hz, regolabile
        self._running = False
        self._thread = None
        # Thread-local client/sim (created inside the sensor thread)
        self._thread_client = None
        self._thread_sim = None

    def start(self):
        """Avvia il thread del sensore."""
        if not self._running:
            self._running = True
            # Usiamo un metodo dedicato per il loop continuo
            self._thread = threading.Thread(target=self._loop_lettura, daemon=True)
            self._thread.start()
            print(f"[{self.name}] Thread avviato.")

    def _loop_lettura(self):
        """Metodo privato che gira in background nel thread."""
        # Creiamo un RemoteAPIClient locale a questo thread per evitare
        # l'uso concorrente dello stesso socket ZMQ da più thread.
        try:
            # Import locale per non forzare la dipendenza a import-time
            from coppeliasim_zmqremoteapi_client import RemoteAPIClient
            host = os.getenv('COPPELIA_HOST', 'host.docker.internal')
            port = int(os.getenv('COPPELIA_PORT', 23000))
            client = RemoteAPIClient(host=host, port=port)
            sim_local = client.getObject('sim')
            self._thread_client = client
            self._thread_sim = sim_local
        except Exception as e:
            print(f"[{self.name}] Impossibile creare RemoteAPIClient nel thread: {e}")
            self._running = False
            return

        try:
            while self._running:
                self.read() # Esegue la lettura e la scrittura su Redis
                time.sleep(self.frequenza_lettura) # Pausa vitale per non saturare la CPU!
        finally:
            # Tentiamo di chiudere il client se espone un metodo di chiusura
            try:
                if hasattr(client, 'close'):
                    client.close()
                elif hasattr(client, '__exit__'):
                    client.__exit__(None, None, None)
            except Exception as e:
                print(f"[{self.name}] Errore durante la chiusura del client: {e}")
            finally:
                self._thread_client = None
                self._thread_sim = None

    def read(self):
        """
        Legge i dati, struttura il dizionario e aggiorna Redis.
        """
        color_val = self.read_rgb255()
        
        # Strutturiamo il dato sotto una sotto-chiave col nome del sensore
        # In questo modo update_sensor_data non cancella gli altri sensori
        sensor_data = {
            self.name: {
                "color": color_val,
                "timestamp": time.time()
            }
        }
        
        # Usiamo UPDATE, non SET, per non distruggere il Belief State degli altri sensori
        self.redis_client.update_sensor_data(SENSORS_KEY, sensor_data)
        
        return color_val # Utile se mai volessi chiamarlo manualmente senza thread

    def read_normalized(self):
        """Legge dal sensore e restituisce i valori RGB normalizzati (0.0 - 1.0)."""
        # Preferisci il sim locale del thread (se presente), altrimenti usa
        # il `sim` passato all'inizio (fallback per chiamate sincrone)
        sim_obj = getattr(self, '_thread_sim', None) or self.sim
        try:
            res, p1, p2 = sim_obj.handleVisionSensor(self.handle)
        except Exception:
            return None, None, None

        if res >= 0 and p1 and len(p1) > 12:
            r = round(p1[10], 3)
            g = round(p1[11], 3)
            b = round(p1[12], 3)
            return r, g, b

        return None, None, None

    def read_rgb255(self):
        """Restituisce i valori RGB in scala 0-255."""
        r, g, b = self.read_normalized()
        if r is not None:
            return int(r * 255), int(g * 255), int(b * 255)
            
        return None, None, None
    
    def stop(self):
        """Ferma il thread in modo pulito."""
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] Thread fermato.")
        # Se per qualche motivo il client del thread è ancora aperto,
        # tentiamo di chiuderlo anche qui (operazione sicura se il thread
        # ha già liberato la risorsa).
        client = getattr(self, '_thread_client', None)
        if client:
            try:
                if hasattr(client, 'close'):
                    client.close()
                elif hasattr(client, '__exit__'):
                    client.__exit__(None, None, None)
            except Exception as e:
                print(f"[{self.name}] Errore chiusura client nel stop: {e}")
            finally:
                self._thread_client = None
                self._thread_sim = None