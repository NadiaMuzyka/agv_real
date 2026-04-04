import redis
import json
import time
import os
import sys
import signal

REDIS_HOST = os.getenv("REDIS_HOST", "agv_redis")
COMMAND_CHANNEL = "agv_command_channel" 
SENSOR_KEY = "agv_sensors"

# 1. FLAG PER LO SPEGNIMENTO PULITO
is_running = True

def signal_handler(sig, frame):
    global is_running
    print("\n🛑 [MOCK BODY] Ricevuto segnale di spegnimento da Docker (SIGTERM)!")
    is_running = False
    sys.exit(0)

# Colleghiamo il segnale di chiusura alla nostra funzione
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

print(f"🦾 [MOCK BODY] Giacomino-Body avviato! Connessione a Redis su {REDIS_HOST}...")

try:
    r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe(COMMAND_CHANNEL)
    print(f"🎧 [MOCK BODY] Sintonizzato sulla frequenza: '{COMMAND_CHANNEL}'")
except Exception as e:
    print(f"❌ [MOCK BODY] Errore di connessione a Redis: {e}")
    sys.exit(1)

ultimo_nodo_destinazione = None

# 2. CICLO NON BLOCCANTE
while is_running:
    # Usiamo get_message con timeout, così il ciclo può sbloccarsi e controllare is_running
    message = pubsub.get_message(timeout=1.0)
    
    if message and message['type'] == 'message':
        try:
            raw_data = message['data'].replace("'", '"')
            comando = json.loads(raw_data)
            tipo = comando.get("type")

            if tipo == "MOVE_TO":
                destinazione = comando.get("next_node")
                
                # 3. CONTROLLO ANTI-SPAM
                if destinazione != ultimo_nodo_destinazione:
                    print(f"🚶‍♂️ [MOCK BODY] Ricevuto ordine: MOVE_TO -> {destinazione}. In viaggio...")
                    ultimo_nodo_destinazione = destinazione
                    
                    # Simuliamo il viaggio
                    time.sleep(2.0) 
                    
                    print(f"📍 [MOCK BODY] Arrivato a destinazione: {destinazione}!")

                    dati_grezzi = r.get(SENSOR_KEY)
                    sensori_attuali = json.loads(dati_grezzi) if dati_grezzi else {}
                    
                    sensori_attuali["current_position"] = destinazione
                    sensori_attuali["am_i_in_a_node"] = True
                    
                    r.set(SENSOR_KEY, json.dumps(sensori_attuali))
                    print(f"✅ [MOCK BODY] Sensori aggiornati!")
                
        except json.JSONDecodeError as e:
            pass # Ignoriamo errori di decodifica per non bloccare il robot
        except Exception as e:
            print(f"⚠️ [MOCK BODY] Errore generico: {e}")


