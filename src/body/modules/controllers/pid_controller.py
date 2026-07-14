import math
import threading
import time
from modules.connection.coppelia_connector import CoppeliaConnector

from modules.controllers.manuever_controller import ManueverController

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
        
        # Parametri PID (sensori discreti = no Kd)
        self.kp = 0.35  # Aumentato per ridurre settling distance
        self.ki = 0.0   # Disabilitato per evitare drift
        self.kd = 0.0  # Disabilitato: amplifica il rumore discreto
        
        # Stato interno
        self.prev_error = 0.0

        # Output cinematico per gli attuatori
        self.v = 0.0
        self.w = 0.0
        
        # Gestione Thread (Identica al ColorSensor)
        self.frequenza_controllo = 0.05 # 20 Hz (0.05 sec) - più stabile
        self._running = False
        self._thread = None

        self.heading_est = 0.0        # stima yaw relativo, azzerato quando confermi allineamento
        self.kh = 1.3             # guadagno del termine di richiamo heading, da tarare
        self.centered_streak_fwd = 0  # debounce per confermare "vero" centrato prima di azzerare la stima


    def start(self, reverse=False):
        """Avvia il thread del PID."""
        if not self._running:
            self._running = True
            # Usiamo _loop_controllo come target
            self._thread = threading.Thread(target=self._loop_controllo, args=(reverse,), daemon=True)
            self._thread.start()
            print("[PID] Thread avviato.")

    def _loop_controllo(self, reverse=False):
        """Metodo privato che gira in background nel thread."""
        #last_time = time.time()
        last_time = self.sim.getSimulationTime()  # Usa il tempo di simulazione di CoppeliaSim
        
        while self._running:
            #now = time.time()
            now = self.sim.getSimulationTime()  # Usa il tempo di simulazione di CoppeliaSim
            dt = now - last_time
            if dt <= 0: 
                time.sleep(0.001)  # Piccola pausa per evitare loop troppo veloce
                continue  # Evita divisione per zero o loop troppo veloce

            #t0 = time.time()
            
            # 1. Lettura diretta dalla RAM dei sensori
            l_rgb = self.sensors['left'].last_color
            c_rgb = self.sensors['center'].last_color
            r_rgb = self.sensors['right'].last_color

            #t1 = time.time()

            alpha = 0.25

            error = self._calculate_error(l_rgb, c_rgb, r_rgb)

            self.heading_est += self.w * dt
            self.heading_est *= 0.98  # leaky integrator: decade sempre un po', non solo quando centrato
            max_heading_est = math.radians(9)  # tara questo valore
            self.heading_est = max(-max_heading_est, min(max_heading_est, self.heading_est))

            if error == 0.0:
                self.centered_streak_fwd += 1
            else:
                self.centered_streak_fwd = 0        
            

            # Codice originale intatto
            target_w = -(self.kp * error) - (self.kh * self.heading_est) 
            self.w = alpha * target_w + (1 - alpha) * self.w
            
            # un piccolo bias di deriva sensori si accumulerebbe all'infinito)
            if self.centered_streak_fwd >= 10:
                self.heading_est *= 0.9  # decadimento morbido invece di azzeramento secco

            v_target = self.base_speed * max(0.2, 1 - abs(error))

            max_delta_v = 0.01  # variazione massima di v per ciclo, da tarare
            delta_v = v_target - self.v
            delta_v = max(-max_delta_v, min(max_delta_v, delta_v))
            self.v = self.v + delta_v
            blk = [self._is_black(l_rgb), self._is_black(c_rgb), self._is_black(r_rgb)]
            #print(f"[PID] blk={blk} err={error:+.2f} target_w={target_w:+.4f} w_filtrato={self.w:+.4f} v={self.v:.3f} dt={dt:.3f}")
            self.prev_error = error

            #t2 = time.time()

            # 4. COMANDO AI MOTORI (Nuova chiamata)
            if reverse:
                self.manuever_controller.set_velocity(-self.v, -self.w)  # Usa il metodo del ManueverController per muovere i motori
            else:
                self.manuever_controller.set_velocity(self.v, self.w)  # Usa il metodo del ManueverController per muovere i motori
            #self.actuator.move(self.v, self.w)
            #t3 = time.time()

            #print(f"[PID-timing] sensori={t1-t0:.3f}s calcolo={t2-t1:.3f}s set_velocity={t3-t2:.3f}s totale_loop={t3-t0:.3f}s dt_atteso={dt:.3f}")


            last_time = now
            
            # Pausa per rispettare la frequenza
            time.sleep(self.frequenza_controllo)

    @staticmethod
    def _is_black(rgb):
        return all(abs(val - 22) < 15 for val in rgb) if rgb else False

    def _calculate_error(self, l, c, r):
        """Mappatura discreta -> Errore continuo."""
        blk = [self._is_black(l), self._is_black(c), self._is_black(r)]
        
        if blk == [False, True, False]: return 0.0   # Centro
        if blk == [True, False, False]: return -1.0  # Sinistra
        if blk == [False, False, True]: return 1.0   # Destra
        if blk == [True, True, False]:  return -0.5  # Centro-Sinistra
        if blk == [False, True, True]:  return 0.5   # Centro-Destra
        
        return self.prev_error # Mantiene l'ultimo errore se perde la linea

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