import json
import time
import os
import sys
import signal
import random

from modules.connection.redis_interface import RedisInterface

REDIS_HOST = os.getenv("REDIS_HOST", "agv_redis")
COMMAND_CHANNEL = "agv_command_channel"
SENSOR_KEY = "brain_memory"

is_running = True


def log_event(message):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def signal_handler(sig, frame):
    global is_running
    log_event("\n🛑 [MOCK BODY] Ricevuto segnale di spegnimento da Docker (SIGTERM)!")
    is_running = False
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

log_event(f"🦾 [MOCK BODY] Giacomino-Body avviato! Connessione a Redis su {REDIS_HOST}...")

redis_interface = RedisInterface()
if not redis_interface.db:
    log_event("❌ [MOCK BODY] Errore di connessione a Redis: impossibile inizializzare l'interfaccia.")
    sys.exit(1)

pubsub = redis_interface.subscribe_to_commands()
if not pubsub:
    log_event("❌ [MOCK BODY] Errore di connessione a Redis: impossibile creare la sottoscrizione ai comandi.")
    sys.exit(1)

log_event(f"🎧 [MOCK BODY] Sintonizzato sulla frequenza: '{COMMAND_CHANNEL}'")

# --- STATE MACHINE VARIABLES ---
current_action = None  # tipo di azione in corso: "MOVE_TO", "PICKUP", "DROP", "CHARGING"
action_started_at = None  # timestamp di inizio
action_ends_at = None  # timestamp di fine atteso
next_node_destination = None  # nodo destinazione per MOVE_TO


# --- PERSON DETECTION STATE ---
person_detected_time = None
person_cooldown_until = None
PERSON_DURATION = 2.0  # Persona presente per 2 secondi
PERSON_COOLDOWN = 5.0  # Cooldown di 5 secondi tra i rilevamenti

# --- ACTION DURATIONS ---
MOVE_DURATION = 2.0
PICKUP_DURATION = 3.0
DROP_DURATION = 3.0


#region get/update sensors (Utilizzano Redis Interface)
def get_sensors():
    """Restituisce lo stato corrente dei sensori letto da Redis."""
    return redis_interface.get_sensor_data(SENSOR_KEY) or {}

def update_sensors(updates):
    """Aggiorna i sensori su Redis con i dati forniti"""
    redis_interface.update_sensor_data(SENSOR_KEY, updates)
    log_event(f"📡 [MOCK BODY] Sensori aggiornati: {updates}")
#endregion

#region STOP action (Interruzione immediata)
def stop_action():
    """Arresta immediatamente l'azione in corso"""
    global current_action, action_started_at, action_ends_at
    if current_action:
        log_event(f"🛑 [MOCK BODY] Stop ricevuto. Interruzione di {current_action}.")
        current_action = None
        action_started_at = None
        action_ends_at = None
    else:
        log_event("🛑 [MOCK BODY] STOP ricevuto ma nessuna azione era attiva.")
#endregion

#region START/COMPLETE action
def start_action(action_type, destination=None):
    """Avvia una nuova azione"""
    global current_action, action_started_at, action_ends_at, next_node_destination
    current_action = action_type
    action_started_at = time.time()
    next_node_destination = destination

    if action_type == "MOVE_TO":
        action_ends_at = action_started_at + MOVE_DURATION
        log_event(f"🚶 [MOCK BODY] In movimento verso {destination}...")
        update_sensors({"am_i_in_a_node": False})
        
    elif action_type == "PICKUP":
        action_ends_at = action_started_at + PICKUP_DURATION
        log_event("📦 [MOCK BODY] Inizio prelievo...")
    elif action_type == "DROP":
        action_ends_at = action_started_at + DROP_DURATION
        log_event("📦 [MOCK BODY] Inizio consegna...")

def complete_action():
    """Completa l'azione in corso"""
    global current_action 
    
    # Quantità di batteria consumata per ogni azione
    battery_consumption = 1.0

    # LETTURA SENSORI
    sensors = get_sensors()

    # CALCOLO CONSUMO BATTERIA
    current_BATTERY = sensors.get("battery_level", 100.0)
    new_battery = max(0.0, current_BATTERY - battery_consumption)  # Consumo fisso per semplicità

    if current_action == "MOVE_TO":
        path_to_target = sensors.get("path_to_target", [])

        # se sto ancora navigando verso il nodo target, aggiorno la posizione al nodo successivo
        if isinstance(path_to_target, list) and len(path_to_target) > 0:
            aggiornamenti = {
                "current_position": path_to_target[0],
                "path_to_target": path_to_target[1:],
                "am_i_in_a_node": True,
                "battery_level": new_battery
            }
            if len(path_to_target) > 1:
                aggiornamenti["next_node"] = path_to_target[1]
            else:
                aggiornamenti["next_node"] = None
            log_event(f"📍 [MOCK BODY] Arrivato al nodo: {path_to_target[0]}!")
            update_sensors(aggiornamenti)

        # altrimenti, se non ho più nodi in path_to_target, arrivo a destinazione
        else:
            log_event(f"📍 [MOCK BODY] Arrivato a destinazione: {next_node_destination}!")
            update_sensors({
                "current_position": next_node_destination,
                "next_node": None,
                "am_i_in_a_node": True,
                "battery_level": new_battery
            })

        update_sensors({"am_i_in_a_node": True})
    elif current_action == "PICKUP":
        log_event("✅ [MOCK BODY] Prelievo completato!")
        update_sensors({
            "is_load": True,
            "battery_level": new_battery
        })
    elif current_action == "DROP":
        log_event("✅ [MOCK BODY] Consegna completata!")
        update_sensors({
            "is_load": False,
            "battery_level": new_battery
        })

    current_action = None
    action_started_at = None
    action_ends_at = None

    # Scartiamo tutti i messaggi duplicati rimasti in coda
    while pubsub.get_message(ignore_subscribe_messages=True):
        pass
#endregion

#region simulate person detection
def simulate_person():
    """Simula la comparsa di una persona durante il movimento o prima di partire"""
    global person_detected_time, person_cooldown_until

    now = time.time()

    # Controlla se siamo in cooldown
    if person_cooldown_until and now < person_cooldown_until:
        return

    # Persona rilevata attualmente?
    if person_detected_time:
        if now - person_detected_time > PERSON_DURATION:
            # Fine della persona
            person_detected_time = None
            person_cooldown_until = now + PERSON_COOLDOWN
            log_event("👤 [MOCK BODY] Persona scomparsa.")
            update_sensors({"person_detected": False})
        return

    # Probabilità di rilevare una persona solo durante movimento
    if current_action == "MOVE_TO":
        if random.random() < 0.10:  # 10% di probabilità
            person_detected_time = now
            log_event("👤 [MOCK BODY] Rilevata una persona nel percorso!")
            update_sensors({"person_detected": True})
#endregion

# --- MAIN LOOP ---
while is_running:
    now = time.time()

    # Leggi UN SOLO messaggio
    message = pubsub.get_message(timeout=0.05)

    if message and message['type'] == 'message':
        try:
            raw_data = message['data'].replace("'", '"')
            comando = json.loads(raw_data)
            cmd_type = comando.get("type")

            # log dei comandi ricevuti
            if cmd_type in ["MOVE_TO", "STOP", "PICKUP", "DROP"]:
                log_event(f"📥 [MOCK BODY] Comando ricevuto: {cmd_type}")

            if cmd_type == "STOP":
                stop_action()
            
            elif cmd_type == "MOVE_TO":
                if current_action:
                    log_event(f"⏭️ [MOCK BODY] MOVE_TO ignorato: azione in corso ({current_action}).")
                    continue
                destination = comando.get("next_node")
                if destination:
                    start_action("MOVE_TO", destination)
                else:
                    log_event("⚠️ [MOCK BODY] MOVE_TO senza next_node: comando ignorato.")

            elif cmd_type == "PICKUP":
                if current_action:
                    log_event(f"⏭️ [MOCK BODY] PICKUP ignorato: azione in corso ({current_action}).")
                    continue
                start_action("PICKUP")

            elif cmd_type == "DROP":
                if current_action:
                    log_event(f"⏭️ [MOCK BODY] DROP ignorato: azione in corso ({current_action}).")
                    continue
                start_action("DROP")

            else:
                log_event(f"⚠️ [MOCK BODY] Comando non riconosciuto: {cmd_type}")

        except Exception as e:
            log_event(f"❌ [MOCK BODY] Errore parsing comando: {e}")

    # --- CHECK AZIONE IN CORSO ---
    if current_action and action_ends_at:
        if now >= action_ends_at:
            complete_action()

    # --- SIMULAZIONE PERSONE ---
    simulate_person()

    time.sleep(0.05)  # Ritmo del loop