import time
import logging
from typing import Tuple, Any, Dict, Optional

from .intersection_handler import IntersectionHandler

logger = logging.getLogger(__name__)

#Classe giocattolo 
class NavigationController:
    """
    Gestisce la logica decisionale e la strategia di navigazione del robot.

    Restituisce comandi ad alto livello per il `LowLevelManager` durante il
    line-following normale. Quando viene rilevato un incrocio (tutti e tre i
    sensori leggono la linea), delega a `IntersectionHandler` una manovra
    bloccante che esegue il posizionamento e la rotazione richiesta.
    """

    COLOR_LINE = (22, 22, 22)
    TOLERANCE_LINE = 50

    def __init__(self, target_speed: float,
                 sensor_offset_m: float = 0.70,
                 align_speed: float = 0.05,
                 rotation_speed: float = 0.5,
                 ignore_window_s: float = 0.15):
        self.target_speed = target_speed
        self.last_error = 0.0

        self.active_intersection_cooldown = 0.0

        # Handler dedicato per le manovre d'incrocio (incapsula la logica bloccante)
        self.intersection_handler = IntersectionHandler(
            sensor_offset_m=sensor_offset_m,
            align_speed=align_speed,
            rotation_speed=rotation_speed,
            ignore_window_s=ignore_window_s,
            color_line=self.COLOR_LINE,
            tolerance_line=self.TOLERANCE_LINE
        )

    @staticmethod
    def is_color_match(rgb: Tuple[int, int, int], target: Tuple[int, int, int], tolerance: int) -> bool:
        """Verifica se il colore rientra nel target all'interno di un certo margine."""
        if not rgb:
            return False
        return all(abs(int(c) - int(t)) <= tolerance for c, t in zip(rgb, target))

    def compute_line_state(self, rgb_left: Tuple[int, int, int], rgb_center: Tuple[int, int, int], rgb_right: Tuple[int, int, int]) -> Dict[str, Any]:
        """
        Determina lo stato della linea e l'errore direzionale.

        Restituisce un dict con chiavi:
          - 'state': 'INTERSECTION'|'LINE'|'OFF_LINE'
          - 'error': float
        """
        on_line_l = self.is_color_match(rgb_left, self.COLOR_LINE, self.TOLERANCE_LINE)
        on_line_c = self.is_color_match(rgb_center, self.COLOR_LINE, self.TOLERANCE_LINE)
        on_line_r = self.is_color_match(rgb_right, self.COLOR_LINE, self.TOLERANCE_LINE)

        # Incrocio: tutti e tre i sensori vedono la linea
        if on_line_l and on_line_c and on_line_r:
            return {"state": "INTERSECTION", "error": 0.0}

        error = 0.0

        if on_line_l and on_line_c:
            error = -0.25
        elif on_line_r and on_line_c:
            error = 0.25
        elif on_line_l:
            error = -1.0
        elif on_line_r:
            error = 1.0
        elif on_line_c:
            error = 0.0
        else:
            # Sensori persi: fallback basato sull'ultimo errore noto
            error = 1.5 if self.last_error > 0 else (-1.5 if self.last_error < 0 else 0.0)

        self.last_error = error

        state = "LINE" if (on_line_l or on_line_c or on_line_r) else "OFF_LINE"

        return {"state": state, "error": error}

    def process(self, rgb_l: Tuple[int, int, int], rgb_c: Tuple[int, int, int], rgb_r: Tuple[int, int, int],
                wheels: Any, manager: Any, central_sensor: Any, left_sensor: Any, right_sensor: Any) -> Optional[Dict[str, Any]]:
        """
        Motore decisionale. Valuta lo stato e restituisce un comando per il PID
        oppure delega la gestione bloccante degli incroci al `IntersectionHandler`.
        """
        # --- 1. TRAIETTORIA / STATO LINEA ---
        result = self.compute_line_state(rgb_l, rgb_c, rgb_r)
        state = result["state"]
        error = result["error"]

        # --- 2. INCROCI ---
        if state == "INTERSECTION":
            if time.time() > self.active_intersection_cooldown:
                if len(self.mock_nav_queue) > 0:
                    direction = self.mock_nav_queue.pop(0)
                else:
                    direction = "STOP"

                logger.info("*" * 60)
                logger.info(f"📍 INCROCIO RAGGIUNTO! Azione richiesta dalla Coda: >>> {direction} <<<")
                logger.info(f"📋 Comandi residui in attesa: {self.mock_nav_queue}")
                logger.info("*" * 60)

                # Assicuriamoci che il low-level sia fermo prima della manovra manuale
                wheels.stop()
                manager.execute_command({"type": "STOP"})

                # Esegui la manovra bloccante: align + rotate until central sensor sees new line
                self.intersection_handler.perform(direction, wheels, central_sensor, left_sensor, right_sensor)

                # cooldown visivo per non rileggere immediatamente lo stesso incrocio
                self.active_intersection_cooldown = time.time() + 1.5
            return None

        # --- 3. LINE FOLLOWING NORMALE ---
        current_speed = self.target_speed if abs(error) < 1.5 else 0.0
        return {
            "type": "LINE_FOLLOW",
            "error": error,
            "target_speed": current_speed
        }
