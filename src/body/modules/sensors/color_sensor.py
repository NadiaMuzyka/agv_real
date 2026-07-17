from modules.connection.coppelia_connector import CoppeliaConnector
from modules.sensors.generic_sensor import GenericSensor
import threading

SENSORS_KEY = "body_memory"

class ColorSensor(GenericSensor):
    STEPS_PER_READ = 1   # 20Hz se il passo fisico è 50ms

    def __init__(self, name, clock):
        super().__init__(name)
        self.clock = clock

        self.connector = CoppeliaConnector(name=f"{self.name}")
        self.sim = self.connector.get_sim()

        try:
            self.handle = self.sim.getObject(self.name)
        except Exception as e:
            print(f"[{self.name}] ERRORE: Sensore non trovato in CoppeliaSim. Dettagli: {e}")
            self.handle = None

        self._running = False
        self._thread = None
        self.last_color = 0.0
        self.last_step_tag = None

    def start(self):
        if not self._running:
            self._running = True
            next_step = self.clock.register(self.name, self.STEPS_PER_READ)
            self._thread = threading.Thread(target=self._loop_lettura, args=(next_step,), daemon=True)
            self._thread.start()
            print(f"[{self.name}] Thread avviato.")

    def _loop_lettura(self, next_step):
        while self._running:
            actual = self.clock.wait_until(next_step)
            if not self._running:
                break
            self.read()
            self.last_step_tag = actual
            self.clock.ack(self.name)
            next_step = actual + self.STEPS_PER_READ

    def read(self):
        color_val = self.get_black_percentage()
        self.last_color = color_val
        return color_val

    def get_black_percentage(self):
        res, p1, p2 = self.sim.handleVisionSensor(self.handle)
        img, res = self.sim.getVisionSensorImg(self.handle)
        count = 0
        total_pixels = res[0] * res[1]
        for i in range(total_pixels):
            r = img[i*3]
            g = img[i*3 + 1]
            b = img[i*3 + 2]
            if r <= 30 and g <= 30 and b <= 30:
                count += 1
        return (count / total_pixels) if total_pixels > 0 else 0

    def stop(self):
        self._running = False
        self.clock.unregister(self.name)
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] Thread fermato.")