from modules.connection.coppelia_connector import CoppeliaConnector
from modules.actuators.generic_actuator import GenericActuator

class WheelsActuator(GenericActuator):
    def __init__(self, name="AGV_Wheels"):
        super().__init__(name)
        
        
        # Connessione sicura e isolata per l'attuatore
        self.connector = CoppeliaConnector(name=f"conn_{self.name}")
        self.sim = self.connector.get_sim()
        
        # Dati fisici calibrati empiricamente
        self.wheel_radius = 0.1  
        # Calibrazione iterativa ultra-fine per compensare l'attrito del mondo 3D e gli spessori.
        # Storia degli angoli 90°: 246° -> 99° -> 90.95°
        #self.wheelbase = 0.3126 
        self.wheelbase = 0.95
        try:
            self.m_as = self.sim.getObject('/Robot/leftMotor')
            self.m_ad = self.sim.getObject('/Robot/rightMotor')
            print(f"✅ [ACTUATOR] {self.name} inizializzato con i motori di Robot.")
        except Exception as e:
            print(f"⚠️ [ACTUATOR] Errore nel trovare i giunti: {e}")

    def move(self, v, w):
        """
        Calcola e applica le velocità ai giunti.
        v: velocità lineare (m/s)
        w: velocità angolare (rad/s)
        """
        v_l = (v - (w * self.wheelbase / 2)) / self.wheel_radius
        v_r = (v + (w * self.wheelbase / 2)) / self.wheel_radius
        
        self._apply_velocity(v_l, v_r)

    def stop(self):
        self._apply_velocity(0.0, 0.0)

    def _apply_velocity(self, v_l, v_r):
        try:
            robot_handle = self.sim.getObject('/Robot')
            script_handle = self.sim.getScript(self.sim.scripttype_childscript, robot_handle)
            
            # Richiamiamo la funzione Python interna a Coppelia passando gli handle dei motori e le velocità
            self.sim.callScriptFunction(
                'set_dual_velocity', 
                script_handle, 
                self.m_as, self.m_ad, float(v_l), float(v_r)
            )
        except Exception as e:
            print(f"❌ [ACTUATOR] Errore nell'invio simultaneo via script: {e}")