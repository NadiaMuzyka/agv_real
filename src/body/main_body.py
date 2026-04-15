import time
import json
import logging

from modules.sensors.sensor_manager import SensorManager
from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.color_sensor import ColorSensor
from modules.controllers.low_level_manager import LowLevelManager

#docker compose up --build body

# Configurazione del Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [AGV Node] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class RobotController:
    """
    Gestisce l'orchestrazione pura (Sensing hardware -> Action hardware)
    """
    
    # --- COSTANTI DI CONFIGURAZIONE ---
    LEFT_SENSOR_NAME = "/Robot/leftColorSensor"
    CENTRAL_SENSOR_NAME = "/Robot/centralColorSensor"
    RIGHT_SENSOR_NAME = "/Robot/rightColorSensor"

    queue = ["RIGHT", "LEFT", "STOP"] #simulazione coda di navigazione (Redis/Brain)
    
    def __init__(self):
        logger.info("Inizializzazione RobotController")
        
        # 1. Connessioni
        #Mi connetto a CoppeliaSim tramite il Multiton CoppeliaConnector, che gestisce la connessione condivisa a CoppeliaSim.
        self.sim = CoppeliaConnector().get_sim()

        if not self.sim:
            logger.error("Impossibile connettersi a Coppelia.")
            raise ConnectionError("Coppelia err")
    

        # 2. Sottosistemi Hardware
        self.manager = LowLevelManager(self.sim) 

        #Hanno connessioni isolate a CoppeliaSim grazie al Multiton CoppeliaConnector
        self.left_sensor = ColorSensor(self.LEFT_SENSOR_NAME)
        self.central_sensor = ColorSensor(self.CENTRAL_SENSOR_NAME)
        self.right_sensor = ColorSensor(self.RIGHT_SENSOR_NAME)

        self.sensor_manager = SensorManager(sensor_names=[self.LEFT_SENSOR_NAME, self.CENTRAL_SENSOR_NAME, self.RIGHT_SENSOR_NAME])


    def run(self):

        #Avvio i thread dei sensori (che leggono e aggiornano Redis in background)
        self.left_sensor.start()
        self.central_sensor.start()
        self.right_sensor.start()
        self.sensor_manager.start()


def main():
    try:
        controller = RobotController()
        controller.run()
    except Exception as e:
        logger.critical(f"Chiusura forzata: {e}")

if __name__ == "__main__":
    main()