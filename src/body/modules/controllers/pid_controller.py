import threading
import time

from modules.controllers.manuever_controller import ManueverController

class PIDController:
    def __init__(self, sensors_dict,  base_speed=0.05):
        """
        :param sensors_dict: Dizionario con le istanze dei sensori {'left': obj, 'center': obj, 'right': obj}
        """
        self.sensors = sensors_dict
        self.base_speed = base_speed

        self.manuever_controller = ManueverController(None) 
        
        # Parametri PID (sensori discreti = no Kd)
        self.kp = 0.1  # Aumentato per ridurre settling distance
        self.ki = 0.0   # Disabilitato per evitare drift
        self.kd = 0.1  # Disabilitato: amplifica il rumore discreto
        
        # Stato interno
        self.prev_error = 0.0
        self.integral = 0.0
        self.error_buffer = []  # Filtro media mobile

        # Reverse: stop-rotate-go (i sensori sono un punto "trainato" rispetto
        # al perno ruote quando si arretra, quindi niente v+w simultanei)
        self._reverse_state = "STRAIGHT"
        self._correcting_left = False
        self._correcting_right = False
        self.reverse_speed = self.base_speed * 0.5
        self.reverse_turn_w = 0.06  # più lento delle svolte forward: va ricalibrato sul robot
        self.reverse_settle_time = 0.15  # pausa a motori fermi dopo una correzione, per smorzare l'inerzia
        
        # Output cinematico per gli attuatori
        self.v = 0.0
        self.w = 0.0
        
        # Gestione Thread (Identica al ColorSensor)
        self.frequenza_controllo = 0.05 # 20 Hz (0.05 sec) - più stabile
        self._running = False
        self._thread = None

    def start(self, reverse=False):
        """Avvia il thread del PID."""
        if not self._running:
            self._running = True
            self._reverse_state = "STRAIGHT"
            # Usiamo _loop_controllo come target
            self._thread = threading.Thread(target=self._loop_controllo, args=(reverse,), daemon=True)
            self._thread.start()
            print("[PID] Thread avviato.")

    def _loop_controllo(self, reverse=False):
        """Metodo privato che gira in background nel thread."""
        last_time = time.time()
        
        while self._running:
            now = time.time()
            dt = now - last_time
            if dt <= 0: continue
            
            # 1. Lettura diretta dalla RAM dei sensori
            l_rgb = self.sensors['left'].last_color
            c_rgb = self.sensors['center'].last_color
            r_rgb = self.sensors['right'].last_color
            
            if reverse:
                # Bang-bang stop-rotate-go su booleani grezzi (vedi _reverse_step):
                # non passiamo dal valore "error" perché _calculate_error, sui
                # pattern non mappati, restituisce l'ultimo errore noto invece
                # di riflettere la lettura attuale, e durante una rotazione
                # questo può far proseguire la svolta ben oltre il centro.
                l_black = self._is_black(l_rgb)
                c_black = self._is_black(c_rgb)
                r_black = self._is_black(r_rgb)
                self._reverse_step(l_black, c_black, r_black)
            else:
                # 2. Calcolo Errore e PID
                error = self._calculate_error(l_rgb, c_rgb, r_rgb)

                # Filtro media mobile (smooth l'errore discreto)
                self.error_buffer.append(error)
                if len(self.error_buffer) > 3:
                    self.error_buffer.pop(0)
                error = sum(self.error_buffer) / len(self.error_buffer)

                # Codice originale intatto
                self.w = -(self.kp * error)
                self.v = self.base_speed * max(0.2, 1 - abs(error))
                self.prev_error = error

            # 4. COMANDO AI MOTORI (Nuova chiamata)
            self.manuever_controller.set_velocity(self.v, self.w)  # Usa il metodo del ManueverController per muovere i motori
            #self.actuator.move(self.v, self.w)

            last_time = now
            
            # Pausa per rispettare la frequenza
            time.sleep(self.frequenza_controllo)

    def _reverse_step(self, l_black, c_black, r_black):
        """
        In retromarcia il perno delle ruote motrici precede i sensori nel verso
        di marcia (i sensori diventano un punto "trainato" invece che di
        lookahead): correggere w mentre si trasla con v!=0 accoppia le due
        dinamiche e diverge in zigzag crescente. Si disaccoppia quindi
        traslazione e rotazione, come già fa manuever_controller per le svolte:
        si arretra dritti finché la linea resta centrata; appena un sensore
        laterale vede nero ci si ferma e si ruota sul posto (v=0) finché non
        si è ricentrati, poi si riprende ad arretrare dritti.

        Durante la rotazione ci si ferma appena il centro rivede nero (anche
        se un laterale è ancora nero, es. linea larga) o appena il pattern
        smentisce il lato di partenza, invece di rincorrere una lettura
        "solo centro" pulita: il vecchio criterio guardava solo se il lato di
        partenza era ancora attivo, quindi con blk=[left+center] restava
        "still_same" anche a centro già raggiunto e continuava a ruotare
        oltre, superando il centro e oscillando da un lato all'altro senza
        mai fermarsi (visto in log reali: mai un vero "centrato", solo
        rimbalzi sx/dx).
        """
        crossing = (l_black and r_black) or (not l_black and not c_black and not r_black)  # incrocio: sx e dx entrambi neri, a prescindere dal centro
        if crossing:
            # attraversa l'incrocio dritto, ignorando qualunque correzione in corso
            self._reverse_state = "STRAIGHT"
            self.v = -self.reverse_speed
            self.w = 0.0
            return

        centered = c_black and not l_black and not r_black
        # In retromarcia i sensori sono un punto trainato (vedi docstring sopra):
        # se il sensore SINISTRO vede la linea il robot deve ruotare a DESTRA
        # per ricentrarsi (e viceversa) - verso opposto rispetto al forward.
        drift_left = l_black and not r_black    # linea a sinistra -> ruota a destra (w positivo)
        drift_right = r_black and not l_black   # linea a destra -> ruota a sinistra (w negativo)

        if self._reverse_state == "CORRECTING":
            if c_black:
                # il centro ha già raggiunto la linea: fermati subito, anche
                # se un laterale è ancora nero (transizione), per non superare
                # il centro rincorrendo una lettura "solo centro" più pulita
            #if centered:
                #il robot è DAVVERO centrato (solo il centro vede nero):
                # fermati e riprendi ad arretrare dritto
                self._reverse_state = "STRAIGHT"
                self.v = 0.0
                self.w = 0.0
                time.sleep(self.reverse_settle_time)  # smorza l'inerzia prima di ripartire
            elif drift_left == self._correcting_left and drift_right == self._correcting_right:
                self.v = 0.0
                self.w = self.reverse_turn_w if self._correcting_left else -self.reverse_turn_w
            else:
                # pattern passato al lato opposto senza mai vedere il centro:
                # overshoot netto, fermati comunque invece di rincorrerlo
                self._reverse_state = "STRAIGHT"
                self.v = 0.0
                self.w = 0.0
                time.sleep(self.reverse_settle_time)
            return

        # stato STRAIGHT
        if centered:
            self.v = -self.reverse_speed
            self.w = 0.0
        elif drift_left or drift_right:
            self._reverse_state = "CORRECTING"
            self._correcting_left = drift_left
            self._correcting_right = drift_right
            self.v = 0.0
            self.w = self.reverse_turn_w if drift_left else -self.reverse_turn_w
            print(f"[PID-reverse] correzione avviata: l={l_black} c={c_black} r={r_black} -> w={self.w:+.3f} ({'destra' if drift_left else 'sinistra'})")
        # else: pattern ambiguo (linea persa o entrambi i laterali neri) -> mantieni l'ultimo comando

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