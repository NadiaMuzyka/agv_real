# FILE: src/body/main_body.py

import time
import os
import sys

# Aggiusta il path per importare i moduli interni
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules/controllers'))

from redis_interface import RedisInterface
from low_level_manager import LowLevelManager

# --- COSTANTI ---
COMMAND_KEY = "agv_command"

def main():
    print("🦾 [BODY] Avvio del Controllore (Ascolto Redis Message Broker)...")
    
    redis_iface = RedisInterface()
    manager = LowLevelManager()

    if not redis_iface.db:
        print("[BODY] Errore critico: Il Body non può ricevere comandi senza Redis.")
        return

    last_command = {"v": -1.0, "w": -1.0} 

    while True:
        # 1. READ COMMAND (Legge i comandi dal Brain via Redis)
        command = redis_iface.get_command(COMMAND_KEY)
        V = command.get("v", 0.0)
        W = command.get("w", 0.0)
        
        # 2. ACT (Invia al Controllore di Basso Livello solo se il comando è cambiato)
        if V != last_command["v"] or W != last_command["w"]:
            manager.execute_command(V, W)
            last_command["v"] = V
            last_command["w"] = W

        time.sleep(0.1) 

if __name__ == "__main__":
    main()