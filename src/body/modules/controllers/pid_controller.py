import threading
import time

class PIDController:
    def __init__(self, sensors_dict, wheels_actuator, base_speed=0.07):
        """
        :param sensors_dict: Dizionario con le istanze dei sensori {'left': obj, 'center': obj, 'right': obj}
        """
        self.sensors = sensors_dict
        self.actuator = wheels_actuator # Salviamo il riferimento all'attuatore
        self.base_speed = base_speed
        
        # Parametri PID (sensori discreti = no Kd)
        self.kp = 0.1  # Aumentato per ridurre settling distance
        self.ki = 0.0   # Disabilitato per evitare drift
        self.kd = 0.1  # Disabilitato: amplifica il rumore discreto
        
        # Stato interno
        self.prev_error = 0.0
        self.integral = 0.0
        self.error_buffer = []  # Filtro media mobile
        
        # Output cinematico per gli attuatori
        self.v = 0.0
        self.w = 0.0
        
        # Gestione Thread (Identica al ColorSensor)
        self.frequenza_controllo = 0.05 # 20 Hz (0.05 sec) - più stabile
        self._running = False
        self._thread = None

    def start(self):
        """Avvia il thread del PID."""
        if not self._running:
            self._running = True
            # Usiamo _loop_controllo come target
            self._thread = threading.Thread(target=self._loop_controllo, daemon=True)
            self._thread.start()
            print("[PID] Thread avviato.")

    def _loop_controllo(self):
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
            
            # 2. Calcolo Errore e PID
            error = self._calculate_error(l_rgb, c_rgb, r_rgb)
            
            # Filtro media mobile (smooth l'errore discreto)
            self.error_buffer.append(error)
            if len(self.error_buffer) > 3:
                self.error_buffer.pop(0)
            error = sum(self.error_buffer) / len(self.error_buffer)
            print(f"[PID] Errore: {error:.3f}, Buffer: {[round(e, 3) for e in self.error_buffer]}")

            # Solo termine proporzionale
            self.w = -(self.kp * error )
            self.v = self.base_speed * max(0.2, 1 - abs(error))

            # 4. COMANDO AI MOTORI (Nuova chiamata)
            self.actuator.move(self.v, self.w)
            
            self.prev_error = error
            last_time = now
            
            # Pausa per rispettare la frequenza
            time.sleep(self.frequenza_controllo)

    def _calculate_error(self, l, c, r):
        """Mappatura discreta -> Errore continuo."""
        def is_black(rgb):
            return all(abs(val - 22) < 15 for val in rgb) if rgb else False

        blk = [is_black(l), is_black(c), is_black(r)]
        
        if blk == [False, True, False]: return 0.0   # Centro
        if blk == [True, False, False]: return -1.0  # Sinistra
        if blk == [False, False, True]: return 1.0   # Destra
        if blk == [True, True, False]:  return -0.5  # Centro-Sinistra
        if blk == [False, True, True]:  return 0.5   # Centro-Destra
        
        return self.prev_error # Mantiene l'ultimo errore se perde la linea

    def stop(self):
        """Ferma il thread in modo pulito."""
        self._running = False
        if self._thread:
            self._thread.join()
            print("[PID] Thread fermato.")