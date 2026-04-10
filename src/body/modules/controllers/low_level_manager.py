# FILE: src/body/modules/controllers/low_level_manager.py

from time import time
import logging

logger = logging.getLogger(__name__)

class LowLevelManager:
    """
    Gestore di Controllo a Basso Livello (Low-Level Manager).
    
    Questa classe agisce come un controllore software embedded. Il suo scopo primario
    è convertire direttive strategiche/discrete di alto livello (es. comando `LINE_FOLLOW` 
    correlato a un errore ottico) in comandi puramente cinematici per l'azionamento 
    (Velocità Lineare `V` e Velocità Angolare `W`).
    
    Tale conversione avviene mediante un algoritmo P.I.D. (Proporzionale-Integrale-Derivativo) 
    in anello chiuso, accoppiato a un filtro passa-basso di ammorbidimento, massimizzando 
    la stabilità del moto e minimizzando l'usura da sovracompensazione sui giunti.
    """
    def __init__(self, sim=None):
        """
        Istanzia il controllore e definisce i parametri dell'algoritmo PID e i registri di stato.
        
        Args:
            sim (obj, optional): Riferimento al motore fisico (CoppeliaSim API) per 
                                 eventuale logging o accesso hardware.
        """
        self.sim = sim
        self.last_print_time = 0
        logger.info("LowLevelManager inizializzato.")
        
        # --- PARAMETRI MATEMATICI DEL CONTROLLORE PID ---
        # Kp: Coefficiente di guadagno Proporzionale. Determina la reattività istantanea all'errore.
        # Valore attuale 0.28: fornisce una sterzata robusta per curve strette ma senza sbandare.
        self.kp = 0.28  
        
        # Ki: Coefficiente di guadagno Integrale. Elimina l'errore stazionario a regime (steady-state).
        # Impostato a 0.0 in scenari Line-Follower per evitare l'accumulo in curva (Windup error). 
        self.ki = 0.0   
        
        # Kd: Coefficiente di guadagno Derivativo. Smorza le oscillazioni reagendo alla velocità
        # della variazione dell'errore (effetto frenante proporzionale alla derivata "de/dt").
        self.kd = 0.01  
        
        # --- REGISTRI DI STATO PID (Memoria del controllore) ---
        self.prev_error = 0.0      # Errore rilevato nel ciclo macchina precedente (t-1)
        self.integral_error = 0.0  # Accumulatore continuo del gradiente di errore
        self.last_time = None      # Timestamp dell'ultima iterazione (t-1)
        
        # --- REGISTRI FILTRO ATTUATORE ---
        self.current_w = 0.0       # Variabile inerziale della sterzata corrente

    def calculate_pid(self, error: float) -> float:
        """
        Calcola l'equazione del controllore PID in base all'errore di tracciamento attuale.
        Formula teorica: U(t) = Kp*e(t) + Ki*∫e(t)dt + Kd*(de(t)/dt)
        Invece di restituire direttamente U(t), la classe converte questa forza in 
        velocità angolare "frenante" invertendola (negativa) a beneficio del modello cinematico.
        
        Args:
            error (float): Quoziente discostamento. Valori positivi indicano uno 
                           scostamento verso destra rispetto alla linea ideale.
        
        Returns:
            float: Il coefficiente cinetico bersaglio da applicare (W richiesto dal PID nudo).
        """
        current_time = time()
        
        # Controllo d'inizio procedura per derivata zero
        if self.last_time is None:
            self.last_time = current_time
            return -self.kp * error 
            
        dt = current_time - self.last_time
        if dt <= 0:
            return -self.kp * error
            
        # 1. Termine Proporzionale: Kp * errore
        p_term = self.kp * error
        
        # 2. Termine Integrale: Ki * sommatoria dell'errore nel tempo (Riemann dt)
        self.integral_error += error * dt
        i_term = self.ki * self.integral_error
        
        # 3. Termine Derivativo: Kd * (variazione dell'errore nell'ultimo dt tangenziale)
        d_term = self.kd * (error - self.prev_error) / dt
        
        # Aggiornamento memorie (t diventa t-1 per la passata successiva)
        self.prev_error = error
        self.last_time = current_time
        
        # Il motore aspetta W invertita per la compensazione geometrica della cinematica.
        output = -(p_term + i_term + d_term)
        return output

    def execute_command(self, command_data: dict) -> tuple:
        """
        Decodifica istruzioni di navigazione ad alto livello ed emette primitive base.
        Integra algoritmi di filtro (Low-pass) sul segnale in uscita per i motori.
        
        Args:
            command_data (dict): Payload proveniente dal layer logico, comprendente:
                                 - type: Tipologia manovra (es. "LINE_FOLLOW", "STOP")
                                 - error: Coefficiente scostamento (se LINE_FOLLOW)
                                 - target_speed: Velocità lineare di crociera impostata
                                 
        Returns:
            tuple: Coppia di velocità V (lineare m/s) e W (angolare rad/s) pronte
                   per essere incapsulate negli odometri o attuatori finali.
        """
        
        cmd_type = command_data.get("type", "UNKNOWN")
        V = 0.0
        W = 0.0

        if cmd_type == "LINE_FOLLOW":
            error = command_data.get("error", 0.0)
            target_speed = command_data.get("target_speed", 0.0)
            
            # 1. Elaborazione dell'uscita matematica nuda del PID
            target_w = self.calculate_pid(error)
            
            # --- FILTRO PASSA-BASSO (Exponential Moving Average / EMA) ---
            # La sterzata netta generata dal PID verrebbe passata in un unico ciclo a "scalino", 
            # causando bruschi sovraccarichi meccanici. Lo smoothing esponenziale rimedia prelevando 
            # l'inerzia precedente della sterzata pesata a 0.4 e iniettando solo la differenza pesata a 0.6.
            self.current_w = (self.current_w * 0.4) + (target_w * 0.6)
            
            W = self.current_w
            V = target_speed
            
        elif cmd_type == "STOP":
            # Procedura di reset totale di emergenza o stop.
            V = 0.0
            W = 0.0
            
            # Flush totale dei registri PID e inerziali per evitare 
            # "jump start" imprevedibili alla successiva ripartenza impulsiva
            self.prev_error = 0.0
            self.integral_error = 0.0
            self.last_time = None
            self.current_w = 0.0
            
        elif "v" in command_data and "w" in command_data:
            # Fallback legacy: se il controller superiore detta comandi cinematici espliciti
            V = command_data.get("v", 0.0)
            W = command_data.get("w", 0.0)

        # Logging cadenzato (ogni secondo) dell'attività del layer di base, 
        # saltando il flooding qualora il sistema sia in stand-by (0,0)
        current_time = time()
        if (V != 0.0 or W != 0.0) and (current_time - self.last_print_time > 1.0):
            # logging disabilitato su console ma tracciabile
            self.last_print_time = current_time
            
        return float(V), float(W)