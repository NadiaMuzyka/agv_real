import time
import json
import logging

from modules.sensors.sensor_manager import SensorManager
from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.color_sensor import ColorSensor
from modules.controllers.pid_controller import PIDController
from modules.actuators.wheel_actuator import WheelsActuator

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

    LOOP_HZ = 20

    queue = ["RIGHT", "LEFT", "STOP"] #simulazione coda di navigazione (Redis/Brain)
    
    def __init__(self):
        logger.info("Inizializzazione RobotController")
        
        # 1. Connessioni
        #Mi connetto a CoppeliaSim tramite il Multiton CoppeliaConnector, che gestisce la connessione condivisa a CoppeliaSim.
        self.sim = CoppeliaConnector().get_sim()

        if not self.sim:
            logger.error("Impossibile connettersi a Coppelia.")
            raise ConnectionError("Coppelia err")


        #Hanno connessioni isolate a CoppeliaSim grazie al Multiton CoppeliaConnector
        self.left_sensor = ColorSensor(self.LEFT_SENSOR_NAME)
        self.central_sensor = ColorSensor(self.CENTRAL_SENSOR_NAME)
        self.right_sensor = ColorSensor(self.RIGHT_SENSOR_NAME)

        self.sensor_manager = SensorManager(sensor_names=[self.LEFT_SENSOR_NAME, self.CENTRAL_SENSOR_NAME, self.RIGHT_SENSOR_NAME])

        self.wheels_actuator = WheelsActuator() #Attuatore con connessione isolata a CoppeliaSim

        #Inizializzazione del PID
        self.pid_controller = PIDController(
            sensors_dict={
                'left': self.left_sensor,
                'center': self.central_sensor,
                'right': self.right_sensor
            },
            wheels_actuator=self.wheels_actuator
        )


    def run(self):

        """Ciclo di vita principale."""
        logger.info(f"Main loop avviato a {self.LOOP_HZ}Hz.")
        loop_delay = 1.0 / self.LOOP_HZ
        

        #Avvio i thread dei sensori (che leggono e aggiornano Redis in background)
        self.left_sensor.start()
        self.central_sensor.start()
        self.right_sensor.start()
        self.sensor_manager.start()

        self.pid_controller.start() #Avvio il thread del PID 

        try:
            while True:                
                
                time.sleep(loop_delay)
                
        except KeyboardInterrupt:
            logger.warning("Interruzione terminale.")

        except Exception as e:
            logger.error(f"Eccezione: {e}", exc_info=True)


def main():
    try:
        controller = RobotController()
        controller.run()
    except Exception as e:
        logger.critical(f"Chiusura forzata: {e}")

if __name__ == "__main__":
    main()