import time
import logging

logger = logging.getLogger(__name__)

class NavigationController:
    """
    Gestisce la logica decisionale e la strategia di navigazione del robot,
    mantenendo il modulo main pulito.
    """

    COLOR_LINE = (22, 22, 22)
    COLOR_OBSTACLE = (99, 255, 22)
    
    TOLERANCE_LINE = 50
    TOLERANCE_OBSTACLE = 40

    def __init__(self, target_speed: float):
        self.target_speed = target_speed
        self.last_error = 0.0
        
        # Coda di navigazione fittizia per incroci (Simulazione Redis/Brain)
        self.mock_nav_queue = ["RIGHT", "LEFT", "STOP"]
        self.active_intersection_cooldown = 0.0

    @staticmethod
    def is_color_match(rgb, target, tolerance):
        """Verifica se il colore rientra nel target all'interno di un certo margine."""
        if not rgb:
            return False
        return all(abs(c - t) <= tolerance for c, t in zip(rgb, target))

    def detect_obstacle(self, rgb_center) -> bool:
        """Controlla se il sensore centrale ha individuato un ostacolo."""
        return self.is_color_match(rgb_center, self.COLOR_OBSTACLE, self.TOLERANCE_OBSTACLE)

    def compute_line_error(self, rgb_left, rgb_center, rgb_right) -> float:
        """Determina l'errore direzionale sui 3 sensori ottici."""
        on_line_l = self.is_color_match(rgb_left, self.COLOR_LINE, self.TOLERANCE_LINE)
        on_line_c = self.is_color_match(rgb_center, self.COLOR_LINE, self.TOLERANCE_LINE)
        on_line_r = self.is_color_match(rgb_right, self.COLOR_LINE, self.TOLERANCE_LINE)
        
        error = 0.0
        
        # TRIGGER INCROCIO
        if on_line_l and on_line_c and on_line_r:
            return 999.0
        
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
            # Sensori persi: raddoppiamo l'ultimo errore noto per perno su se stesso
            error = 1.5 if self.last_error > 0 else (-1.5 if self.last_error < 0 else 0.0)
            
        self.last_error = error
        return error

    def _handle_obstacle_evasion(self, wheels, manager):
        """Esegue la manovra prefissata per aggirare un ostacolo."""
        logger.warning("OSTACOLO RILEVATO! Avvio manovra evasiva...")
        wheels.stop()
        manager.execute_command({"type": "STOP"})
        time.sleep(0.5)
        
        logger.info("Evasione 1/2: Rotazione a destra di 90°")
        wheels.move(0.0, -0.5)
        time.sleep(1.57) # ~90°
        
        logger.info("Evasione 2/2: Avanzamento di soppasso")
        wheels.move(self.target_speed, 0.0)
        time.sleep(2.0)
        
        logger.info("Manovra completata. Ripristino stato PID.")
        wheels.stop()
        time.sleep(1.0)

    def _handle_intersection(self, direction: str, wheels, manager, central_sensor, left_sensor, right_sensor):
        """Esegue una svolta all'incrocio superando fisicamente il marker spesso."""
        logger.info(f"🛣️ Svincolo rilevato! Esecuzione istruzione: {direction}")
        
        wheels.stop()
        manager.execute_command({"type": "STOP"})
        
        if direction == "RIGHT":
            logger.info("-> Fase 1: Rotazione per allineamento...")
            wheels.move(0.02, -0.5)  
            time.sleep(0.6)
            
            # Attende l'allineamento frontale
            while True:
                rgb_c = central_sensor.read()
                if self.is_color_match(rgb_c, self.COLOR_LINE, self.TOLERANCE_LINE):
                    break
                time.sleep(0.02)
                
            logger.info("-> Fase 2: Allineato! Avanzo per sgomberare l'area nera.")
            wheels.move(self.target_speed, 0.0)
            while True:
                rgb_l = left_sensor.read()
                rgb_r = right_sensor.read()
                if not self.is_color_match(rgb_l, self.COLOR_LINE, self.TOLERANCE_LINE) and \
                   not self.is_color_match(rgb_r, self.COLOR_LINE, self.TOLERANCE_LINE):
                    break
                time.sleep(0.02)
                
            logger.info("Traccia sgombra! Cedo controllo al PID.")
            wheels.stop()
            
        elif direction == "LEFT":
            logger.info("<- Fase 1: Rotazione per allineamento...")
            wheels.move(0.02, 0.5)   
            time.sleep(0.6)
            
            # Attende l'allineamento frontale
            while True:
                rgb_c = central_sensor.read()
                if self.is_color_match(rgb_c, self.COLOR_LINE, self.TOLERANCE_LINE):
                    break
                time.sleep(0.02)
                
            logger.info("<- Fase 2: Allineato! Avanzo per sgomberare l'area nera.")
            wheels.move(self.target_speed, 0.0)
            while True:
                rgb_l = left_sensor.read()
                rgb_r = right_sensor.read()
                if not self.is_color_match(rgb_l, self.COLOR_LINE, self.TOLERANCE_LINE) and \
                   not self.is_color_match(rgb_r, self.COLOR_LINE, self.TOLERANCE_LINE):
                    break
                time.sleep(0.02)
                
            logger.info("Traccia sgombra! Cedo controllo al PID.")
            wheels.stop()
            
        elif direction == "STRAIGHT":
            logger.info("^ Svincolando DRITTO. Ignoro marker laterali.")
            wheels.move(self.target_speed, 0.0)
            time.sleep(1.0)
            logger.info("Oltrepassato il marker centrale. Cedo controllo al PID.")
            
        elif direction == "STOP" or direction is None:
            logger.info("🛑 Destinazione Definitiva Raggiunta. In attesa di ordini.")
            wheels.stop()
            while True:
                time.sleep(1.0)

    def process(self, rgb_l, rgb_c, rgb_r, wheels, manager, central_sensor, left_sensor, right_sensor):
        """
        Motore decisionale. Valuta lo stato e restituisce un comando per il PID o gestisce loop interni bloccanti.
        """
        # --- 1. OSTACOLI ---
        if self.detect_obstacle(rgb_c):
            self._handle_obstacle_evasion(wheels, manager)
            return None
            
        # --- 2. TRAIETTORIA ---
        error = self.compute_line_error(rgb_l, rgb_c, rgb_r)
        
        # --- 3. INCROCI ---
        if error == 999.0:
            if time.time() > self.active_intersection_cooldown:
                if len(self.mock_nav_queue) > 0:
                    direction = self.mock_nav_queue.pop(0)
                else:
                    direction = "STOP"
                    
                logger.info("*" * 60)
                logger.info(f"📍 INCROCIO RAGGIUNTO! Azione richiesta dalla Coda: >>> {direction} <<<")
                logger.info(f"📋 Comandi residui in attesa: {self.mock_nav_queue}")
                logger.info("*" * 60)
                
                self._handle_intersection(direction, wheels, manager, central_sensor, left_sensor, right_sensor)
                # Imposta cooldown visivo, per ogni evenienza
                self.active_intersection_cooldown = time.time() + 1.5
            return None
            
        # --- 4. LINE FOLLOWING NORMALE ---
        current_speed = self.target_speed if abs(error) < 1.5 else 0.0
        return {
            "type": "LINE_FOLLOW",
            "error": error,
            "target_speed": current_speed
        }
