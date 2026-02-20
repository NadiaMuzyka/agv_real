import math
import time
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

class RobotAGV:
    def vai_avanti_return_dist(self, metri_target, velocita=1.5):
        self.ferma()
        time.sleep(0.05)
        pos_iniziale = self.sim.getObjectPosition(self.robot_handle, -1)
        orient_iniziale = self.sim.getObjectOrientation(self.robot_handle, -1)
        angolo_iniziale = orient_iniziale[2]
        # Pre-correzione di orientamento a motori fermi
        Kp_prec = 12.0
        for _ in range(10):
            angolo_attuale = self.sim.getObjectOrientation(self.robot_handle, -1)[2]
            errore_angolo = self._normalize_delta(angolo_iniziale, angolo_attuale)
            if abs(math.degrees(errore_angolo)) < 0.05:
                break
            correzione = errore_angolo * Kp_prec
            self.set_velocita(-correzione, correzione)
            time.sleep(0.01)
            self.ferma()
            time.sleep(0.01)
        self.last_pos_sx, self.last_pos_dx = self._get_raw_encoder_positions()
        distanza_percorsa = 0
        Kp = 12.0
        step = 0
        while distanza_percorsa < metri_target:
            angolo_attuale = self.sim.getObjectOrientation(self.robot_handle, -1)[2]
            errore_angolo = self._normalize_delta(angolo_iniziale, angolo_attuale)
            correzione = errore_angolo * Kp
            self.set_velocita(velocita - correzione, velocita + correzione)
            curr_sx, curr_dx = self._get_raw_encoder_positions()
            delta_sx = abs(self._normalize_delta(curr_sx, self.last_pos_sx))
            delta_dx = abs(self._normalize_delta(curr_dx, self.last_pos_dx))
            distanza_percorsa += ((delta_sx + delta_dx) / 2) * self.raggio_ruota
            self.last_pos_sx, self.last_pos_dx = curr_sx, curr_dx
            step += 1
            time.sleep(0.002)
        self.ferma()
        return distanza_percorsa
    def __init__(self, client):
        self.sim = client.getObject('sim')
        # Dati del tuo robot
        self.raggio_ruota = 0.1  # raggio = 10 cm (diametro 20 cm)
        self.interasse = 0.5     # interasse = 50 cm
        
        try:
            self.robot_handle = self.sim.getObject('/Robot')
            self.motori = {
                'ps': self.sim.getObject('/Robot/JointPS'),
                'as': self.sim.getObject('/Robot/JointAS'),
                'pd': self.sim.getObject('/Robot/JointPD'),
                'ad': self.sim.getObject('/Robot/JointAD')
            }
            self.log("Sistema pronto.")
        except Exception as e:
            print(f"Errore nel recupero degli oggetti: {e}")
        
        # Variabili per l'odometria
        self.last_pos_sx = 0
        self.last_pos_dx = 0

    def log(self, messaggio):
        self.sim.addLog(self.sim.verbosity_scriptinfos, f"[Python AGV] {messaggio}")

    def set_velocita(self, v_sx, v_dx):
        # Imposta tutte le velocità in un'unica chiamata batch per massima sincronia
        for handle, vel in zip([
            self.motori['as'], self.motori['ps'], self.motori['ad'], self.motori['pd']],
            [v_sx, v_sx, v_dx, v_dx]):
            self.sim.setJointTargetVelocity(handle, vel)

    def ferma(self):
        self.set_velocita(0, 0)

    def _get_raw_encoder_positions(self):
        """Legge i radianti attuali dai giunti"""
        pos_sx = (self.sim.getJointPosition(self.motori['as']) + self.sim.getJointPosition(self.motori['ps'])) / 2
        pos_dx = (self.sim.getJointPosition(self.motori['ad']) + self.sim.getJointPosition(self.motori['pd'])) / 2
        return pos_sx, pos_dx

    def _normalize_delta(self, attuale, precedente):
        """Gestisce il salto angolare (-pi a +pi)"""
        diff = attuale - precedente
        while diff > math.pi: diff -= 2 * math.pi
        while diff < -math.pi: diff += 2 * math.pi
        return diff

    # --- MOVIMENTO RETTILINEO (ODOMETRIA) ---
    def vai_avanti(self, metri_target, velocita=1.5):
        self.ferma()  # 1. Imposta velocità motori a zero prima di leggere posizione iniziale
        time.sleep(0.05)  # pausa più lunga per assicurarsi che il robot sia fermo
        self.log(f"Avanzo di {metri_target}m con correzione di rotta (velocità ridotta)")
        pos_iniziale = self.sim.getObjectPosition(self.robot_handle, -1)
        orient_iniziale = self.sim.getObjectOrientation(self.robot_handle, -1)
        print(f"PRIMA: x={pos_iniziale[0]:.3f}, y={pos_iniziale[1]:.3f}, gamma={math.degrees(orient_iniziale[2]):.2f}°")
        self.log(f"PRIMA: x={pos_iniziale[0]:.3f}, y={pos_iniziale[1]:.3f}, gamma={math.degrees(orient_iniziale[2]):.2f}°")
        angolo_iniziale = orient_iniziale[2]

        # Pre-correzione di orientamento a motori fermi
        Kp_prec = 12.0
        for _ in range(10):
            angolo_attuale = self.sim.getObjectOrientation(self.robot_handle, -1)[2]
            errore_angolo = self._normalize_delta(angolo_iniziale, angolo_attuale)
            if abs(math.degrees(errore_angolo)) < 0.05:
                break
            correzione = errore_angolo * Kp_prec
            # Applica una piccola correzione di velocità per allineare
            self.set_velocita(-correzione, correzione)
            time.sleep(0.01)
            self.ferma()
            time.sleep(0.01)

        self.last_pos_sx, self.last_pos_dx = self._get_raw_encoder_positions()
        distanza_percorsa = 0
        Kp = 12.0  # Aumentato per correzione più forte
        step = 0
        # 2. Applica subito la correzione di rotta già allo step 0
        while distanza_percorsa < metri_target:
            angolo_attuale = self.sim.getObjectOrientation(self.robot_handle, -1)[2]
            errore_angolo = self._normalize_delta(angolo_iniziale, angolo_attuale)
            correzione = errore_angolo * Kp
            self.set_velocita(velocita - correzione, velocita + correzione)
            curr_sx, curr_dx = self._get_raw_encoder_positions()
            delta_sx = abs(self._normalize_delta(curr_sx, self.last_pos_sx))
            delta_dx = abs(self._normalize_delta(curr_dx, self.last_pos_dx))
            distanza_percorsa += ((delta_sx + delta_dx) / 2) * self.raggio_ruota
            self.last_pos_sx, self.last_pos_dx = curr_sx, curr_dx
            # 4. Rileggi posizione e correggi rotta ad ogni step (già presente)
            if step % 10 == 0:
                pos = self.sim.getObjectPosition(self.robot_handle, -1)
                orient = self.sim.getObjectOrientation(self.robot_handle, -1)
                print(f"Step {step}: x={pos[0]:.3f}, y={pos[1]:.3f}, gamma={math.degrees(orient[2]):.2f}°")
                self.log(f"Step {step}: x={pos[0]:.3f}, y={pos[1]:.3f}, gamma={math.degrees(orient[2]):.2f}°")
            step += 1
            # 3. Aumenta frequenza ciclo di controllo (sleep più breve)
            time.sleep(0.002)
        self.ferma()
        pos_finale = self.sim.getObjectPosition(self.robot_handle, -1)
        orient_finale = self.sim.getObjectOrientation(self.robot_handle, -1)
        print(f"DOPO: x={pos_finale[0]:.3f}, y={pos_finale[1]:.3f}, gamma={math.degrees(orient_finale[2]):.2f}°")
        self.log(f"DOPO: x={pos_finale[0]:.3f}, y={pos_finale[1]:.3f}, gamma={math.degrees(orient_finale[2]):.2f}°")
        print(f"Distanza percorsa (odometria): {distanza_percorsa:.4f} m")
        self.log(f"Distanza percorsa (odometria): {distanza_percorsa:.4f} m")

    # --- ROTAZIONE (ORIENTAMENTO OGGETTO) ---
    def gira_sx(self, gradi, velocita_base=3.0):
        self.log(f"Giro a sinistra di {gradi}° (Orientamento)")
        initial_orientation = self.sim.getObjectOrientation(self.robot_handle, -1)[2]
        
        vel_rot = velocita_base * 0.4
        self.set_velocita(-vel_rot, vel_rot)
        
        soglia = 0.005
        while True:
            current_orientation = self.sim.getObjectOrientation(self.robot_handle, -1)[2]
            diff = (current_orientation - initial_orientation)
            diff = (diff + math.pi) % (2 * math.pi) - math.pi
            if abs(diff) >= abs(math.radians(gradi)) - soglia:
                break
            time.sleep(0.003)
        
        # Frenata attiva per inerzia
        self.set_velocita(vel_rot, -vel_rot)
        time.sleep(0.025)
        self.ferma()
        self.log(f"Angolo finale: {math.degrees(diff):.2f}°")

    def gira_dx(self, gradi, velocita_base=3.0):
        self.log(f"Giro a destra di {gradi}° (Orientamento)")
        initial_orientation = self.sim.getObjectOrientation(self.robot_handle, -1)[2]
        
        vel_rot = velocita_base * 0.4
        self.set_velocita(vel_rot, -vel_rot)
        
        soglia = 0.005
        while True:
            current_orientation = self.sim.getObjectOrientation(self.robot_handle, -1)[2]
            diff = (current_orientation - initial_orientation)
            diff = (diff + math.pi) % (2 * math.pi) - math.pi
            if abs(diff) >= abs(math.radians(gradi)) - soglia:
                break
            time.sleep(0.003)
        
        # Frenata attiva
        self.set_velocita(-vel_rot, vel_rot)
        time.sleep(0.025)
        self.ferma()
        self.log(f"Angolo finale: {math.degrees(diff):.2f}°")

def main():
    client = RemoteAPIClient()
    sim = client.getObject('sim')
    agv = RobotAGV(client)

    sim.startSimulation()

    try:
        risultati = []
        # Valori di partenza desiderati
        pos_reset = [9.0, 9.0, 0.0]
        orient_reset = [0.0, 0.0, -math.pi/2]  # gamma = -90°
        for i in range(10):
            agv.log(f"--- Simulazione {i+1}/10 ---")
            # Reset posizione e orientamento
            agv.sim.setObjectPosition(agv.robot_handle, -1, pos_reset)
            agv.sim.setObjectOrientation(agv.robot_handle, -1, orient_reset)
            time.sleep(0.1)
            distanza = agv.vai_avanti_return_dist(1.0)
            pos = agv.sim.getObjectPosition(agv.robot_handle, -1)
            orient = agv.sim.getObjectOrientation(agv.robot_handle, -1)
            risultati.append(f"Sim {i+1}: x={pos[0]:.3f}, y={pos[1]:.3f}, gamma={math.degrees(orient[2]):.2f}, dist={distanza:.4f} m\n")
            time.sleep(0.5)
        # Salva i risultati su file
        with open("risultati_simulazioni.txt", "w") as f:
            f.writelines(risultati)
        agv.log("Risultati delle simulazioni salvati in risultati_simulazioni.txt")
    except KeyboardInterrupt:
        agv.ferma()
    finally:
        agv.ferma()
        time.sleep(1)
        sim.stopSimulation()

if __name__ == "__main__":
    main()