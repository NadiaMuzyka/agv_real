import time
import os

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
    LIDAR_SENSOR_NAME = "Lidar"
    LOOP_HZ = 20

    queue = ["RIGHT", "LEFT", "STOP"] #simulazione coda di navigazione (Redis/Brain)
    
    def __init__(self):
        print("Inizializzazione RobotController")

        #self.task_controller.start() #Avvio il thread del TaskController (che legge i comandi dal Brain e gestisce la logica di alto livello)

        
        # 1. Connessioni
        #Mi connetto a CoppeliaSim tramite il Multiton CoppeliaConnector, che gestisce la connessione condivisa a CoppeliaSim.
        self.sim = CoppeliaConnector().get_sim()

        if not self.sim:
            print("Impossibile connettersi a Coppelia.")
            raise ConnectionError("Coppelia err")


        #Hanno connessioni isolate a CoppeliaSim grazie al Multiton CoppeliaConnector
        self.left_sensor = ColorSensor(self.LEFT_SENSOR_NAME)
        self.central_sensor = ColorSensor(self.CENTRAL_SENSOR_NAME)
        self.right_sensor = ColorSensor(self.RIGHT_SENSOR_NAME)
        self.vision_sensor = VisionSensor(self.VISION_SENSOR_NAME)
        self.sensor_manager = SensorManager()
        self.apriltag_sensor = AprilTagSensor(self.APRILTAG_SENSOR_NAME)
        self.lidar_sensor = LidarSensor(self.LIDAR_SENSOR_NAME)
        

        self.pid = PIDController({"left": self.left_sensor, "center": self.central_sensor, "right": self.right_sensor})

        self.task_controller = TaskController(pid=self.pid)



    def run(self):

        """Ciclo di vita principale."""
        print(f"Main loop avviato a {self.LOOP_HZ}Hz.")
        loop_delay = 1.0 / self.LOOP_HZ
        

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

        try:
            while True:                
                
                time.sleep(loop_delay)
                
        except KeyboardInterrupt:
            print("Interruzione terminale.")
            if os.path.exists(ready_file):
                os.remove(ready_file)

        except Exception as e:
            print(f"Eccezione: {e}", exc_info=True)


def main():
    try:
        controller = RobotController()
        controller.run()
    except Exception as e:
        print(f"Chiusura forzata: {e}")

if __name__ == "__main__":
    main()