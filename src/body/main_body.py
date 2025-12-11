# FILE: src/body/main_body.py

import time
import os
import sys
import json

# Aggiusta il path per importare i moduli interni
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules/controllers'))

from redis_interface import RedisInterface
from low_level_manager import LowLevelManager

def main():
    print("🦾 [BODY] Avvio del Controllore (Ascolto Redis Pub/Sub)...")
    
    redis_iface = RedisInterface()
    manager = LowLevelManager()

    if not redis_iface.db:
        print("[BODY] Errore critico: Il Body non può ricevere comandi senza Redis.")
        return

    # 1. Iscrizione al canale dei comandi
    pubsub = redis_iface.subscribe_to_commands()
    if not pubsub:
        print("[BODY] Errore nell'iscrizione al canale Pub/Sub.")
        return

    # Ciclo di esecuzione principale (Loop di ascolto Pub/Sub)
    while True:
        # Attende bloccando il prossimo messaggio (timeout=0.1 per controllare periodicamente)
        message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1) 
        
        if message and message['data']:
            try:
                # 2. READ COMMAND (Deserializza il comando JSON)
                command = json.loads(message['data'])
                V = command.get("v", 0.0)
                W = command.get("w", 0.0)

                # 3. ACT (Invia al Controllore di Basso Livello)
                manager.execute_command(V, W)
                
            except json.JSONDecodeError:
                print("[BODY] Errore nella decodifica del comando ricevuto.")
        
        time.sleep(0.01) # Ciclo di pausa minimo

if __name__ == "__main__":
    main()