import time
import math

from modules.connection.coppelia_connector import CoppeliaConnector
from modules.actuators.generic_actuator import GenericActuator

class CartActuator(GenericActuator):
    def __init__(self, name="AGV_Cart"):
        super().__init__(name)
        
        
        # Connessione sicura e isolata per l'attuatore
        self.connector = CoppeliaConnector(name=f"conn_{self.name}")
        self.sim = self.connector.get_sim()
        
        # Dati fisici calibrati empiricamente

        try:
            self.motor = self.sim.getObject('/Robot/cartMotor')
            print(f"✅ [ACTUATOR] {self.name} inizializzato con i motori di Robot.")
        
        except Exception as e:
            print(f"⚠️ [ACTUATOR] Errore nel trovare i giunti: {e}")

    def open(self):
        print(f"🚀 [CartActuator] Sto per alzare la pinza.")
        angle = 0.0  # Angolo per aprire il carrello
        
        radianti = math.radians(angle)
        self.sim.setJointTargetPosition(self.motor, radianti)

        start_time = self.sim.getSimulationTime()
        while self.sim.getSimulationTime() - start_time < 20.0:  # Attendi 1 secondo per completare l'apertura
            time.sleep(0.1)  # Controlla ogni 100ms

    def close(self):
        print(f"🚀 [CartActuator] Sto per abbassare la pinza.")
        angle = 70.0  # Angolo per chiudere il carrello
        
        radianti = math.radians(angle)
        self.sim.setJointTargetPosition(self.motor, radianti)

        start_time = self.sim.getSimulationTime()
        while self.sim.getSimulationTime() - start_time < 20.0:  # Attendi 1 secondo per completare l'apertura
            time.sleep(0.1)  # Controlla ogni 100ms




