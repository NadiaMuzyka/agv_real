import time
import logging
from typing import Any, Tuple

logger = logging.getLogger(__name__)

#Classe giocattolo
class IntersectionHandler:
    """
    Gestisce la manovra di svolta agli incroci.
    Esegue:
      - avanzamento di allineamento (distance = sensor_offset_m)
      - rotazione ignorando letture per ignore_window_s
      - continua a ruotare finché il sensore centrale non rileva la nuova linea
    """
    def __init__(self,
                 sensor_offset_m: float = 0.70,
                 align_speed: float = 0.05,
                 rotation_speed: float = 0.5,
                 ignore_window_s: float = 0.15,
                 color_line: Tuple[int, int, int] = (22,22,22),
                 tolerance_line: int = 50):
        self.sensor_offset_m = sensor_offset_m
        self.align_speed = align_speed
        self.rotation_speed = rotation_speed
        self.ignore_window_s = ignore_window_s
        self.COLOR_LINE = color_line
        self.TOLERANCE_LINE = tolerance_line

    @staticmethod
    def is_color_match(rgb: Tuple[int, int, int], target: Tuple[int, int, int], tolerance: int) -> bool:
        if not rgb:
            return False
        return all(abs(int(c) - int(t)) <= tolerance for c, t in zip(rgb, target))

    def perform(self,
                direction: str,
                wheels: Any,
                central_sensor: Any,
                left_sensor: Any = None,
                right_sensor: Any = None) -> None:
        """
        Esegue la sequenza di svolta per la direzione richiesta.
        Questa funzione è bloccante e prende il controllo diretto sui `wheels`.
        """
        logger.info("IntersectionHandler: inizio manovra '%s'", direction)

        # 1) Align: avanzare di sensor_offset_m a velocità align_speed
        if self.sensor_offset_m > 0 and self.align_speed > 0:
            duration = self.sensor_offset_m / self.align_speed
            logger.debug("Allineamento: avanzo %.3fm a %.3fm/s (%.2fs)", self.sensor_offset_m, self.align_speed, duration)
            wheels.move(self.align_speed, 0.0)
            time.sleep(duration)
            wheels.stop()
            time.sleep(0.05)

        # 2) Rotate: ruotare su se stesso nella direzione voluta
        w = -self.rotation_speed if direction == "RIGHT" else (self.rotation_speed if direction == "LEFT" else 0.0)
        if direction == "STRAIGHT":
            # semplicemente avanzare oltre il marker
            logger.debug("STRAIGHT: avanzamento di attraversamento")
            wheels.move(self.align_speed, 0.0)
            time.sleep(0.5)
            wheels.stop()
            return

        if direction == "STOP" or direction is None:
            logger.info("IntersectionHandler: STOP richiesto, fermo motori.")
            wheels.stop()
            return

        # Inizio rotazione
        logger.debug("Inizio rotazione (w=%.3f) con ignore_window=%.3fs", w, self.ignore_window_s)
        wheels.move(0.0, w)
        # Ignora letture iniziali (finestra per stabilizzare il movimento)
        time.sleep(self.ignore_window_s)

        # Strategia corretta:
        # 1) aspetta che il sensore centrale esca dall'area nera iniziale (intersection)
        # 2) poi continua a ruotare finché il sensore centrale non rileva la nuova linea
        rotate_start = time.time()
        timeout = max(5.0, self.sensor_offset_m / max(1e-3, self.align_speed) * 2)

        try:
            # 1) attendi uscita dall'area nera
            while True:
                rgb_c = central_sensor.read()
                if not self.is_color_match(rgb_c, self.COLOR_LINE, self.TOLERANCE_LINE):
                    break
                if time.time() - rotate_start > timeout:
                    logger.warning("IntersectionHandler: timeout durante uscita dall'area nera; proseguo alla fase successiva.")
                    break
                time.sleep(0.01)

            # 2) attendi il rilevamento della nuova linea (perpendicolare)
            detect_start = time.time()
            while True:
                rgb_c = central_sensor.read()
                if self.is_color_match(rgb_c, self.COLOR_LINE, self.TOLERANCE_LINE):
                    break
                if time.time() - detect_start > timeout:
                    logger.warning("IntersectionHandler: timeout durante ricerca nuova linea; termino la rotazione.")
                    break
                time.sleep(0.01)
        finally:
            wheels.stop()
            time.sleep(0.05)
            logger.info("IntersectionHandler: Manovra completata.")
