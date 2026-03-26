from modules.actuators.generic_actuator import GenericActuator

class WheelsActuator(GenericActuator):
    def __init__(self, sim, name="AGV_Wheels"):
        super().__init__(name)
        self.sim = sim
        
        # Dati fisici (Diametro 20cm, Interasse 50cm)
        self.wheel_radius = 0.1  
        self.wheelbase = 0.5     
        
        try:
            # Percorsi basati sulla tua gerarchia in CoppeliaSim
            self.m_ps = self.sim.getObject('/Robot/JointPS')
            self.m_as = self.sim.getObject('/Robot/JointAS')
            self.m_pd = self.sim.getObject('/Robot/JointPD')
            self.m_ad = self.sim.getObject('/Robot/JointAD')
            print(f"✅ [ACTUATOR] {self.name} inizializzato con i 4 giunti.")
        except Exception as e:
            print(f"⚠️ [ACTUATOR] Errore nel trovare i giunti: {e}")

    def move(self, v, w):
        """
        Calcola e applica le velocità ai giunti.
        v: velocità lineare (m/s)
        w: velocità angolare (rad/s)
        """
        # Cinematica per robot a trazione differenziale
        v_l = (v - (w * self.wheelbase / 2)) / self.wheel_radius
        v_r = (v + (w * self.wheelbase / 2)) / self.wheel_radius
        
        self._apply_velocity(v_l, v_r)

    def stop(self):
        self._apply_velocity(0.0, 0.0)

    def _apply_velocity(self, v_l, v_r):
        try:
            self.sim.setJointTargetVelocity(self.m_ps, v_l)
            self.sim.setJointTargetVelocity(self.m_as, v_l)
            self.sim.setJointTargetVelocity(self.m_pd, v_r)
            self.sim.setJointTargetVelocity(self.m_ad, v_r)
        except Exception as e:
            print(f"❌ [ACTUATOR] Errore setJointTargetVelocity: {e}")