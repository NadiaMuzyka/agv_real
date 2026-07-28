import time
import os
import signal
import threading


from modules.sensors.sensor_manager import SensorManager
from modules.connection.create3_connector import Create3Connector
from modules.controllers.task_controller import TaskController
from modules.sensors.vision_sensor import VisionSensor
from modules.sensors.color_zone_sensor import ColorZoneSensor
from modules.sensors.lidar_sensor import LidarSensor

class RobotController:
    """
    Orchestrates the Body service from hardware sensing to hardware actions.
    """
    
    # --- COSTANTI DI CONFIGURAZIONE ---
    VISION_SENSOR_NAME = "vision"
    LOOP_HZ = 20

    queue = ["RIGHT", "LEFT", "STOP"] #simulazione coda di navigazione (Redis/Brain)
    
    def __init__(self):
        """
        Initialize the robot controller and its hardware interfaces.
        Args:
            None.

        Returns:
            None.

        Raises:
            ConnectionError: If the controller cannot connect to CoppeliaSim.
        """
        print("Inizializzazione RobotController")

        self._stop_event = threading.Event()
        
        # 1. Connessione al robot reale (singleton BLE, thread+loop asyncio propri)
        self.connector = Create3Connector()

        # 2. Origine delle coordinate: azzerata qui.
        #    DECISIONE VOSTRA: se il robot parte sempre agganciato al dock,
        #    aggiungete self.connector.undock() PRIMA di reset_navigation().
        #    Se lo posizionate a mano sul banco, saltate l'undock.
        self.connector.reset_navigation()

        self.vision_sensor = VisionSensor(self.VISION_SENSOR_NAME)  # invariato, legge solo Redis
        self.color_zone_sensor = ColorZoneSensor(self.connector, use_color=False)  # test odometria pura, telecamera non a bordo
        self.lidar_sensor = LidarSensor(self.connector)

        self.task_controller = TaskController(self.connector)



    def run(self):

        """Start the Body services and run the simulation control loop.

        The method starts the sensor and task-controller threads, creates the
        readiness marker used by the container health check, and advances the
        CoppeliaSim stepping loop until a shutdown signal is received.

        Args:
            None.

        Returns:
            None.
        """
        print(f"Main loop avviato a {self.LOOP_HZ}Hz.")
        
        # RIMUOVI il file di ready all'avvio, se esiste (da un avvio precedente)
        ready_file = "/tmp/body_ready"
        if os.path.exists(ready_file):
            os.remove(ready_file)
            print(f"⚠️  File di ready precedente rimosso: {ready_file}")

        #Avvio i thread dei sensori (che leggono e aggiornano Redis in background)
        self.color_zone_sensor.start()
        #self.lidar_sensor.start()

        self.task_controller.start()

        # TUTTI I THREAD SONO PRONTI - Creiamo un file di segnalazione per il health check
        ready_file = "/tmp/body_ready"
        open(ready_file, 'a').close()
        print(f"✅ Body completamente avviato. File di ready creato: {ready_file}")


        # Ogni thread è autonomo (proprio time.sleep interno): qui basta restare
        # vivi finché non arriva lo stop, nessun clock da far girare.
        while not self._stop_event.is_set():
            time.sleep(1.0 / self.LOOP_HZ)

        # Quando esce dal loop, fa il cleanup
        self.cleanup()
                

    def cleanup(self):
        """
        Stop all Body threads and release the simulation resources.

        Because CoppeliaSim runs in stepping mode, the method keeps advancing
        the simulation and the shared simulation clock in a temporary thread
        while sensors and controllers finish their shutdown commands. This
        prevents commands waiting for a simulation step from blocking the
        cleanup sequence.

        Args:
            None.

        Returns:
            None.
        """
        print("✅ Sto in cleanup: fermo i thread dei sensori e i controller...")
        self.task_controller.stop()
        self.color_zone_sensor.stop()
        self.lidar_sensor.stop()
        self.connector.disconnect()


def main():
    """Run the Body service and install graceful shutdown handlers.

    Args:
        None.

    Returns:
        None.
    """
    print("🔴 Main() avviato", flush=True)
    controller_ref = [None]

    def spegnimento_sicuro(signum, frame):
        """Request a graceful controller shutdown after an OS signal.

        Args:
            signum: Numeric identifier of the received signal.
            frame: Current stack frame provided by Python's signal handler.

        Returns:
            None.
        """
        print(f"\n[BODY] SIGTERM ricevuto!", flush=True)
        if controller_ref[0]:
            controller_ref[0]._stop_event.set()  # ← sblocca il loop → va in cleanup()

    signal.signal(signal.SIGTERM, spegnimento_sicuro)
    signal.signal(signal.SIGINT, spegnimento_sicuro)

    try:
        controller_ref[0] = RobotController()
        controller_ref[0].run()
    except Exception as e:
        print(f"Chiusura forzata: {e}")
        if controller_ref[0]:
            try:
                controller_ref[0].cleanup()
            except Exception as cleanup_err:
                print(f"Errore anche durante il cleanup di emergenza: {cleanup_err}")

if __name__ == "__main__":
    main()