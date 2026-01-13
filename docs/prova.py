import time
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

# Connessione
client = RemoteAPIClient()
sim = client.getObject('sim')

# --- CONFIGURAZIONE ---
VELOCITA_CROCIERA = 3.0
VELOCITA_ROTAZIONE = 1.0
# Calibrazione: quanti secondi servono per fare 90 gradi? 
# Sperimenta con questo valore (es. 1.2 o 1.5) finché non è preciso
TEMPO_PER_90_GRADI = 7.0

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
    # Calcola il tempo proporzionale ai gradi (es. 90 gradi -> TEMPO_PER_90_GRADI)
    durata = (gradi / 90) * TEMPO_PER_90_GRADI
    sim.addLog(sim.verbosity_scriptinfos, f"Giro a sinistra di {gradi}°")
    imposta_velocita(-VELOCITA_ROTAZIONE, VELOCITA_ROTAZIONE, motori)
    time.sleep(durata)


def gira_dx(gradi, motori):
    durata = (gradi / 90) * TEMPO_PER_90_GRADI
    sim.addLog(sim.verbosity_scriptinfos, f"Giro a destra di {gradi}°")
    imposta_velocita(VELOCITA_ROTAZIONE, -VELOCITA_ROTAZIONE, motori)
    time.sleep(durata)
    ferma(motori)

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
        # ESEMPIO DI PERCORSO: Un quadrato
        #for i in range(2):

        vai_dritto(2, motori)
        gira_sx(90, motori)
        time.sleep(0.5) # Piccola pausa tra i movimenti
        vai_dritto(2, motori)
            

        sim.addLog(sim.verbosity_scriptinfos, "Percorso completato!")

    except KeyboardInterrupt:
        ferma(motori)

    time.sleep(1)
    sim.stopSimulation()

if __name__ == "__main__":
    main()