from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.generic_sensor import GenericSensor
from modules.connection.redis_interface import RedisInterface 
import threading
import time
import json
import base64
import numpy as np
import cv2
import os


class PositionSensor(GenericSensor):
    def __init__(self, name, clock):
        # Richiama il costruttore della classe base (GenericSensor)
        super().__init__(name)
        
        # 1. Connessione a CoppeliaSim (Isolata e sicura grazie al Multiton)
        self.connector = CoppeliaConnector(name=f"position")
        self.sim = self.connector.get_sim()
        
        # Recuperiamo l'handle dell'oggetto da CoppeliaSim
        try:
            self.handle = self.sim.getObject(self.name)
        except Exception as e:
            print(f"[position] ERRORE: Sensore non trovato in CoppeliaSim. Dettagli: {e}")
            self.handle = None

        # 2. Connessione a Redis (Condivisa e sicura grazie al Singleton)
        self.redis_client = RedisInterface()
        if not self.redis_client.db:
            print(f"[position] Redis non raggiungibile.")
            raise ConnectionError("Redis err")
        
        self.last_data = {"detected": False, "distance": 999.0}

        # Sincronizzazione sul SimClock invece che su un timer reale: è un
        # partecipante GATING della barriera. Il main loop non avanza allo
        # step successivo finché questo sensore non ha completato read() e
        # confermato con ack() — così il contenuto letto corrisponde
        # garantito al tick per cui era stato richiesto, non a "qualunque
        # stato la fisica abbia raggiunto nel frattempo".
        self.clock = clock
        self.physical_dt = self.sim.getSimulationTimeStep()
        target_period_seconds = 0.1  # stesso target di prima (~10Hz)
        self.STEPS_PER_READ = max(1, round(target_period_seconds / self.physical_dt))

        self._running = False
        self._thread = None

        self.BODY_KEY = "body_memory"
        
    def start(self):
        """Avvia il thread del sensore."""
        if not self._running:
            self._running = True
            next_step = self.clock.register(self.name, self.STEPS_PER_READ)
            self._thread = threading.Thread(target=self._loop_lettura, args=(next_step,), daemon=True)
            self._thread.start()
            print(f"[{self.name}] Thread avviato.")

    def _loop_lettura(self, next_step):
        """Gira in background, gated sul tick: il main loop non avanza allo
        step successivo finché questo sensore non ha fatto ack()."""
        while self._running:
            actual = self.clock.wait_until(next_step)
            if not self._running:
                break
            self.read()
            self.clock.ack(self.name)
            next_step = actual + self.STEPS_PER_READ

    def read(self):
        """Scrive la posizione e orientamento nella body memory di redis"""
        
        if self.handle is None:
            print(f"[position] Errore: handle del sensore non valido.")
            return
        
        try:

            x, y, z = self.sim.getObjectPosition(self.handle)
            alpha, beta, gamma = self.sim.getObjectOrientation(self.handle)

            self.redis_client.update_sensor_data(self.BODY_KEY, {
                                        "x_pos": x,
                                        "y_pos": y,
                                        "orientation": gamma
                                    })
            
                
        except Exception as e:
            print(f"[position] Errore durante il rilevamento: {e}")


    def stop(self):
        """Ferma il thread in modo pulito."""
        self._running = False
        self.clock.unregister(self.name)
        if self._thread:
            self._thread.join()
            print(f"[position] Thread fermato.")