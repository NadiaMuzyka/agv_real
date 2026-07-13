import math
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
        self.kp = 0.15  # Aumentato per ridurre settling distance
        self.ki = 0.0   # Disabilitato per evitare drift
        self.kd = 0.0  # Disabilitato: amplifica il rumore discreto
        
        # Stato interno
        self.prev_error = 0.0
        self.integral = 0.0
        self.error_buffer = []  # Filtro media mobile

        # Reverse: stop-rotate-go (i sensori sono un punto "trainato" rispetto
        # al perno ruote quando si arretra, quindi niente v+w simultanei)
        self._reverse_state = "STRAIGHT"
        self._correcting_left = False
        self._correcting_right = False
        self._correcting_mild = False
        # Storia minima per disambiguare testa/culo rispetto alla linea quando il
        # pattern letto è lo stesso ma il verso corretto è opposto (vedi _reverse_step)
        self._last_correction_dir_left = None  # verso (bool, convenzione di drift_left) dell'ultima correzione eseguita
        self._seen_centered_since = True  # precondizione: all'avvio della retromarcia il robot è già centrato
        self._centered_streak = 0  # debounce: letture "centered" consecutive pulite, per non fidarsi di un frame rumoroso
        self.reverse_speed = self.base_speed * 0.5
        self.reverse_turn_w = 0.06  # più lento delle svolte forward: va ricalibrato sul robot
        self.reverse_turn_w_mild = self.reverse_turn_w * 0.5  # laterale+centro neri = deviazione lieve (come errore ±0.5 nel forward)
        self.reverse_settle_time = 0.15  # pausa a motori fermi dopo una correzione, per smorzare l'inerzia
        
        # Output cinematico per gli attuatori
        self.v = 0.0
        self.w = 0.0
        
        # Gestione Thread (Identica al ColorSensor)
        self.frequenza_controllo = 0.05 # 20 Hz (0.05 sec) - più stabile
        self._running = False
        self._thread = None

        self.turn_accum = 0.0  # rotazione accumulata nella correzione corrente (rad)
        self.correcting = False
        self.max_turn_per_correction = math.radians(6)  # soglia da tarare: quanto puoi ruotare prima di fermarti e ricontrollare

        self.heading_est = 0.0        # stima yaw relativo, azzerato quando confermi allineamento
        self.kh = 0.5                # guadagno del termine di richiamo heading, da tarare
        self.centered_streak_fwd = 0  # debounce per confermare "vero" centrato prima di azzerare la stima


    def start(self, reverse=False):
        """Avvia il thread del PID."""
        if not self._running:
            self._running = True
            self._reverse_state = "STRAIGHT"
            self._correcting_left = False
            self._correcting_right = False
            self._correcting_mild = False
            self._last_correction_dir_left = None
            self._seen_centered_since = True
            self._centered_streak = 0
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

            t0 = time.time()
            
            # 1. Lettura diretta dalla RAM dei sensori
            l_rgb = self.sensors['left'].last_color
            c_rgb = self.sensors['center'].last_color
            r_rgb = self.sensors['right'].last_color

            t1 = time.time()
            
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

                alpha = 0.5
                # 2. Calcolo Errore e PID
                error = self._calculate_error(l_rgb, c_rgb, r_rgb)

                self.heading_est += self.w * dt
                self.heading_est *= 0.98  # leaky integrator: decade sempre un po', non solo quando centrato
                max_heading_est = math.radians(8)  # tara questo valore
                self.heading_est = max(-max_heading_est, min(max_heading_est, self.heading_est))


                if error == 0.0:
                    self.centered_streak_fwd += 1
                else:
                    self.centered_streak_fwd = 0



                # Filtro media mobile (smooth l'errore discreto)
                #self.error_buffer.append(error)
                #if len(self.error_buffer) > 2:
                #    self.error_buffer.pop(0)
                #error = sum(self.error_buffer) / len(self.error_buffer)
                
                

                # Codice originale intatto
                target_w = -(self.kp * error) - (self.kh * self.heading_est) 
                self.w = alpha * target_w + (1 - alpha) * self.w
                
                # nel loop, dopo aver calcolato self.w
                #if abs(error) > 0.01:  # sta correggendo
                   # self.turn_accum += self.w * dt
                    #if abs(self.turn_accum) > self.max_turn_per_correction:
                        #self.w *= 0.2  # smorza fortemente: ha già ruotato abbastanza, aspetta che il sensore si aggiorni
                #else:
                   # self.turn_accum = 0.0  # errore rientrato, resetta l'accumulo
                                # se siamo stabilmente centrati per un po', ri-azzeriamo la stima (altrimenti
                
                # un piccolo bias di deriva sensori si accumulerebbe all'infinito)
                if self.centered_streak_fwd >= 10:
                    self.heading_est *= 0.9  # decadimento morbido invece di azzeramento secco


                self.v = self.base_speed * max(0.2, 1 - abs(error))
                blk = [self._is_black(l_rgb), self._is_black(c_rgb), self._is_black(r_rgb)]
                print(f"[PID] blk={blk} err={error:+.2f} target_w={target_w:+.4f} w_filtrato={self.w:+.4f} v={self.v:.3f} dt={dt:.3f}")
                self.prev_error = error

            t2 = time.time()

            # 4. COMANDO AI MOTORI (Nuova chiamata)
            self.manuever_controller.set_velocity(self.v, self.w)  # Usa il metodo del ManueverController per muovere i motori
            #self.actuator.move(self.v, self.w)
            t3 = time.time()

            print(f"[PID-timing] sensori={t1-t0:.3f}s calcolo={t2-t1:.3f}s set_velocity={t3-t2:.3f}s totale_loop={t3-t0:.3f}s dt_atteso={dt:.3f}")


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

        Deviazione "lieve" (laterale+centro entrambi neri, es. blk=[T,T,F]):
        equivalente dell'errore ±0.5 nel forward, si corregge con una w
        dimezzata (reverse_turn_w_mild). In questo caso il centro è già nero
        FIN DALL'INIZIO della correzione, quindi il criterio di stop "c_black"
        usato per la deviazione forte scatterebbe al primo ciclo senza aver
        ruotato quasi nulla: per il caso lieve si aspetta invece che il
        laterale si spenga (centered), come faceva il vecchio criterio.

        Ambiguità testa/culo: un solo sensore laterale nero (o laterale+centro)
        non basta a sapere IL VERSO giusto di rotazione, perché in retromarcia
        (sensore trainato, non lookahead) lo stesso pattern può corrispondere
        a due assetti opposti — es. "culo a destra della linea, testa a
        sinistra" (skew ampio) oppure "sia testa che culo a sinistra, solo il
        bordo del sensore destro sfiora la linea" (semplice offset laterale) —
        che richiedono correzioni di verso opposto. Nel forward questa
        ambiguità non si presenta perché il sensore è davanti al perno: la
        regola "mirror" (gira verso il lato che vede nero) riduce l'errore
        futuro qualunque sia l'assetto reale (come nella pure-pursuit). In
        retromarcia no, quindi ci si fida della regola mirror SOLO quando si
        riparte da un vero centraggio confermato da quando è iniziata l'ultima
        correzione (_seen_centered_since); altrimenti si assume che il nuovo
        pattern sia la coda dello stesso skew e si mantiene il verso della
        correzione precedente (_last_correction_dir_left) invece di flippare,
        per non innescare uno zigzag rincorrendo ogni singola lettura.
        _seen_centered_since scatta solo dopo 2 letture "centered" consecutive
        (debounce): un singolo frame rumoroso al bordo del nastro non deve
        poter far scattare la fiducia sulla regola mirror e reintrodurre lo
        zigzag. Lo stop del motore (stop_now sotto) resta invece immediato e
        non debounced, per non reintrodurre l'overshoot descritto sopra.
        """
        crossing = (l_black and r_black) or (not l_black and not c_black and not r_black)  # incrocio: sx e dx entrambi neri, a prescindere dal centro
        if crossing:
            # attraversa l'incrocio dritto, ignorando qualunque correzione in corso
            self._reverse_state = "STRAIGHT"
            self.v = -self.reverse_speed
            self.w = 0.0
            self._centered_streak = 0  # pattern ambiguo per definizione, non conta per il debounce
            return

        centered = c_black and not l_black and not r_black
        # linea a sinistra -> ruota a destra (w negativo); linea a destra -> ruota a sinistra (w positivo)
        drift_left = l_black and not r_black
        drift_right = r_black and not l_black
        # deviazione lieve: il centro vede già nero insieme al laterale (blk=[T,T,F] o [F,T,T])
        mild = (drift_left or drift_right) and c_black

        # Debounce della conferma "centrato": solo il flag di fiducia per la
        # prossima decisione di verso aspetta 2 letture pulite, non lo stop motore.
        if centered:
            self._centered_streak += 1
            if self._centered_streak >= 2:
                self._seen_centered_since = True
        else:
            self._centered_streak = 0

        if self._reverse_state == "CORRECTING":
            stop_now = centered if self._correcting_mild else c_black
            if stop_now:
                # deviazione forte: il centro ha raggiunto la linea, fermati
                # subito anche se un laterale è ancora nero (transizione).
                # deviazione lieve: il laterale si è spento, il robot è
                # DAVVERO centrato (solo il centro vede nero).
                # In entrambi i casi: fermati e riprendi ad arretrare dritto
                self._reverse_state = "STRAIGHT"
                self.v = 0.0
                self.w = 0.0
                time.sleep(self.reverse_settle_time)  # smorza l'inerzia prima di ripartire
            elif drift_left == self._correcting_left and drift_right == self._correcting_right:
                self.v = 0.0
                turn_w = self.reverse_turn_w_mild if self._correcting_mild else self.reverse_turn_w
                self.w = -turn_w if self._last_correction_dir_left else turn_w
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
            # scelta del verso: fidati della lettura raw solo se siamo ripartiti
            # da un centraggio confermato, altrimenti mantieni il verso precedente
            # (vedi ambiguità testa/culo nel docstring)
            if self._seen_centered_since or self._last_correction_dir_left is None:
                turn_left = drift_left
            else:
                turn_left = self._last_correction_dir_left
                if turn_left != drift_left:
                    print(f"[PID-reverse] verso mantenuto da correzione precedente (lettura raw suggerirebbe {'sinistra' if drift_left else 'destra'}, probabile skew testa/culo)")

            self._reverse_state = "CORRECTING"
            self._correcting_left = drift_left
            self._correcting_right = drift_right
            self._correcting_mild = mild
            self._last_correction_dir_left = turn_left
            self._seen_centered_since = False
            turn_w = self.reverse_turn_w_mild if mild else self.reverse_turn_w
            self.v = 0.0
            self.w = -turn_w if turn_left else turn_w
            print(f"[PID-reverse] correzione avviata: l={l_black} c={c_black} r={r_black} -> w={self.w:+.3f} ({'destra' if turn_left else 'sinistra'}{', lieve' if mild else ''})")
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