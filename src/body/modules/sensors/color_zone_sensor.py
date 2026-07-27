import threading
import time
import json
import os
import cv2
import numpy as np
from modules.connection.redis_interface import RedisInterface
from modules.controllers.position_controller import PositionController


class ColorZoneSensor:
    # Range HSV — PLACEHOLDER, DA CALIBRARE con l'illuminazione reale e i
    # fogli A4 veri. Il rosso serve in due pezzi perché in HSV avvolge 0/180.
    RANGE_COLORI = {
        "rosso":  [((0, 100, 100), (10, 255, 255)), ((170, 100, 100), (180, 255, 255))],
        "verde":  [((45, 80, 80), (75, 255, 255))],
        "giallo": [((20, 100, 100), (35, 255, 255))],
        "ciano":  [((85, 100, 100), (100, 255, 255))],
        "nero":   [((0, 0, 0), (180, 255, 50))],
    }
    COLOR_MATCH_THRESHOLD = 0.5    # frazione dell'immagine (0-1) che deve essere di quel colore
    POSITION_TOLERANCE_CM = 15.0   # PLACEHOLDER: adattate alla dimensione dei fogli A4

    def __init__(self, connector, camera_index=0):
        self.connector = connector
        self.redis_client = RedisInterface()
        if not self.redis_client.db:
            raise ConnectionError("[color_zone] Redis err")

        self.BRAIN_KEY = "brain_memory"
        self.camera_index = camera_index
        self.webcam = None
        self._running = False
        self._thread = None

        self.position_controller = PositionController()
        color_map_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "node_color_map.json")
        with open(color_map_path) as f:
            self.node_color_map = json.load(f)

        self.frequenza_lettura = 0.05  # ~20 Hz

    def start(self):
        if not self._running:
            self.webcam = cv2.VideoCapture(self.camera_index)
            self._running = True
            self._thread = threading.Thread(target=self._loop_lettura, daemon=True)
            self._thread.start()
            print("[color_zone] Sensore colore avviato.")

    def _loop_lettura(self):
        while self._running and self.webcam.isOpened():
            ret, frame = self.webcam.read()
            if ret:
                self.read(frame)
            time.sleep(self.frequenza_lettura)

    def read(self, frame):
        try:
            candidato = self._nodo_candidato()
            if candidato is None:
                self.redis_client.update_sensor_data(self.BRAIN_KEY, {"am_i_in_a_node": False})
                return

            atteso = self.node_color_map.get(candidato)
            if atteso and self._colore_visibile(frame, atteso):
                self.redis_client.update_sensor_data(self.BRAIN_KEY, {
                    "am_i_in_a_node": True,
                    "current_position": candidato,
                })
            else:
                self.redis_client.update_sensor_data(self.BRAIN_KEY, {"am_i_in_a_node": False})

        except Exception as e:
            print(f"[color_zone] Errore elaborazione colore: {e}")

    def _nodo_candidato(self):
        """Nodo più vicino secondo l'odometria del Create3, entro tolleranza.
        Usa solo x, y (l'orientamento del robot non conta qui)."""
        pos = self.connector.get_position()
        if pos is None:
            return None
        x, y, _heading = pos

        migliore, dist_migliore = None, None
        for nodo, (nx, ny) in self.position_controller.POSITION_TABLE.items():
            d = ((x - nx) ** 2 + (y - ny) ** 2) ** 0.5
            if dist_migliore is None or d < dist_migliore:
                migliore, dist_migliore = nodo, d

        if dist_migliore is not None and dist_migliore <= self.POSITION_TOLERANCE_CM:
            return migliore
        return None

    def _colore_visibile(self, frame, colore):
        """Percentuale dell'immagine coperta da quel colore, non conteggio assoluto:
        la camera è a 2-3cm da terra e vede solo il foglio A4, quindi la frazione
        dell'inquadratura è la misura giusta, non un'area in pixel."""
        hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask_totale = np.zeros(hsv_frame.shape[:2], dtype=np.uint8)
        for lo, hi in self.RANGE_COLORI.get(colore, []):
            mask_totale |= cv2.inRange(hsv_frame, np.array(lo), np.array(hi))

        percentuale = np.count_nonzero(mask_totale) / mask_totale.size
        return percentuale >= self.COLOR_MATCH_THRESHOLD

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        if self.webcam:
            self.webcam.release()
        print("[color_zone] Telecamera rilasciata.")