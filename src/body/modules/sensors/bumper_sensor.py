import random
from .generic_sensor import GenericSensor

class BumperSensor(GenericSensor):
    def __init__(self):
        super().__init__("Bumper")
        self.triggered = False

    def read(self):
        """
        Simulates reading the bumper sensor.
        In a real scenario, this would read GPIO pins.
        For simulation, we can assume it returns False unless externally set.
        """
        # For simulation purposes, we might want a way to trigger it.
        # For now, let's just return the internal state.
        return self.triggered

    def set_triggered(self, state: bool):
        """ Helper for simulation to manually trigger the bumper """
        self.triggered = state
