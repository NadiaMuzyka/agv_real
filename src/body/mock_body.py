import json
import time
import os
import sys
import signal
import random

from modules.connection.redis_interface import RedisInterface

REDIS_HOST = os.getenv("REDIS_HOST", "agv_redis")
COMMAND_CHANNEL = "agv_command_channel"
SENSOR_KEY = "agv_sensors"

is_running = True

def signal_handler(sig, frame):
    global is_running
    print("\n🛑 [MOCK BODY] Ricevuto segnale di spegnimento da Docker (SIGTERM)!")
    is_running = False
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

print(f"🦾 [MOCK BODY] Giacomino-Body avviato! Connessione a Redis su {REDIS_HOST}...")

redis_interface = RedisInterface()
if not redis_interface.db:
    print(f"❌ [MOCK BODY] Errore di connessione a Redis: impossibile inizializzare l'interfaccia.")
    sys.exit(1)

pubsub = redis_interface.subscribe_to_commands()
if not pubsub:
    print(f"❌ [MOCK BODY] Errore di connessione a Redis: impossibile creare la sottoscrizione ai comandi.")
    sys.exit(1)

print(f"🎧 [MOCK BODY] Sintonizzato sulla frequenza: '{COMMAND_CHANNEL}'")

# --- STATE MACHINE VARIABLES ---
current_action = None  # tipo di azione in corso: "MOVE_TO", "PICKUP", "DROP", "CHARGING"
action_started_at = None  # timestamp di inizio
action_ends_at = None  # timestamp di fine atteso
next_node_destination = None  # nodo destinazione per MOVE_TO

# --- BATTERY STATE ---
battery_level = 15.0
is_charging = False

# --- PERSON DETECTION STATE ---
person_detected_time = None
person_cooldown_until = None
PERSON_DURATION = 2.0  # Persona presente per 2 secondi
PERSON_COOLDOWN = 5.0  # Cooldown di 5 secondi tra i rilevamenti

# --- ACTION DURATIONS ---
MOVE_DURATION = 2.0
PICKUP_DURATION = 3.0
DROP_DURATION = 3.0

def get_sensors():
    """Restituisce lo stato corrente dei sensori letto da Redis."""
    return redis_interface.get_sensor_data(SENSOR_KEY)

def update_sensors(updates):
    """Aggiorna i sensori su Redis con i dati forniti"""
    redis_interface.update_sensor_data(SENSOR_KEY, updates)

def start_action(action_type, destination=None):
    """Avvia una nuova azione"""
    global current_action, action_started_at, action_ends_at, next_node_destination
    current_action = action_type
    action_started_at = time.time()
    next_node_destination = destination

    if action_type == "MOVE_TO":
        action_ends_at = action_started_at + MOVE_DURATION
        print(f"🚶 [MOCK BODY] In movimento verso {destination}...")
        update_sensors({"am_i_in_a_node": False})
        
    elif action_type == "PICKUP":
        action_ends_at = action_started_at + PICKUP_DURATION
        print(f"📦 [MOCK BODY] Inizio prelievo...")
    elif action_type == "DROP":
        action_ends_at = action_started_at + DROP_DURATION
        print(f"📦 [MOCK BODY] Inizio consegna...")
    elif action_type == "START_CHARGE":
        action_ends_at = None  # Non ha una fine fissa
        print(f"🔋 [MOCK BODY] Inizio ricarica...")

def stop_action():
    """Arresta immediatamente l'azione in corso"""
    global current_action, action_started_at, action_ends_at
    if current_action:
        print(f"🛑 [MOCK BODY] Stop ricevuto. Interruzione di {current_action}.")
        current_action = None
        action_started_at = None
        action_ends_at = None

def complete_action():
    """Completa l'azione in corso"""
    global current_action

    if current_action == "MOVE_TO":
        sensors = get_sensors()
        path_to_target = sensors.get("path_to_target", [])

        if isinstance(path_to_target, list) and len(path_to_target) > 0:
            aggiornamenti = {
                "current_position": path_to_target[0],
                "path_to_target": path_to_target[1:]
            }
            if len(path_to_target) > 1:
                aggiornamenti["next_node"] = path_to_target[1]
            else:
                aggiornamenti["next_node"] = None

            print(f"📍 [MOCK BODY] Arrivato al nodo: {path_to_target[0]}!")
            update_sensors(aggiornamenti)
        else:
            print(f"📍 [MOCK BODY] Arrivato a destinazione: {next_node_destination}!")
            update_sensors({
                "current_position": next_node_destination,
                "next_node": None
            })

        update_sensors({"am_i_in_a_node": True})
    elif current_action == "PICKUP":
        print(f"✅ [MOCK BODY] Prelievo completato!")
        update_sensors({"is_load": True})
    elif current_action == "DROP":
        print(f"✅ [MOCK BODY] Consegna completata!")
        update_sensors({"is_load": False})

    current_action = None
    action_started_at = None
    action_ends_at = None

    # Scartiamo tutti i messaggi duplicati rimasti in coda
    while pubsub.get_message(ignore_subscribe_messages=True):
        pass

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
            print(f"👤 [MOCK BODY] Persona scomparsa.")
            update_sensors({"person_detected": False})
        return

    # Probabilità di rilevare una persona solo durante movimento
    if current_action == "MOVE_TO":
        if random.random() < 0.10:  # 10% di probabilità
            person_detected_time = now
            print(f"👤 [MOCK BODY] Rilevata una persona nel percorso!")
            update_sensors({"person_detected": True})

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

            if cmd_type == "STOP":
                stop_action()
            
            elif cmd_type == "MOVE_TO" and not current_action:
                destination = comando.get("next_node")
                if destination:
                    is_charging = False
                    start_action("MOVE_TO", destination)

            elif cmd_type == "PICKUP" and not current_action:
                start_action("PICKUP")

            elif cmd_type == "DROP" and not current_action:
                start_action("DROP")

            elif cmd_type == "START_CHARGE" and not current_action:
                is_charging = True
                start_action("START_CHARGE")

        except Exception:
            pass  # Ignora errori di parsing

    # --- CHECK AZIONE IN CORSO ---
    if current_action and action_ends_at:
        if now >= action_ends_at:
            complete_action()

    # --- SIMULAZIONE BATTERIA ---
    if is_charging:
        battery_level = min(100.0, battery_level + 5.0)
        update_sensors({"battery_level": battery_level})
        if battery_level >= 100.0:
            print(f"🔋 [MOCK BODY] Batteria completamente carica!")
            is_charging = False
            current_action = None
    else:
        # Consuma batteria durante il movimento
        if current_action == "MOVE_TO":
            battery_level = max(0.0, battery_level - 0.5)
        update_sensors({"battery_level": battery_level})

    # --- SIMULAZIONE PERSONE ---
    simulate_person()

    time.sleep(0.05)  # Ritmo del loop
