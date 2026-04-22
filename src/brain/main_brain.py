# FILE: src/brain/main_brain.py (VERSIONE CORRETTA)
import time
import sys
import os
import shutil
import py_trees
import signal # Per gestire l'interruzione del processo con Ctrl+C

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.bt_manager import crea_albero_agv
from modules.redis_interface import RedisInterface 
from modules.logic_controller import LogicController 

def main():
    print("🧠 Avvio BRAIN. Implementazione Logic Controller su Redis Pub/Sub...")
    
    # --- RIPRISTINO INFO_PACK DAL BACKUP ---
    info_pack_path = os.path.join(os.path.dirname(__file__), 'docs', 'info_pack.json')
    backup_path = os.path.join(os.path.dirname(__file__), 'docs', 'info_pack_backup.json')
    try:
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, info_pack_path)
            print(f"✓ info_pack.json ripristinato dal backup")
    except Exception as e:
        print(f"⚠ Avviso: Impossibile ripristinare info_pack.json dal backup: {e}")
    
    redis_manager = RedisInterface() 
    if not redis_manager.db:
        print("[BRAIN] Errore critico: Uscita per mancata connessione a Redis.")
        return 
    
    # --- INIZIALIZZAZIONE LOGIC CONTROLLER ---
    logic_controller = LogicController(redis_manager) 
       
    # --- INIZIALIZZAZIONE BLACKBOARD ---
    # Creiamo un client per scrivere i dati nella memoria del BT
    blackboard_client = py_trees.blackboard.Client(name="ClientBrain")
    # Registriamo la chiave per il Logic Controller, che sarà un oggetto condiviso
    blackboard_client.register_key(key="logic_controller", access=py_trees.common.Access.WRITE)
    blackboard_client.logic_controller = logic_controller

    # Creazione e setup del Behavior Tree  
    behavior_tree = crea_albero_agv() 
    tree_executor = py_trees.trees.BehaviourTree(behavior_tree)
    tree_executor.setup(timeout=15) 

    def spegnimento_sicuro(signum, frame):
        print("\n[BRAIN] Ricevuto segnale di spegnimento da Docker (SIGTERM)!")
        raise KeyboardInterrupt() # Scatena l'eccezione che ti fa uscire dal while!

    # Diciamo a Python di usare questa funzione quando Docker bussa alla porta
    signal.signal(signal.SIGTERM, spegnimento_sicuro)

    print("[BRAIN] Ingresso nel ciclo principale...")
    try:
        while True:
            
            #aggiornamento della blackboard con i dati dei sensori elaborati provenienti da Redis
            logic_controller.update_blackboard_reading_from_redis()
            
            #tick del BT
            tree_executor.tick()
            
            # Il Brain invia comandi solo quando il BT fa un tick e ne ha bisogno.
            time.sleep(0.1) 

    except KeyboardInterrupt:
        print("Spegnimento Brain...")

if __name__ == "__main__":
    main()