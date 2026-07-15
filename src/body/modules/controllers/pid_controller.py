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
    def __init__(self, sensors_dict, base_speed=0.05):
        """
        :param sensors_dict: Dizionario con le istanze dei sensori {'left': obj, 'center': obj, 'right': obj}
        """
        self.sensors = sensors_dict
        self.base_speed = base_speed

        # Connessione ZMQ dedicata e isolata (come i sensori), NON la connessione
        # condivisa del thread principale: i socket ZMQ non sono thread-safe, e
        # condividerla con main_body.py (che chiama step() in continuazione)
        # causa "Operation cannot be accomplished in current state".
        self.connector = CoppeliaConnector(name="pid_controller")
        self.sim = self.connector.get_sim()

        self.manuever_controller = ManueverController(None)

        self.frequenza_controllo = 0.05  # Ts nominale (20 Hz)

        # PID discreto sull'errore laterale (l'uscita è direttamente w).
        # Ki e Kd partono a 0 come nella versione precedente: attivateli quando
        # volete introdurre integrale/derivata, la struttura è già pronta e
        # corretta secondo il modello Matlab (basta cambiare i guadagni qui sotto).
        # out_min/out_max: mettete i limiti fisici reali della vostra w prima di
        # usare Ki != 0, altrimenti l'anti-windup non ha niente su cui agire.
        self.pid = DiscretePID(
            kp=0.25,
            ki=0.0,
            kd=0.25,
            ts=self.frequenza_controllo,
            n_filter=10.0,
            out_min=None,
            out_max=None,
        )

        # Output cinematico per gli attuatori
        self.v = 0.0
        self.w = 0.0

        # Gestione Thread
        self._running = False
        self._thread = None

    def start(self, reverse=False):
        """Avvia il thread del PID."""
        if not self._running:
            self._running = True
            self.pid.reset()
            self._thread = threading.Thread(target=self._loop_controllo, args=(reverse,), daemon=True)
            self._thread.start()
            print("[PID] Thread avviato.")

    def _loop_controllo(self, reverse=False):
        """Metodo privato che gira in background nel thread."""
        last_time = self.sim.getSimulationTime()  # Usa il tempo di simulazione di CoppeliaSim

        while self._running:
            now = self.sim.getSimulationTime()
            dt = now - last_time
            if dt <= 0:
                time.sleep(0.001)  # Piccola pausa per evitare loop troppo veloce
                continue

            # 1. Lettura diretta dalla RAM dei sensori
            l_rgb = self.sensors['left'].last_color
            c_rgb = self.sensors['center'].last_color
            r_rgb = self.sensors['right'].last_color

            error = self._calculate_error(l_rgb, c_rgb, r_rgb)

            print(f"[PID] errore: {error}")

            # 2. PID discreto (modello Matlab, forma parallela, ForwardEuler).
            # Il segno "-" mantiene la stessa convenzione della versione precedente
            # (target_w = -(kp*error) - ...): se il nero si sposta a destra
            # (error > 0) il robot deve girare nella direzione opposta.
            self.w = -self.pid.step(error, dt)

            # 3. Velocità lineare: rallenta nelle curve strette in base all'errore.
            # Logica invariata rispetto a prima: non fa parte del modello PID,
            # è uno scheduling indipendente della v.
            v_target = self.base_speed * max(0.2, 1 - abs(error))
            max_delta_v = 0.01  # variazione massima di v per ciclo, da tarare
            delta_v = v_target - self.v
            delta_v = max(-max_delta_v, min(max_delta_v, delta_v))
            self.v = self.v + delta_v

            # 4. Comando ai motori
            if reverse:
                self.manuever_controller.set_velocity(-self.v, -self.w)
            else:
                self.manuever_controller.set_velocity(self.v, self.w)

            last_time = now
            time.sleep(self.frequenza_controllo)

    def _calculate_error(self, l, c, r):
        """Mappatura discreta -> Errore continuo."""
        return (r - l)

    def stop(self):
        """Ferma il thread in modo pulito."""
        self._running = False
        try:
            self.manuever_controller.set_velocity(0.0, 0.0)  # Con lock, safe
            print("[PID] Thread fermato e motori bloccati.")
        except Exception as e:
            print(f"⚠️ [PID] Errore in stop: {e}")
        if self._thread:
            self._thread.join(timeout=0.5)  # Aspetta che il thread finisca