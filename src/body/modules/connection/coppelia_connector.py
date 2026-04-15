import os
import threading
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

class CoppeliaConnector:
    """
    Gestisce connessioni multiple a CoppeliaSim (Multiton pattern).
    Mantiene un'istanza condivisa ('main') e permette istanze dedicate per i thread.
    """
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, name="main"):
        """
        Ritorna l'istanza associata al 'name'. Se non esiste, la crea.
        name="main" garantisce la compatibilità con il codice esistente.
        """
        with cls._lock:
            if name not in cls._instances:
                instance = super(CoppeliaConnector, cls).__new__(cls)
                instance._initialized = False
                cls._instances[name] = instance
        return cls._instances[name]

    def __init__(self, name="main"):
        # Se l'istanza con questo nome è già stata configurata, non fare nulla
        if self._initialized:
            return
            
        self.name = name
        self._client = None
        self._sim = None
        
        # Parametri di rete
        self.host = os.getenv('COPPELIA_HOST', 'host.docker.internal')
        self.port = int(os.getenv('COPPELIA_PORT', 23000))
        
        # Esegue la connessione immediata
        self.connect()
        self._initialized = True

    def connect(self):
        """Stabilisce la connessione specifica per questa istanza."""
        if self._sim is None:
            try:
                print(f"[CoppeliaConnector:{self.name}] Connessione a {self.host}:{self.port}...")
                self._client = RemoteAPIClient(host=self.host, port=self.port)
                self._sim = self._client.getObject('sim')
                print(f"[CoppeliaConnector:{self.name}] Connessione stabilita.")
            except Exception as e:
                print(f"[CoppeliaConnector:{self.name}] ERRORE: {e}")
                self._sim = None
        return self._sim

    def get_sim(self):
        """Restituisce l'oggetto sim specifico per questa connessione."""
        if not self._sim:
            return self.connect()
        return self._sim