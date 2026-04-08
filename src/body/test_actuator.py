import time
import math
# Assicurati che questi import corrispondano alla struttura reale delle tue cartelle
from modules.connection.coppelia_connector import CoppeliaConnector
from modules.actuators.wheel_actuator import WheelsActuator 
#docker compose run --rm body python test_actuator.py

# --- PARAMETRI DI CONFIGURAZIONE ---
# In una codebase aziendale/strutturata queste costanti risiederebbero 
# in un file 'config.py', in un '.env' o in un file 'settings.json'.
TEST_LINEAR_VEL = 0.1   # Velocità lineare di test (m/s)
TEST_ANGULAR_VEL = 0.5  # Velocità angolare di test (rad/s)

def run_test():
    print("🧪 Avvio test di calibrazione cinematica...")
    
    # 1. Connessione a CoppeliaSim
    connector = CoppeliaConnector()
    sim = connector.get_sim()
    
    if not sim:
        print("❌ Errore: CoppeliaSim non risponde. Hai premuto PLAY?")
        return

    # 2. Istanzia l'attuatore
    wheels = WheelsActuator(sim)

    try:
        # TEST 1: Movimento lineare (Avanti)
        print(f"➡️ TEST 1: Avanti dritto a {TEST_LINEAR_VEL} m/s per 5 secondi...")
        wheels.move(TEST_LINEAR_VEL, 0.0)
        time.sleep(5.0)
        
        wheels.stop()
        sim.addLog(sim.verbosity_scriptinfos, "Ciao dal terminale Python!")
        print("🛑 Pausa pre-rotazione...")
        time.sleep(2.0)
        
        # TEST 2: Rotazione 90 Gradi (Destra)
        print(f"🔄 TEST 2: Rotazione di 90 gradi a destra (w=-{TEST_ANGULAR_VEL})...")
        # 90 gradi in radianti è pi/2. 
        # A una velocità angolare (w) ci vorrà tempo = (pi/2) / w
        w_target = -TEST_ANGULAR_VEL  # negativo per girare a destra
        duration = (math.pi / 2) / TEST_ANGULAR_VEL
        
        wheels.move(0.0, w_target)
        time.sleep(duration)
        
        wheels.stop()
        print("🛑 Pausa pre-rotazione a sinistra...")
        time.sleep(2.0)
        
        # TEST 3: Rotazione 90 Gradi (Sinistra)
        print(f"🔄 TEST 3: Rotazione di 90 gradi a sinistra (w={TEST_ANGULAR_VEL})...")
        w_target_left = TEST_ANGULAR_VEL  # positivo per girare a sinistra
        duration_left = (math.pi / 2) / TEST_ANGULAR_VEL
        
        wheels.move(0.0, w_target_left)
        time.sleep(duration_left)

        # Stop finale

        print("🛑 STOP. Controlla l'angolo del robot in CoppeliaSim!")
        wheels.stop()
        
        print("✅ Test completato con successo!")

    except Exception as e:
        print(f"❌ Errore durante l'esecuzione del test: {e}")
        wheels.stop()

if __name__ == "__main__":
    run_test()