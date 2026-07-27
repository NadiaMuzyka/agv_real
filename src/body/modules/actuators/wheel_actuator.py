import time
import math

from modules.connection.coppelia_connector import CoppeliaConnector
from modules.actuators.generic_actuator import GenericActuator

class WheelsActuator(GenericActuator):
    def __init__(self, name="AGV_Wheels"):
        """Initialize the wheel actuator and resolve the drive handles.

        Args:
            name: Identifier assigned to the actuator and its dedicated
                CoppeliaSim connection.

        Returns:
            None.

        Raises:
            ConnectionError: May be raised by the CoppeliaSim connector when
                no simulator connection can be established.
        """
        super().__init__(name)
        
        
        # Connessione sicura e isolata per l'attuatore
        self.connector = CoppeliaConnector(name=f"conn_{self.name}")
        self.sim = self.connector.get_sim()
        
        # Physical data calibrated empirically
        self.wheel_radius = 0.1  
        # Iterative calibration for fine-tuning to compensate for 3D world friction and thickness.
        # Angle history 90°: 246° -> 99° -> 90.95°
        #self.wheelbase = 0.3126 
        self.wheelbase = 0.95
        try:
            self.m_as = self.sim.getObject('/Robot/leftMotor')
            self.m_ad = self.sim.getObject('/Robot/rightMotor')
            print(f"✅ [ACTUATOR] {self.name} inizializzato con i motori di Robot.")

            self.robot_handle = self.sim.getObject('/Robot')
            self.script_handle = self.sim.getScript(self.sim.scripttype_childscript, self.robot_handle)
        
        except Exception as e:
            print(f"⚠️ [ACTUATOR] Errore nel trovare i giunti: {e}")

    def move(self, v, w):
        """Apply differential-drive wheel velocities.

        The requested linear and angular velocities are converted into left
        and right wheel angular velocities using the configured wheel radius
        and wheelbase.

        Args:
            v: Linear velocity of the robot in metres per second.
            w: Angular velocity of the robot in radians per second.

        Returns:
            None.
        """
        v_l = (v - (w * self.wheelbase / 2)) / self.wheel_radius
        v_r = (v + (w * self.wheelbase / 2)) / self.wheel_radius
        
        self._apply_velocity(v_l, v_r)
        
    def move_for(self, v, w, duration):
        """Apply wheel velocities for a fixed simulation duration.

        Args:
            v: Linear velocity of the robot in metres per second.
            w: Angular velocity of the robot in radians per second.
            duration: Movement duration in seconds.

        Returns:
            None.
        """
        v_l = (v - (w * self.wheelbase / 2)) / self.wheel_radius
        v_r = (v + (w * self.wheelbase / 2)) / self.wheel_radius
        
        self._apply_velocity(v_l, v_r)

        start_time = self.sim.getSimulationTime()
        while self.sim.getSimulationTime() - start_time < duration:
            time.sleep(0.1)  # Controlla ogni 100ms

    def stop(self):
        """Stop both drive wheels immediately.

        Args:
            None.

        Returns:
            None.
        """
        self._apply_velocity(0.0, 0.0)

    def _apply_velocity(self, v_l, v_r):
        """Send left and right wheel velocities to CoppeliaSim.

        Args:
            v_l: Left wheel angular velocity in radians per second.
            v_r: Right wheel angular velocity in radians per second.

        Returns:
            None. Errors from the simulator call are logged and are not
            re-raised by this helper.
        """
        try:
            # Recall the internal Python function in Coppelia passing the motor handles and velocities
            self.sim.callScriptFunction(
                'set_dual_velocity', 
                self.script_handle, 
                self.m_as, self.m_ad, float(v_l), float(v_r)
            )
        except Exception as e:
            print(f"❌ [ACTUATOR] Errore nell'invio simultaneo via script: {e}")