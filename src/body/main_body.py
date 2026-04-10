import time
import math
import json
import logging

from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.color_sensor import ColorSensor
from modules.actuators.wheel_actuator import WheelsActuator
from modules.redis_interface import RedisInterface 
from modules.controllers.low_level_manager import LowLevelManager

# Configurazione del Logging (Professionale)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [AGV Node] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class RobotController:
    """
    Gestisce la logica di alto livello del robot (Sensing, Decision, Action).
    """
    
    # --- COSTANTI DI CONFIGURAZIONE ---
    SENSORS_KEY = "agv_sensors"
    
    COLOR_LINE = (22, 22, 22)
    COLOR_OBSTACLE = (99, 255, 22)
    
    TOLERANCE_LINE = 50
    TOLERANCE_OBSTACLE = 40
    
    TARGET_SPEED = 0.1
    LOOP_HZ = 20
    
    def __init__(self):
        logger.info("Inizializzazione RobotController: Modalità PID 3 Sensori")
        
        # 1. Inizializzazione Connessioni (Coppelia & Redis)
        connector = CoppeliaConnector()
        self.sim = connector.get_sim()
        
        self.redis_iface = RedisInterface()
        if not self.redis_iface.db:
            logger.error("Redis non raggiungibile. Impossibile istanziare il controller.")
            raise ConnectionError("Redis connection failed")

        if not self.sim:
            logger.error("Impossibile connettersi a CoppeliaSim.")
            raise ConnectionError("CoppeliaSim connection failed")

        # 2. Inizializzazione Sottosistemi
        self.manager = LowLevelManager(self.sim) 
        self.wheels = WheelsActuator(self.sim)
        self.left_sensor = ColorSensor(self.sim, "/Robot/leftColorSensor")
        self.central_sensor = ColorSensor(self.sim, "/Robot/centralColorSensor") 
        self.right_sensor = ColorSensor(self.sim, "/Robot/rightColorSensor")
        
        # Sottoscrizione Redis
        self.pubsub = self.redis_iface.subscribe_to_commands()

        # Stato interno
        self.last_error = 0.0
        
        # Coda di navigazione fittizia per incroci (Simulazione Redis/Brain)
        self.mock_nav_queue = ["RIGHT", "LEFT","STOP"]
        self.active_intersection_cooldown = 0.0  # Frequenza per non triggherare più volte sullo stesso marker

    @staticmethod
    def _is_color_match(rgb, target, tolerance):
        """Verifica se il colore rientra nel target all'interno di un certo margine."""
        if not rgb:
            return False
        return all(abs(c - t) <= tolerance for c, t in zip(rgb, target))

    def _handle_obstacle_evasion(self):
        """Esegue la manovra prefissata per aggirare un ostacolo."""
        logger.warning("OSTACOLO RILEVATO! Avvio manovra evasiva...")
        
        # 1. Ferma e resetta il PID
        self.wheels.stop()
        self.manager.execute_command({"type": "STOP"})
        time.sleep(0.5)
        
        # 2. Ruota di 90 gradi a destra
        logger.info("Evasione 1/2: Rotazione a destra di 90°")
        w_target = -0.5
        duration = (math.pi / 2) / abs(w_target)
        self.wheels.move(0.0, w_target)
        time.sleep(duration)
        
        # 3. Avanza per superarlo
        logger.info("Evasione 2/2: Avanzamento di soppasso")
        self.wheels.move(self.TARGET_SPEED, 0.0)
        time.sleep(2.0)
        
        logger.info("Manovra completata. Ripristino stato PID.")
        self.wheels.stop()
        time.sleep(1.0)

    def _handle_intersection(self, direction: str):
        """Sospende il PID ed esegue una svolta svincolata (cieca) basata sulla coda."""
        logger.info(f"🛣️ Svincolo rilevato! Esecuzione istruzione da coda fittizia: {direction}")
        
        # Sospende i comandi PID
        self.wheels.stop()
        self.manager.execute_command({"type": "STOP"})
        
        if direction == "RIGHT":
            # 1. Spinge lo sterzo a destra per sgomberare l'alone dell'incrocio con moto di avanzamento
            logger.info("-> Svincolando a DESTRA. Prima fase open-loop...")
            self.wheels.move(0.05, -0.4)  # Modificato da 0.0 a 0.05 per curve smussate
            time.sleep(0.7)  # Calibra in base alla dimensione dell'intersezione
            
            # 2. Continua a muoversi in ciclo infinito leggendo il sensore centrale.
            # Appena la telecamera centrale intercetta di nuovo la linea nera, stoppa!
            logger.info("-> Cerco la nuova traiettoria e attendo riaggancio della traccia...")
            while True:
                rgb_c = self.central_sensor.read()
                if self._is_color_match(rgb_c, self.COLOR_LINE, self.TOLERANCE_LINE):
                    logger.info("Traccia riagganciata! Cedo controllo al PID.")
                    break
                time.sleep(0.02)
            self.wheels.stop()
            
        elif direction == "LEFT":
            logger.info("<- Svincolando a SINISTRA. Prima fase open-loop...")
            self.wheels.move(0.05, 0.4)   # Modificato da 0.0 a 0.05 per curve smussate
            time.sleep(0.7)
            logger.info("<- Cerco la nuova traiettoria e attendo riaggancio della traccia...")
            while True:
                rgb_c = self.central_sensor.read()
                if self._is_color_match(rgb_c, self.COLOR_LINE, self.TOLERANCE_LINE):
                    logger.info("Traccia riagganciata! Cedo controllo al PID.")
                    break
                time.sleep(0.02)
            self.wheels.stop()
            
        elif direction == "STRAIGHT":
            logger.info("^ Svincolando DRITTO. Ignoro eventuali appendici nere dei marker laterali.")
            self.wheels.move(self.TARGET_SPEED, 0.0)
            time.sleep(1.0)
            logger.info("Oltrepassato il marker centrale. Cedo controllo al PID.")
            
        elif direction == "STOP" or direction is None:
            logger.info("🛑 Destinazione Definitiva Raggiunta. In attesa di ordini.")
            self.wheels.stop()
            while True:
                time.sleep(1.0)

    def _compute_line_error(self, rgb_left, rgb_center, rgb_right) -> float:
        """Determina l'errore direzionale sui 3 sensori ottici."""
        on_line_l = self._is_color_match(rgb_left, self.COLOR_LINE, self.TOLERANCE_LINE)
        on_line_c = self._is_color_match(rgb_center, self.COLOR_LINE, self.TOLERANCE_LINE)
        on_line_r = self._is_color_match(rgb_right, self.COLOR_LINE, self.TOLERANCE_LINE)
        
        error = 0.0
        
        # --- TRIGGER INCROCIO ---
        # Accade quando i colleghi aggiungono mattoncini neri ai lati per innescare i sensori destro e sinistro.
        if on_line_l and on_line_c and on_line_r:
            return 999.0  # Usato come magic flag float (senza rompere i template PEP)
        
        if on_line_l and on_line_c:
            error = -0.25 # Correzione morbidissima per piccoli disallineamenti
        elif on_line_r and on_line_c:
            error = 0.25  # Correzione morbidissima per piccoli disallineamenti
        elif on_line_l:
            error = -1.0  # Curva stretta
        elif on_line_r:
            error = 1.0   # Curva stretta
        elif on_line_c:
            error = 0.0   # Perfettamente allineato
        else:
            # Sensori persi: raddoppiamo l'ultimo errore noto per non uscire dalla carreggiata
            error = 1.5 if self.last_error > 0 else (-1.5 if self.last_error < 0 else 0.0)
            
        self.last_error = error
        return error

    def _publish_telemetry(self, rgb_left, rgb_center, rgb_right):
        """Invia lo stato dei sensori a Redis per debug o controllo remoto."""
        sensor_data = {
            "color_left": rgb_left,
            "color_center": rgb_center,
            "color_right": rgb_right,
            "timestamp": time.time()
        }
        self.redis_iface.set_sensor_data(self.SENSORS_KEY, sensor_data)

    def run(self):
        """Ciclo di vita principale del componente Body."""
        logger.info(f"Main loop avviato a {self.LOOP_HZ}Hz.")
        loop_delay = 1.0 / self.LOOP_HZ
        
        try:
            while True:
                # --- 1. SENSING (Lettura Ingressi) ---
                rgb_l = self.left_sensor.read()
                rgb_c = self.central_sensor.read()
                rgb_r = self.right_sensor.read()
                
                # --- 2. GESTIONE OSTACOLI ---
                if self._is_color_match(rgb_c, self.COLOR_OBSTACLE, self.TOLERANCE_OBSTACLE):
                    self._handle_obstacle_evasion()
                    continue
                    
                # --- 3. CONTROLLO TRAIETTORIA E INCROCI ---
                error = self._compute_line_error(rgb_l, rgb_c, rgb_r)
                
                # Se il trigger incrocio è vero (999.0) ed è passato il delay di raffreddamento:
                if error == 999.0:
                    if time.time() > self.active_intersection_cooldown:
                        if len(self.mock_nav_queue) > 0:
                            direction = self.mock_nav_queue.pop(0)
                        else:
                            direction = "STOP"
                            
                        # --- HIGHLIGHT SU TERMINALE (Per Test) ---
                        logger.info("*" * 60)
                        logger.info(f"📍 INCROCIO RAGGIUNTO! Azione richiesta dalla Coda: >>> {direction} <<<")
                        logger.info(f"📋 Comandi residui in attesa: {self.mock_nav_queue}")
                        logger.info("*" * 60)
                        
                        self._handle_intersection(direction)
                        # Imposta cooldown di 1.5 secondi per ignorare la coda visiva del marker stesso
                        self.active_intersection_cooldown = time.time() + 1.5
                    continue
                
                # --- 4. TELEMETRIA ---
                self._publish_telemetry(rgb_l, rgb_c, rgb_r)
                
                # Ricezione messaggi da Brain disabilitata temporaneamente in modalità Autonoma/PID 
                # message = self.pubsub.get_message(ignore_subscribe_messages=True, timeout=0.001)

                # --- 5. ATTUAZIONE (Segnali Motori) ---
                # Se l'errore è estremo (linea persa), ferma l'avanzamento logico per fare un perno su sé stesso e cercare la linea
                current_speed = self.TARGET_SPEED if abs(error) < 1.5 else 0.0

                command = {
                    "type": "LINE_FOLLOW",
                    "error": error,
                    "target_speed": current_speed
                }
                
                v_target, w_target = self.manager.execute_command(command)
                self.wheels.move(v_target, w_target)
                
                # Wait per stabilità
                time.sleep(loop_delay)
                
        except KeyboardInterrupt:
            logger.warning("Interruzione manuale del Container rilevata.")
            self.wheels.stop()
        except Exception as e:
            logger.error(f"Eccezione critica nel ciclo: {e}", exc_info=True)
            self.wheels.stop()


def main():
    try:
        controller = RobotController()
        controller.run()
    except Exception as e:
        logger.critical(f"Chiusura forzata: {e}")

if __name__ == "__main__":
    main()