import time
import json
import logging

from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.color_sensor import ColorSensor
from modules.actuators.wheel_actuator import WheelsActuator
from modules.controllers.low_level_manager import LowLevelManager
from modules.controllers.navigation_controller import NavigationController

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
    Gestisce l'orchestrazione pura (Sensing hardware -> Action hardware
    """
    
    # --- COSTANTI DI CONFIGURAZIONE ---
    SENSORS_KEY = "agv_sensors"
    TARGET_SPEED = 0.05
    LOOP_HZ = 20

    queue = ["RIGHT", "LEFT", "STOP"] #simulazione coda di navigazione (Redis/Brain)
    
    def __init__(self):
        logger.info("Inizializzazione RobotController")
        
        # 1. Connessioni
        #Mi connetto a CoppeliaSim tramite il Singleton CoppeliaConnector, che gestisce la connessione condivisa a CoppeliaSim.
        connector = CoppeliaConnector()
        #self.sim è l'oggetto che utilizzerò per interagire con le API di Coppelia in tutto il codice 
        self.sim = connector.get_sim()

        if not self.sim:
            logger.error("Impossibile connettersi a Coppelia.")
            raise ConnectionError("Coppelia err")
    

        # 2. Sottosistemi Hardware
        self.manager = LowLevelManager(self.sim) 
        self.left_sensor = ColorSensor(self.sim, "/Robot/leftColorSensor")
        self.central_sensor = ColorSensor(self.sim, "/Robot/centralColorSensor") 
        self.right_sensor = ColorSensor(self.sim, "/Robot/rightColorSensor")
        

        # 3. Controller Mente Decisionale
        self.nav = NavigationController(target_speed=self.TARGET_SPEED)


    def run(self):
        """Ciclo di vita principale."""
        logger.info(f"Main loop avviato a {self.LOOP_HZ}Hz.")
        loop_delay = 1.0 / self.LOOP_HZ

        #Avvio i thread dei sensori (che leggono e aggiornano Redis in background)
        self.left_sensor.start()
        self.central_sensor.start()
        self.right_sensor.start()
        
        try:
            while True:                
                
                # --- 2.1. GESTIONE CODA DI NAVIGAZIONE ---
                #Qui avverrà la lettura dei comandi di navigazione (simulati o reali da Redis/Brain)
                if self.queue:
                    command = self.queue.pop(0)
                else:
                    command = None

                '''
                # --- 4. ATTUAZIONE ---
                if command is not None:
                    v_target, w_target = self.manager.execute_command(command)
                    self.wheels.move(v_target, w_target)
                '''
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