def vai_avanti_metri(distanza, motori):
    sim.addLog(sim.verbosity_scriptinfos, f"Avanzo per {distanza} metri")
    pos_iniziale = sim.getObjectPosition(sim.getObject('/Robot'), -1)
    imposta_velocita(VELOCITA_CROCIERA, VELOCITA_CROCIERA, motori)
    import math
    while True:
        pos_attuale = sim.getObjectPosition(sim.getObject('/Robot'), -1)
        percorso = math.sqrt((pos_attuale[0] - pos_iniziale[0])**2 + (pos_attuale[1] - pos_iniziale[1])**2)
        if percorso >= distanza:
            break
        time.sleep(0.01)
    ferma(motori)
    sim.addLog(sim.verbosity_scriptinfos, f"Percorso effettivo: {percorso:.4f} m")
import time
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

# Connessione
client = RemoteAPIClient()
sim = client.getObject('sim')

# --- CONFIGURAZIONE ---
VELOCITA_CROCIERA = 3.0
VELOCITA_ROTAZIONE = 3.0
# Calibrazione: quanti secondi servono per fare 90 gradi? 
# Sperimenta con questo valore (es. 1.2 o 1.5) finché non è preciso
TEMPO_PER_90_GRADI = 4.0

# --- FUNZIONI DI MOVIMENTO ---

def imposta_velocita(v_sinistra, v_destra, motori):
    sim.setJointTargetVelocity(motori['ps'], v_sinistra)
    sim.setJointTargetVelocity(motori['as'], v_sinistra)
    sim.setJointTargetVelocity(motori['pd'], v_destra)
    sim.setJointTargetVelocity(motori['ad'], v_destra)

def vai_dritto(secondi, motori):
    sim.addLog(sim.verbosity_scriptinfos, f"Avanzo per {secondi}s")
    imposta_velocita(VELOCITA_CROCIERA, VELOCITA_CROCIERA, motori)
    time.sleep(secondi)
    ferma(motori)

def gira_sx(gradi, motori):
    sim.addLog(sim.verbosity_scriptinfos, f"Giro a sinistra di {gradi}° (preciso)")
    # Ottieni orientamento iniziale (asse Z locale)
    initial_orientation = sim.getObjectOrientation(sim.getObject('/Robot'), -1)[2]
    import math
    target_angle = initial_orientation + (gradi * math.pi / 180)
    target_angle = (target_angle + math.pi) % (2 * math.pi) - math.pi
    vel_rot_precisa = VELOCITA_ROTAZIONE * 0.4
    imposta_velocita(-vel_rot_precisa, vel_rot_precisa, motori)
    soglia = 0.005  # ~0.3°
    while True:
        current_orientation = sim.getObjectOrientation(sim.getObject('/Robot'), -1)[2]
        diff = (current_orientation - initial_orientation)
        diff = (diff + math.pi) % (2 * math.pi) - math.pi
        if abs(diff) >= abs(gradi * math.pi / 180) - soglia:
            break
        time.sleep(0.003)
    # Breve frenata per annullare inerzia
    imposta_velocita(vel_rot_precisa, -vel_rot_precisa, motori)
    time.sleep(0.025)
    ferma(motori)
    # Log angolo effettivo
    final_orientation = sim.getObjectOrientation(sim.getObject('/Robot'), -1)[2]
    effettivo = (final_orientation - initial_orientation)
    effettivo = (effettivo + math.pi) % (2 * math.pi) - math.pi
    sim.addLog(sim.verbosity_scriptinfos, f"Angolo effettivo ruotato: {math.degrees(effettivo):.3f}°")


def gira_dx(gradi, motori):
    sim.addLog(sim.verbosity_scriptinfos, f"Giro a destra di {gradi}° (preciso)")
    # Ottieni orientamento iniziale (asse Z locale)
    initial_orientation = sim.getObjectOrientation(sim.getObject('/Robot'), -1)[2]
    import math
    target_angle = initial_orientation - (gradi * math.pi / 180)
    target_angle = (target_angle + math.pi) % (2 * math.pi) - math.pi
    vel_rot_precisa = VELOCITA_ROTAZIONE * 0.4
    imposta_velocita(vel_rot_precisa, -vel_rot_precisa, motori)
    soglia = 0.005  # ~0.3°
    while True:
        current_orientation = sim.getObjectOrientation(sim.getObject('/Robot'), -1)[2]
        diff = (current_orientation - initial_orientation)
        diff = (diff + math.pi) % (2 * math.pi) - math.pi
        if abs(diff) >= abs(gradi * math.pi / 180) - soglia:
            break
        time.sleep(0.003)
    # Breve frenata per annullare inerzia
    imposta_velocita(-vel_rot_precisa, vel_rot_precisa, motori)
    time.sleep(0.025)
    ferma(motori)
    # Log angolo effettivo
    final_orientation = sim.getObjectOrientation(sim.getObject('/Robot'), -1)[2]
    effettivo = (final_orientation - initial_orientation)
    effettivo = (effettivo + math.pi) % (2 * math.pi) - math.pi
    sim.addLog(sim.verbosity_scriptinfos, f"Angolo effettivo ruotato: {math.degrees(effettivo):.3f}°")

def ferma(motori):
    imposta_velocita(0, 0, motori)

# --- LOGICA PRINCIPALE ---

def main():
    try:
        motori = {
            'ps': sim.getObject('/Robot/JointPS'),
            'as': sim.getObject('/Robot/JointAS'),
            'pd': sim.getObject('/Robot/JointPD'),
            'ad': sim.getObject('/Robot/JointAD')
        }
    except Exception as e:
        print(f"Errore: {e}")
        return

    sim.startSimulation()

    try:


        # Misura distanza percorsa in 2 secondi
        pos_start = sim.getObjectPosition(sim.getObject('/Robot'), -1)
        vai_dritto(2, motori)
        pos_end = sim.getObjectPosition(sim.getObject('/Robot'), -1)
        import math
        distanza_2s = math.sqrt((pos_end[0] - pos_start[0])**2 + (pos_end[1] - pos_start[1])**2)
        print(f"Distanza percorsa in 2 secondi: {distanza_2s:.4f} m")
        sim.addLog(sim.verbosity_scriptinfos, f"Distanza percorsa in 2 secondi: {distanza_2s:.4f} m")

        # Registra posizione prima della rotazione
        pos_before = sim.getObjectPosition(sim.getObject('/Robot'), -1)
        gira_sx(90, motori)
        # Registra posizione dopo la rotazione
        pos_after = sim.getObjectPosition(sim.getObject('/Robot'), -1)
        distanza = math.sqrt((pos_after[0] - pos_before[0])**2 + (pos_after[1] - pos_before[1])**2)
        print(f"Distanza tra le due rette (centro robot): {distanza:.4f} m")
        sim.addLog(sim.verbosity_scriptinfos, f"Distanza tra le due rette (centro robot): {distanza:.4f} m")

        sim.addLog(sim.verbosity_scriptinfos, f"Sto per fermarmi per 10 secondi di tempo simulato")
        ferma(motori)
        start_time = sim.getSimulationTime()
        while sim.getSimulationTime() - start_time < 10:
            time.sleep(0.05)  # Attendi brevemente per non bloccare il thread
        sim.addLog(sim.verbosity_scriptinfos, f"Sono passati i 10 secondi, riparto")

        # Esempio: avanza di 1 metro
        vai_avanti_metri(1.0, motori)
            

        sim.addLog(sim.verbosity_scriptinfos, "Percorso completato!")

    except KeyboardInterrupt:
        ferma(motori)

    time.sleep(1)
    sim.stopSimulation()

if __name__ == "__main__":
    main()