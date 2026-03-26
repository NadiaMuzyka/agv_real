import time
from modules.connection.coppelia_connector import CoppeliaConnector
from modules.actuators.wheel_actuator import WheelsActuator

def run_test():
    print("🧪 Avvio test dell'attuatore WheelsActuator...")
    
    # 1. Ottieni la connessione a Coppelia
    connector = CoppeliaConnector()
    sim = connector.get_sim()
    
    if not sim:
        print("❌ Errore: CoppeliaSim non risponde. Controlla il tasto PLAY.")
        return

    # 2. Istanzia l'attuatore
    wheels = WheelsActuator(sim)

    try:
        # TEST 1: Avanti dritto
        print("➡️ Movimento lineare: v=0.2 m/s...")
        wheels.move(0.2, 0.0)
        time.sleep(2)

        # TEST 2: Rotazione
        print("🔄 Movimento angolare (rotazione): w=0.5 rad/s...")
        wheels.move(0.0, 0.5)
        time.sleep(2)

        # TEST 3: Stop
        print("🛑 STOP.")
        wheels.stop()
        
        print("✅ Test completato!")

    except Exception as e:
        print(f"❌ Errore durante il test: {e}")

if __name__ == "__main__":
    run_test()