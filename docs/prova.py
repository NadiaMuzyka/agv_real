import math
import time
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

class RobotAGV:
    def __init__(self, client):
        self.client = client # Ci serve per il comando .step()
        self.sim = client.getObject('sim')
        self.raggio_ruota = 0.1  
        self.interasse = 0.5     
        
        try:
            self.robot_handle = self.sim.getObject('/Robot')
            self.motori = {
                'ps': self.sim.getObject('/Robot/JointPS'),
                'as': self.sim.getObject('/Robot/JointAS'),
                'pd': self.sim.getObject('/Robot/JointPD'),
                'ad': self.sim.getObject('/Robot/JointAD')
            }
        except Exception as e:
            print(f"Errore handle: {e}")
        
        self.last_pos_sx = 0
        self.last_pos_dx = 0

    def set_velocita(self, v_sx, v_dx):
        for handle, vel in zip([self.motori['as'], self.motori['ps'], self.motori['ad'], self.motori['pd']],
                               [v_sx, v_sx, v_dx, v_dx]):
            self.sim.setJointTargetVelocity(handle, vel)

    def ferma(self):
        # 2. STOP FORZATO: Ripetiamo il comando per assicurarci che venga recepito
        for _ in range(5):
            self.set_velocita(0, 0)

    def _get_raw_encoder_positions(self):
        pos_sx = (self.sim.getJointPosition(self.motori['as']) + self.sim.getJointPosition(self.motori['ps'])) / 2
        pos_dx = (self.sim.getJointPosition(self.motori['ad']) + self.sim.getJointPosition(self.motori['pd'])) / 2
        return pos_sx, pos_dx

    def _normalize_delta(self, attuale, precedente):
        diff = attuale - precedente
        while diff > math.pi: diff -= 2 * math.pi
        while diff < -math.pi: diff += 2 * math.pi
        return diff

    def vai_avanti_return_dist(self, metri_target, velocita_max=1.5):
        self.ferma()
        orient_iniziale = self.sim.getObjectOrientation(self.robot_handle, -1)
        angolo_iniziale = orient_iniziale[2]
        
        self.last_pos_sx, self.last_pos_dx = self._get_raw_encoder_positions()
        distanza_percorsa = 0
        Kp = 12.0
        
        while distanza_percorsa < metri_target:
            # 1. FRENATA DOLCE: Rallenta quando mancano meno di 15cm
            distanza_residua = metri_target - distanza_percorsa
            velocita_attuale = velocita_max
            if distanza_residua < 0.15:
                velocita_attuale = 0.2 # Velocità di "accosto" molto bassa
            
            angolo_attuale = self.sim.getObjectOrientation(self.robot_handle, -1)[2]
            errore_angolo = self._normalize_delta(angolo_iniziale, angolo_attuale)
            correzione = errore_angolo * Kp
            
            self.set_velocita(velocita_attuale - correzione, velocita_attuale + correzione)
            
            # Aggiornamento odometria
            curr_sx, curr_dx = self._get_raw_encoder_positions()
            delta_sx = abs(self._normalize_delta(curr_sx, self.last_pos_sx))
            delta_dx = abs(self._normalize_delta(curr_dx, self.last_pos_dx))
            distanza_percorsa += ((delta_sx + delta_dx) / 2) * self.raggio_ruota
            self.last_pos_sx, self.last_pos_dx = curr_sx, curr_dx
            
            # 3. MODALITÀ SINCRONA: Diciamo a CoppeliaSim di fare un passo avanti
            self.client.step() 
            
        self.ferma()
        return distanza_percorsa

def main():
    client = RemoteAPIClient()
    # 3. ATTIVAZIONE SINCRONA: Fondamentale per la precisione millimetrica
    client.setStepping(True) 
    
    sim = client.getObject('sim')
    agv = RobotAGV(client)

    sim.startSimulation()

    try:
        risultati = []
        pos_reset = [9.0, 9.0, 0.105]
        orient_reset = [0.0, 0.0, -math.pi/2]

        for i in range(10):
            sim.setObjectPosition(agv.robot_handle, -1, pos_reset)
            sim.setObjectOrientation(agv.robot_handle, -1, orient_reset)
            
            # Aspettiamo che la fisica si calmi (in modalità sincrona servono dei .step())
            agv.ferma()
            for _ in range(20): client.step()
            
            distanza = agv.vai_avanti_return_dist(1.0)
            
            pos = sim.getObjectPosition(agv.robot_handle, -1)
            orient = sim.getObjectOrientation(agv.robot_handle, -1)
            
            res = f"Sim {i+1}: x={pos[0]:.3f}, y={pos[1]:.3f}, gamma={math.degrees(orient[2]):.2f}, dist={distanza:.4f} m\n"
            risultati.append(res)
            print(res.strip())

        with open("risultati_simulazioni.txt", "w") as f:
            f.writelines(risultati)

    finally:
        sim.stopSimulation()

if __name__ == "__main__":
    main()