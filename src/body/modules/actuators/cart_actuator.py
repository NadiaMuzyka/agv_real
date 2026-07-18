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
        self._move_joint(0.0)

    def close(self):
        print(f"🚀 [CartActuator] Sto per abbassare la pinza.")
        self._move_joint(70.0)

    def _move_joint(self, angle_deg, retries=1):
        radianti = math.radians(angle_deg)
        for attempt in range(retries + 1):
            try:
                self.sim.setJointTargetPosition(self.motor, radianti)
                start_time = self.sim.getSimulationTime()
                while self.sim.getSimulationTime() - start_time < 20.0:
                    time.sleep(0.1)
                current = self.sim.getJointPosition(self.motor)
                print(f"✅ [CartActuator] Giunto impostato a {math.degrees(current):.2f}° (target: {angle_deg}°)")
                return
            except Exception as e:
                print(f"⚠️ [CartActuator] RPC fallita (tentativo {attempt+1}): {e}")
                self.sim = self.connector.connect()  # forza riconnessione

                if self.sim is None:
                    self.motor = None
        # se arrivi qui, tutti i tentativi sono falliti: segnala l'errore,
        # non far sparire il thread in silenzio
        raise RuntimeError(f"Impossibile muovere il cart a {angle_deg}° dopo {retries+1} tentativi") 



