from coppeliasim_zmqremoteapi_client import RemoteAPIClient
from NavigatoreGrafo import NavigatoreGrafo
from ColorSensor import ColorSensor
import time

class RobotController:
    def __init__(self):
        """Inizializza la connessione a CoppeliaSim e i componenti del robot."""
        self.client = RemoteAPIClient()
        self.sim = self.client.getObject('sim')
        
        # Creiamo un'istanza del nostro sensore, passandogli l'oggetto 'sim'
        self.color_sensor = ColorSensor(self.sim, '/Robot/visionSensor')
        
    def start(self):
        """Avvia la simulazione e il ciclo di lettura."""
        print("--- Test Robot e Sensore Modulare Avviato ---")
        self.sim.startSimulation()
        
        try:
            # Reiseriamo il ciclo while per testarlo in modo continuo
            for i in range(5):
                # Chiediamo direttamente al sensore i valori già formattati a 255!
                r, g, b = self.color_sensor.read_rgb255()
                
                if r is not None:
                    print(f"Colore Rilevato (0-255) -> R: {r:3d} | G: {g:3d} | B: {b:3d}")
                else:
                    print("Errore o dati non pronti.")
                    
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nTest interrotto dall'utente.")
        finally:
            self.sim.stopSimulation()
            print("Simulazione terminata.")

    def percorso(self, nodo_partenza, nodo_arrivo):
        """Metodo per calcolare e seguire un percorso tra due nodi."""
        # Qui potremmo integrare il NavigatoreGrafo per ottenere il percorso
        sistema_navigazione = NavigatoreGrafo()

        # Calcoliamo il percorso
        percorso, distanza = sistema_navigazione.trova_percorso_minimo(nodo_partenza, nodo_arrivo)

        print(percorso, distanza)

# Esecuzione principale
if __name__ == "__main__":
    mio_robot = RobotController()
    #mio_robot.start()
    mio_robot.percorso("EC", "E2")  # Esempio di chiamata al metodo percorso (da implementare)