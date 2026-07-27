import threading
import time
import math
from modules.connection.redis_interface import RedisInterface
from modules.actuators.wheel_actuator import WheelsActuator
from modules.controllers.path_controller import PathController
from modules.actuators.cart_actuator import CartActuator
from modules.controllers.position_controller import PositionController

class ManueverController:

    # Tolleranze per la lettura rumorosa di posizione/orientamento da Redis.
    POSITION_TOLERANCE = 0.005   # metri: precisione di arrivo (stretta)
    # Soglia (volutamente più larga di POSITION_TOLERANCE) per decidere SE
    # serve una Fase 2: il residuo dopo la Fase 1 è quasi sempre rumore
    # dell'ordine di 1-2 cm (mai esattamente zero), mentre un vero scarto di
    # seconda gamba è dell'ordine del metro (vedi POSITION_TABLE). Se qui
    # usassimo POSITION_TOLERANCE, un residuo di rumore la farebbe scattare
    # per errore, causando una svolta spuria dopo un hop a singolo asse.
    PHASE2_TOLERANCE = 0.05     # metri
    ANGLE_TOLERANCE = 0.05      # gradi
    CALIBRATION_DISTANCE = 0.1  # metri percorsi prima di capire su quale asse mi sto muovendo

    ADVANCE_SPEED = 0.1
    TURN_SPEED = 0.2
    # Sotto questa soglia (gradi) rallento proporzionalmente: col passo
    # angolare per tick a piena velocità (~1.2°), ANGLE_TOLERANCE=0.05° non
    # può mai "catturare" l'errore — serve restringere il passo prima di
    # arrivare, non solo stringere la tolleranza.
    TURN_SLOW_ZONE = 15.0       # gradi
    MIN_TURN_SPEED = 0.02
    # Stessa idea della rampa angolare, ma per l'avanzata rettilinea: senza
    # decelerazione il passo per tick resta a piena velocità fino
    # all'ultimo istante, e POSITION_TOLERANCE (1 cm) non riesce a
    # "catturare" l'arrivo con precisione.
    ADVANCE_SLOW_ZONE = 0.15    # metri
    MIN_ADVANCE_SPEED = 0.01

    # Gradi: se il verso risulta invertito nel test reale, basta scambiare
    # il segno di LEFT/RIGHT qui, è l'unico posto da toccare.
    TURN_ANGLES = {"LEFT": 90.0, "RIGHT": -90.0, "STRAIGHT": 0.0}

    def __init__(self, redis_client: RedisInterface, clock):
        self.redis_client = redis_client
        self.clock = clock
        self.wheels = WheelsActuator()
        self.path_controller = PathController()
        self.cart = CartActuator()
        self.position_controller = PositionController()

        # Lock per evitare race condition su wheel_actuator
        self._wheel_lock = threading.Lock()
        self._cart_lock = threading.Lock()  # Lock per evitare race condition

        # Cancellazione cooperativa per lo STOP: execute_turn non lo guarda
        # mai (una svolta, iniziata, finisce sempre — vale sia per le svolte
        # di move_to sia per i 180° di PICKUP/DROP), _advance_to_target lo
        # controlla ad ogni tick (si ferma sul posto), move_to lo controlla
        # tra una fase e l'altra (finisce la svolta in corso, poi abortisce
        # invece di iniziare la fase successiva).
        self._stop_requested = threading.Event()

        # Leg (current_position, next_node, previous_node) per cui la svolta
        # di Fase 1 è già stata fatta. Serve per riprendere correttamente
        # dopo uno STOP a metà avanzata: senza questo, move_to rifarebbe la
        # svolta di Fase1 anche se il robot è già orientato bene, perché
        # normalmente assume di essere appena arrivato al nodo.
        self._phase1_done_for = None

        # Passo fisico della simulazione: usato per convertire le durate in
        # secondi (API esistente, invariata) in un numero deterministico di
        # step del SimClock.
        self.physical_dt = self.wheels.sim.getSimulationTimeStep()

    def execute_maneuver(self, command_type, command_data=None):
        """
        Avvia un thread per eseguire la manovra.
        Il thread è daemon, quindi termina automaticamente quando finisce.
        """
        maneuver_thread = threading.Thread(
            target=self._execute_maneuver_thread,
            args=(command_type, command_data),
            daemon=True
        )
        maneuver_thread.start()

    def request_stop(self):
        """
        Richiesta di stop cooperativa: non interrompe nulla direttamente,
        alza solo il flag che execute_turn ignora, _advance_to_target e
        move_to controllano nei punti giusti.
        """
        self._stop_requested.set()

    def _execute_maneuver_thread(self, command_type, command_data):
        """
        Esecuzione effettiva della manovra all'interno del thread.
        Termina automaticamente quando finisce.
        """
        self._stop_requested.clear()  # ogni nuova manovra parte senza uno stop residuo
        self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "IN_PROGRESS"})
        print(f"🚀 Esecuzione manovra: {command_type} con dati: {command_data}")


        if command_type == "MOVE_TO":

            self.move_to(
                command_data.get("current_position"),
                command_data.get("next_node"),
                command_data.get("previous_node")
            )

            # Segnala il completamento della manovra
            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "COMPLETED"})
            print(f"🧠 [ManeuverController] Manovra completata")

        elif command_type == "DROP":

            self.execute_turn(180.0)
            print(f"✅ Manovra DROP completata.")

            # Segnala il completamento della manovra
            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "COMPLETED"})
            self.redis_client.update_sensor_data("brain_memory", {"is_load": False})

        elif command_type == "PICKUP":
            self.execute_turn(180.0)
            print(f"✅ Manovra PICKUP completata.")

            # Segnala il completamento della manovra
            self.redis_client.update_sensor_data("body_memory", {"maneuver_state": "COMPLETED"})
            self.redis_client.update_sensor_data("brain_memory", {"is_load": True})


    def set_velocity(self, v, w):
        """
        Comanda i wheel in modo thread-safe.
        Scrittura 'nuda': va chiamata SOLO da dentro un loop già gated
        sul SimClock (es. il PID, che fa il proprio ack subito dopo).
        """
        with self._wheel_lock:
            self.wheels.move(v, w)

    def set_velocity_for(self, v, w, duration, participant_name="maneuver"):
        duration_steps = max(1, round(duration / self.physical_dt))
        next_step = self.clock.register(participant_name, 1)
        try:
            for _ in range(duration_steps):
                actual = self.clock.wait_until(next_step)
                with self._wheel_lock:
                    self.wheels.move(v, w)
                self.clock.ack(participant_name)
                next_step = actual + 1
        finally:
            self.clock.unregister(participant_name)

    def execute_turn(self, delta_degrees):
        """
        Ruota di un angolo relativo, in gradi. Positivo = sinistra,
        negativo = destra: il verso del comando ai motori (TURN_SPEED *
        direction) è quello giusto, confermato in sim. Il valore di
        orientamento letto da Redis però si muove in verso OPPOSTO al
        segno di delta_degrees (con target = orientation + delta_degrees
        una svolta di 90° ne faceva fare 270, il giro lungo) — quindi il
        target si calcola sottraendo, non sommando.
        """
        orientation = self._read_orientation_deg()
        # Aggancio il target al cardinale più vicino (0/90/-90/180) invece di
        # usarlo come puro offset relativo dall'orientamento corrente: così
        # ogni svolta si auto-corregge verso il cardinale vero, invece di
        # accumulare il residuo (mai esattamente 0) lasciato dalla svolta
        # precedente.
        target = self._normalize_deg(round((orientation - delta_degrees) / 90.0) * 90.0)
        direction = 1 if delta_degrees > 0 else -1
        previous_error = self._normalize_deg(target - orientation)
        #print(f"🎯 [execute_turn] delta={delta_degrees}° orientamento_iniziale={orientation:.2f}° target={target:.2f}°")

        # Il sensore di posizione scrive su Redis a ~10Hz, molto più lento
        # del polling di questo loop: per diversi tick leggiamo lo stesso
        # valore stantio, poi arriva un campione nuovo che "salta" di colpo
        # di quanto il robot ha ruotato nell'intervallo. Se quel salto è più
        # largo di ANGLE_TOLERANCE, il solo controllo |errore|<=tolleranza
        # può scavallare la finestra senza mai cadere dentro -> giro infinito.
        # Per questo rilevo anche il cambio di segno dell'errore (l'ho
        # superato, anche se non ci sono caduta esattamente dentro).
        #
        # Guardia necessaria per le svolte di 180°: l'errore iniziale è per
        # costruzione sempre vicino a ±180° (l'antipodo), cioè esattamente
        # sulla discontinuità della normalizzazione. Un piccolissimo
        # movimento che attraversa quel punto fa cambiare segno all'errore
        # anche se siamo lontanissimi dal target vero — quindi il cambio di
        # segno conta come "l'ho superato" solo se ero già vicino al target
        # (dentro la slow zone) in entrambe le letture, non all'antipodo.
        participant_name = "maneuver_turn"
        next_step = self.clock.register(participant_name, 1)
        try:
            while True:
                actual = self.clock.wait_until(next_step)
                orientation = self._read_orientation_deg()
                error = self._normalize_deg(target - orientation)
                near_target = abs(previous_error) < self.TURN_SLOW_ZONE and abs(error) < self.TURN_SLOW_ZONE
                crossed = near_target and (error == 0.0 or (previous_error > 0.0) != (error > 0.0))
                reached = abs(error) <= self.ANGLE_TOLERANCE or crossed
                previous_error = error

                # Rallento proporzionalmente sotto TURN_SLOW_ZONE: il passo
                # per tick si restringe man mano che mi avvicino, così la
                # tolleranza stretta diventa raggiungibile invece di essere
                # sempre scavallata dal rilevamento del cambio di segno.
                abs_error = abs(error)
                if abs_error < self.TURN_SLOW_ZONE:
                    speed = self.MIN_TURN_SPEED + (self.TURN_SPEED - self.MIN_TURN_SPEED) * (abs_error / self.TURN_SLOW_ZONE)
                else:
                    speed = self.TURN_SPEED

                #print(f"   [execute_turn] orientamento={orientation:.2f}° target={target:.2f}° errore={error:.2f}° speed={speed:.3f} reached={reached}")
                with self._wheel_lock:
                    self.wheels.move(0.0, 0.0 if reached else speed * direction)
                self.clock.ack(participant_name)
                next_step = actual + 1
                if reached:
                    break
        finally:
            self.clock.unregister(participant_name)

        self.set_velocity(0.0, 0.0)

    def _read_orientation_deg(self):
        """
        Legge l'orientamento da Redis e lo riporta in gradi. Il valore
        crudo puo' arrivare sia in radianti (API CoppeliaSim) sia già in
        gradi secondo di com'è configurato il sensore: un angolo normalizzato
        in radianti sta sempre in [-pi, pi], quindi se il valore letto supera
        quel range e' già in gradi.
        """
        raw = self.redis_client.get_sensor_data("body_memory").get("orientation")
        if abs(raw) <= math.pi + 0.01:
            return math.degrees(raw)
        return raw

    def _advance_to_target(self, target_x, target_y):
        """
        Avanza in linea retta finché la coordinata sull'asse su cui mi sto
        effettivamente muovendo (osservato dal moto reale, non assunto
        dall'orientamento) non raggiunge il target. Ritorna (asse, dx, dy)
        percorsi, utile al chiamante per calcolare la svolta successiva.
        """
        data0 = self.redis_client.get_sensor_data("body_memory")
        x0, y0 = data0.get("x_pos"), data0.get("y_pos")

        if abs(target_x - x0) <= self.POSITION_TOLERANCE and abs(target_y - y0) <= self.POSITION_TOLERANCE:
            return None, 0.0, 0.0

        axis = None
        target_value = None
        previous_error = None
        x, y = x0, y0

        # Stessa insidia di execute_turn: il sensore di posizione scrive su
        # Redis a ~10Hz, più lento del polling di questo loop. Con una
        # POSITION_TOLERANCE stretta lo spostamento tra due letture diverse
        # consecutive può essere comparabile alla finestra di tolleranza e
        # scavallarla senza mai cadere dentro -> avanzata infinita. Rilevo
        # quindi anche il cambio di segno dell'errore, non solo la soglia.
        participant_name = "maneuver_advance"
        next_step = self.clock.register(participant_name, 1)
        try:
            while True:
                actual = self.clock.wait_until(next_step)
                data = self.redis_client.get_sensor_data("body_memory")
                x, y = data.get("x_pos"), data.get("y_pos")

                if axis is None and (abs(x - x0) >= self.CALIBRATION_DISTANCE or abs(y - y0) >= self.CALIBRATION_DISTANCE):
                    axis = "x" if abs(x - x0) >= abs(y - y0) else "y"
                    target_value = target_x if axis == "x" else target_y
                    previous_error = target_value - (x if axis == "x" else y)

                if axis is not None:
                    current_value = x if axis == "x" else y
                    error = target_value - current_value
                    crossed = error == 0.0 or (previous_error > 0.0) != (error > 0.0)
                    reached = abs(error) <= self.POSITION_TOLERANCE or crossed
                    previous_error = error

                    abs_error = abs(error)
                    if abs_error < self.ADVANCE_SLOW_ZONE:
                        speed = self.MIN_ADVANCE_SPEED + (self.ADVANCE_SPEED - self.MIN_ADVANCE_SPEED) * (abs_error / self.ADVANCE_SLOW_ZONE)
                    else:
                        speed = self.ADVANCE_SPEED
                else:
                    reached = False
                    speed = self.ADVANCE_SPEED  # in fase di calibrazione asse, avanzo a piena velocità

                # STOP richiesto durante l'avanzata: mi fermo qui, non aspetto
                # di arrivare al target come farebbe la sola tolleranza.
                if self._stop_requested.is_set():
                    reached = True

                #print(f"   [_advance_to_target] x={x:.3f} y={y:.3f} asse={axis} speed={speed:.3f} reached={reached}")
                with self._wheel_lock:
                    self.wheels.move(0.0 if reached else speed, 0.0)
                self.clock.ack(participant_name)
                next_step = actual + 1
                if reached:
                    break
        finally:
            self.clock.unregister(participant_name)

        self.set_velocity(0.0, 0.0)
        return axis, x - x0, y - y0

    def move_to(self, current_position, next_node, previous_node):
        """
        Manovra punto-a-punto verso next_node, in 2 fasi:
        Fase 1: la svolta la decide il PathController (dato topologico,
        affidabile) sulla base di come sono entrata nel nodo attuale.
        Fase 2 (solo se resta uno scarto sull'altro asse): la svolta la
        calcolo io dai numeri, perché per questo caso non esiste una voce
        di tabella.
        """
        target_x, target_y = self.position_controller.get_position(next_node)
        leg_key = (current_position, next_node, previous_node)

        if self._phase1_done_for == leg_key:
            print(f"🧭 [move_to] {current_position} -> {next_node} (da {previous_node}): riprendo dopo uno STOP, Fase1 già fatta, salto la svolta")
        else:
            turn = self.path_controller.get_next_step2(current_position, next_node, previous_node)
            angle = self.TURN_ANGLES.get(turn, 0.0)
            print(f"🧭 [move_to] {current_position} -> {next_node} (da {previous_node}): Fase1 PathController={turn}")
            if angle != 0.0:
                self.execute_turn(angle)  # finisce sempre, lo STOP non la interrompe
            # Segnalo fatta anche se subito dopo arriva uno STOP: è quello
            # che permette alla ripresa di saltarla correttamente.
            self._phase1_done_for = leg_key

        if self._stop_requested.is_set():
            return  # svolta finita, non inizio l'avanzata

        axis, dx1, dy1 = self._advance_to_target(target_x, target_y)
        print(f"🧭 [move_to] Fase1 avanzata su asse={axis} dx1={dx1:.3f} dy1={dy1:.3f}")
        if axis is None:
            self._phase1_done_for = None  # leg completata (ero già a target)
            return
        if self._stop_requested.is_set():
            return  # avanzata fermata per STOP: leg non completata, non azzero il flag

        data = self.redis_client.get_sensor_data("body_memory")
        x, y = data.get("x_pos"), data.get("y_pos")
        dx, dy = target_x - x, target_y - y

        if abs(dx) <= self.PHASE2_TOLERANCE and abs(dy) <= self.PHASE2_TOLERANCE:
            print(f"🧭 [move_to] Fase2 non necessaria (dx={dx:.3f} dy={dy:.3f})")
            self._phase1_done_for = None  # leg completata
            return  # scarto residuo = rumore, non un vero secondo asse da correggere

        heading = (self._sign(dx1), self._sign(dy1))
        needed = (0.0, self._sign(dy)) if axis == "x" else (self._sign(dx), 0.0)

        cross = heading[0] * needed[1] - heading[1] * needed[0]
        fase2_turn = "LEFT" if cross > 0 else "RIGHT" if cross < 0 else "NESSUNA"
        print(f"🧭 [move_to] Fase2: heading={heading} needed={needed} cross={cross} -> {fase2_turn} (dx={dx:.3f} dy={dy:.3f})")
        if cross > 0:
            self.execute_turn(self.TURN_ANGLES["LEFT"])
        elif cross < 0:
            self.execute_turn(self.TURN_ANGLES["RIGHT"])

        if self._stop_requested.is_set():
            return  # svolta di Fase2 finita, non inizio la seconda avanzata

        self._advance_to_target(target_x, target_y)
        if not self._stop_requested.is_set():
            self._phase1_done_for = None  # leg completata

    @staticmethod
    def _normalize_deg(angle):
        return ((angle + 180.0) % 360.0) - 180.0

    @staticmethod
    def _sign(value, tol=1e-3):
        if value > tol:
            return 1.0
        if value < -tol:
            return -1.0
        return 0.0

    def stop(self):
        """
        Ferma il robot immediatamente.
        Stessa garanzia di set_velocity_for: un solo tick gated, così anche
        l'arresto avviene in modo sincronizzato e non in una finestra
        temporale variabile.
        """
        self.set_velocity_for(0.0, 0.0, self.physical_dt, participant_name="maneuver_stop")