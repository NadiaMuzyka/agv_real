import time
import json
import logging

from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.color_sensor import ColorSensor
from modules.actuators.wheel_actuator import WheelsActuator
from modules.redis_interface import RedisInterface 
from modules.controllers.low_level_manager import LowLevelManager
from modules.controllers.navigation_controller import NavigationController

# Configurazione del Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [AGV Node] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class RobotController:
    """
    Gestisce l'orchestrazione pura (Sensing hardware -> Action hardware,
    delegando 100% della dinamica e traiettoria a NavigationController).
    """
    
    # --- COSTANTI DI CONFIGURAZIONE ---
    SENSORS_KEY = "agv_sensors"
    TARGET_SPEED = 0.05
    LOOP_HZ = 20
    
    def __init__(self):
        logger.info("Inizializzazione RobotController: Modalità orchestratore puro (SRP)")
        
        # 1. Connessioni
        connector = CoppeliaConnector()
        self.sim = connector.get_sim()
        
        self.redis_iface = RedisInterface()
        if not self.redis_iface.db:
            logger.error("Redis non raggiungibile.")
            raise ConnectionError("Redis err")

        if not self.sim:
            logger.error("Impossibile connettersi a Coppelia.")
            raise ConnectionError("Coppelia err")

        # 2. Sottosistemi Hardware
        self.manager = LowLevelManager(self.sim) 
        self.wheels = WheelsActuator(self.sim)
        self.left_sensor = ColorSensor(self.sim, "/Robot/leftColorSensor")
        self.central_sensor = ColorSensor(self.sim, "/Robot/centralColorSensor") 
        self.right_sensor = ColorSensor(self.sim, "/Robot/rightColorSensor")
        
        self.pubsub = self.redis_iface.subscribe_to_commands()

        # 3. Controller Mente Decisionale
        self.nav = NavigationController(target_speed=self.TARGET_SPEED)

    def _publish_telemetry(self, rgb_left, rgb_center, rgb_right):
        sensor_data = {
            "color_left": rgb_left,
            "color_center": rgb_center,
            "color_right": rgb_right,
            "timestamp": time.time()
        }
        self.redis_iface.set_sensor_data(self.SENSORS_KEY, sensor_data)

    def run(self):
        """Ciclo di vita principale."""
        logger.info(f"Main loop avviato a {self.LOOP_HZ}Hz.")
        loop_delay = 1.0 / self.LOOP_HZ
        
        try:
            while True:
                # --- 1. SENSING ---
                rgb_l = self.left_sensor.read()
                rgb_c = self.central_sensor.read()
                rgb_r = self.right_sensor.read()
                
                # --- 2. TELEMETRIA ---
                self._publish_telemetry(rgb_l, rgb_c, rgb_r)
                
                # --- 3. ELABORAZIONE DECISIONALE ---
                command = self.nav.process(
                    rgb_l, rgb_c, rgb_r, 
                    self.wheels, self.manager, 
                    self.central_sensor, self.left_sensor, self.right_sensor
                )
                
                # --- 4. ATTUAZIONE ---
                if command is not None:
                    v_target, w_target = self.manager.execute_command(command)
                    self.wheels.move(v_target, w_target)
                
                time.sleep(loop_delay)
                
        except KeyboardInterrupt:
            logger.warning("Interruzione terminale.")
            self.wheels.stop()
        except Exception as e:
            logger.error(f"Eccezione: {e}", exc_info=True)
            self.wheels.stop()

def main():
    try:
        controller = RobotController()
        controller.run()
    except Exception as e:
        logger.critical(f"Chiusura forzata: {e}")

if __name__ == "__main__":
    main()