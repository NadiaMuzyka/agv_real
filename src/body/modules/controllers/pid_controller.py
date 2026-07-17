import threading
import time
from modules.connection.coppelia_connector import CoppeliaConnector

from modules.controllers.manuever_controller import ManueverController


class DiscretePID:
    """
    Controller PID discreto in forma parallela, come nel modello Matlab
    (oggetto `pid`, vedi documentazione Control System Toolbox):

        C = Kp + Ki * IF(z) + Kd / (Tf + DF(z))

    con IF(z) = DF(z) = Ts / (z - 1)   (ForwardEuler, opzione di default in Matlab).

    Equazioni alle differenze corrispondenti (derivate discretizzando C
    con ForwardEuler, non "inventate" a mano):

        Integrale:          I(k) = I(k-1) + Ki * Ts * e(k-1)
        Derivata filtrata:  D(k) = alpha * D(k-1) + beta * (e(k) - e(k-1))
                             con alpha = (Tf - Ts) / Tf ,  beta = Kd / Tf
        Uscita:             u(k) = Kp*e(k) + I(k) + D(k)   (poi saturata)

    Tf è la costante di tempo del filtro derivativo (analoga a Tf nell'oggetto
    `pid` di Matlab). Se non la passi esplicitamente, viene derivata da
    n_filter come Tf = Ts * n_filter (più n_filter è grande, più il filtro è
    "lento"/aggressivo nel tagliare il rumore ad alta frequenza).
    """

    def __init__(self, kp, ki, kd, ts, tf=None, n_filter=10.0,
                 out_min=None, out_max=None):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.ts = ts  # Ts nominale, usato solo se non viene passato un dt reale a step()

        # Tf deve essere > Ts perché alpha resti in [0,1) e il filtro sia stabile
        self.tf = tf if tf is not None else max(ts * n_filter, ts * 1.01)

        self.out_min = out_min
        self.out_max = out_max

        self.integral = 0.0
        self.d_filtered = 0.0
        self.prev_error = 0.0
        self._initialized = False

    def reset(self):
        """Azzera lo stato interno (da chiamare ad ogni start() del controllore)."""
        self.integral = 0.0
        self.d_filtered = 0.0
        self.prev_error = 0.0
        self._initialized = False

    def step(self, error, dt=None):
        """
        Esegue un passo del PID discreto.
        :param error: e(k), l'errore corrente
        :param dt: tempo di campionamento reale del passo corrente (Ts). Se None
                    usa self.ts nominale.
        """
        ts = dt if (dt is not None and dt > 0) else self.ts

        if not self._initialized:
            # Al primissimo passo non esiste un e(k-1) affidabile: lo inizializziamo
            # con l'errore corrente per evitare un picco spurio di derivata/integrale.
            self.prev_error = error
            self._initialized = True

        p_term = self.kp * error

        # --- Integrale (ForwardEuler): I(k) = I(k-1) + Ki*Ts*e(k-1) ---
        integral_candidate = self.integral + self.ki * ts * self.prev_error

        # --- Derivata filtrata (ForwardEuler) ---
        alpha = (self.tf - ts) / self.tf
        beta = self.kd / self.tf
        d_term = alpha * self.d_filtered + beta * (error - self.prev_error)

        unsaturated = p_term + integral_candidate + d_term
        output = unsaturated
        if self.out_min is not None:
            output = max(self.out_min, output)
        if self.out_max is not None:
            output = min(self.out_max, output)

        # --- Anti-windup (clamping) ---
        # Se l'uscita è saturata e l'integratore la spingerebbe ulteriormente
        # nella stessa direzione di saturazione, non aggiorniamo l'integrale.
        # Senza questo, un Ki != 0 con saturazione andrebbe in windup (esattamente
        # il tipo di drift che vi aveva fatto disattivare Ki nella versione precedente).
        saturated_high = self.out_max is not None and output >= self.out_max
        saturated_low = self.out_min is not None and output <= self.out_min
        pushing_further = (saturated_high and integral_candidate > self.integral) or \
                           (saturated_low and integral_candidate < self.integral)

        if not pushing_further:
            self.integral = integral_candidate

        self.d_filtered = d_term
        self.prev_error = error

        return output


class PIDController:
    STEPS_PER_CONTROL = 1

    def __init__(self, sensors_dict, clock, base_speed=0.05):
        self.sensors = sensors_dict
        self.clock = clock
        self.base_speed = base_speed

        self.manuever_controller = ManueverController(None, clock)

        self._left_name = sensors_dict["left"].name
        self._right_name = sensors_dict["right"].name
        self._physical_dt = self.manuever_controller.physical_dt

        self.pid = DiscretePID(
            kp=0.35, ki=0.0, kd=0.35,
            ts=self._physical_dt,
            n_filter=10.0,
            out_min=None, out_max=None,
        )

        self.v = 0.0
        self.w = 0.0
        self.reverse = False
        self._running = False
        self._thread = None

    def start(self, reverse=False):
        if not self._running:
            self._running = True
            self.pid.reset()
            next_step = self.clock.register("pid_controller", self.STEPS_PER_CONTROL)
            self._thread = threading.Thread(target=self._loop_controllo, args=(reverse, next_step), daemon=True)
            self._thread.start()
            print("[PID] Thread avviato.")

    def _loop_controllo(self, reverse=False, next_step=None):
        self.reverse = reverse
        last_step = next_step - self.STEPS_PER_CONTROL

        while self._running:
            actual = self.clock.wait_until(next_step)
            if not self._running:
                break

            self.clock.wait_for([self._left_name, self._right_name], actual)

            dt = (actual - last_step) * self._physical_dt

            l_rgb = self.sensors['left'].last_color
            r_rgb = self.sensors['right'].last_color
            error = self._calculate_error(l_rgb, r_rgb)

            self.w = -self.pid.step(error, dt)
            v_target = self.base_speed * max(0.2, 1 - abs(error))
            max_delta_v = 0.01
            delta_v = max(-max_delta_v, min(max_delta_v, v_target - self.v))
            self.v += delta_v

            print(f"[PID] step={actual} error={error:.4f} w={self.w:.4f} v={self.v:.4f}")

            if reverse:
                self.manuever_controller.set_velocity(-self.v, -self.w)
            else:
                self.manuever_controller.set_velocity(self.v, self.w)

            self.clock.ack("pid_controller")
            last_step = actual
            next_step = actual + self.STEPS_PER_CONTROL

    def _calculate_error(self, l, r):
        return (r - l)

    def stop(self):
        self._running = False
        self.clock.unregister("pid_controller")
        try:
            direction = -1 if self.reverse else 1
            self.manuever_controller.set_velocity_for(0.05*direction, 0.0, 0.3 if not self.reverse else 0.4)
            self.manuever_controller.stop()
            print("[PID] Thread fermato e motori bloccati.")
        except Exception as e:
            print(f"⚠️ [PID] Errore in stop: {e}")
        if self._thread:
            self._thread.join(timeout=0.5)