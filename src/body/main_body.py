import time
import os
import signal
import threading
import sys

from modules.sensors.sensor_manager import SensorManager
from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.color_sensor import ColorSensor
from modules.controllers.pid_controller import PIDController
from modules.controllers.task_controller import TaskController
from modules.sensors.vision_sensor import VisionSensor
from modules.sensors.apriltag_sensor import AprilTagSensor
from modules.sensors.lidar_sensor import LidarSensor

#docker compose up --build body


class RobotController:
    """
    Gestisce l'orchestrazione pura (Sensing hardware -> Action hardware)
    """
    
    # --- COSTANTI DI CONFIGURAZIONE ---
    LEFT_SENSOR_NAME = "/Robot/leftColorSensor"
    CENTRAL_SENSOR_NAME = "/Robot/centralColorSensor"
    RIGHT_SENSOR_NAME = "/Robot/rightColorSensor"
    VISION_SENSOR_NAME = "/Robot/visionSensor"
    APRILTAG_SENSOR_NAME = "/Robot/aprilTagSensor"
    LIDAR_SENSOR_NAME = "/Robot/lidarSensor"
    LOOP_HZ = 20

    queue = ["RIGHT", "LEFT", "STOP"] #simulazione coda di navigazione (Redis/Brain)
    
    def __init__(self):
        print("Inizializzazione RobotController")

        #self.task_controller.start() #Avvio il thread del TaskController (che legge i comandi dal Brain e gestisce la logica di alto livello)

        self._stop_event = threading.Event()
        
        # 1. Connessioni
        #Mi connetto a CoppeliaSim tramite il Multiton CoppeliaConnector, che gestisce la connessione condivisa a CoppeliaSim.
        self.sim = CoppeliaConnector().get_sim()

        if not self.sim:
            print("Impossibile connettersi a Coppelia.")
            raise ConnectionError("Coppelia err")
        
        self.sim.startSimulation()


        #Hanno connessioni isolate a CoppeliaSim grazie al Multiton CoppeliaConnector
        self.left_sensor = ColorSensor(self.LEFT_SENSOR_NAME)
        self.central_sensor = ColorSensor(self.CENTRAL_SENSOR_NAME)
        self.right_sensor = ColorSensor(self.RIGHT_SENSOR_NAME)
        self.vision_sensor = VisionSensor(self.VISION_SENSOR_NAME)
        self.sensor_manager = SensorManager()
        self.apriltag_sensor = AprilTagSensor(self.APRILTAG_SENSOR_NAME)
        self.lidar_sensor = LidarSensor(self.LIDAR_SENSOR_NAME)
        # self.high_lidar_sensor = LidarSensor(self.HIGH_LIDAR_SENSOR_NAME)

        self.pid = PIDController({"left": self.left_sensor, "center": self.central_sensor, "right": self.right_sensor})

        self.task_controller = TaskController(pid=self.pid)



    def run(self):

        """Ciclo di vita principale."""
        print(f"Main loop avviato a {self.LOOP_HZ}Hz.")
        loop_delay = 1.0 / self.LOOP_HZ
        
        # RIMUOVI il file di ready all'avvio, se esiste (da un avvio precedente)
        ready_file = "/tmp/body_ready"
        if os.path.exists(ready_file):
            os.remove(ready_file)
            print(f"⚠️  File di ready precedente rimosso: {ready_file}")

        #Avvio i thread dei sensori (che leggono e aggiornano Redis in background)
        self.left_sensor.start()
        self.central_sensor.start()
        self.right_sensor.start()
        #self.sensor_manager.start()
        self.apriltag_sensor.start()
        self.lidar_sensor.start()

        self.task_controller.start()
        
        # TUTTI I THREAD SONO PRONTI - Creiamo un file di segnalazione per il health check
        ready_file = "/tmp/body_ready"
        open(ready_file, 'a').close()
        print(f"✅ Body completamente avviato. File di ready creato: {ready_file}")


        # Loop principale: usa l'Event invece di sleep puro
        # wait() si sblocca immediatamente quando _stop_event viene settato
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=loop_delay)

        # Quando esce dal loop, fa il cleanup
        self.cleanup()
                

    def cleanup(self):
        """Pulizia ordinata di tutte le risorse."""
        self.left_sensor.stop()
        self.central_sensor.stop()
        self.right_sensor.stop()
        self.apriltag_sensor.stop()
        self.lidar_sensor.stop()
        #self.sensor_manager.stop()
        self.task_controller.stop()
        self.sim.stopSimulation()

        print("✅ Sto in cleanup: fermo i thread dei sensori...")


def main():
    print("🔴 VERSIONE NUOVA - main() avviato", flush=True)

    controller_ref = [None]

    def spegnimento_sicuro(signum, frame):
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

if __name__ == "__main__":
    main()