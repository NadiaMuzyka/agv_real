import os
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

class CoppeliaConnector:

    """
    Gestisce la connessione a CoppeliaSim come Singleton.
    Garantisce che tutte le parti del codice condividano la stessa istanza di connessione"""
    _instance = None
    _client = None
    _sim = None

    def __new__(cls):
        """Implementazione Singleton: garantisce una sola connessione."""
        if cls._instance is None:
            cls._instance = super(CoppeliaConnector, cls).__new__(cls)
        return cls._instance

    def connect(self):
        """Stabilisce la connessione se non è già attiva."""
        if self._sim is None:
            # Prende l'host da Docker o usa il default per Windows/Mac
            host = os.getenv('COPPELIA_HOST', 'host.docker.internal')
            port = int(os.getenv('COPPELIA_PORT', 23000))
            
            try:
                print(f"Tentativo di connessione a CoppeliaSim su {host}:{port}...")
                self._client = RemoteAPIClient(host=host, port=port)
                self._sim = self._client.getObject('sim')
                print("Connessione stabilita con successo!")
            except Exception as e:
                print(f"Errore di connessione a CoppeliaSim: {e}")
                self._sim = None
        
        return self._sim

    def get_sim(self):
        """Restituisce l'oggetto sim per interagire con le API."""
        if not self._sim:
            return self.connect()
        return self._sim