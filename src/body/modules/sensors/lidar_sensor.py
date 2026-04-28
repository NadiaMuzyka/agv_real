from modules.sensors.generic_sensor import GenericSensor
from modules.connection.redis_interface import RedisInterface
from coppeliasim_zmqremoteapi_client import RemoteAPIClient
import threading
import time
import json
import math

class LidarSensor(GenericSensor):
    def __init__(self, name="Lidar"):
        super().__init__(name)
        
        # Connessione a Redis
        self.redis_client = RedisInterface()
        if not self.redis_client.db:
            print(f"[{self.name}] ❌ Redis non raggiungibile.")

        self.last_data = {"ostacolo": False, "distanza": 999.0}
        self.frequenza_lettura = 0.05  
        self._running = False
        self._thread = None
        self.soglia_sicurezza = 2.0  

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._loop_lettura, daemon=True)
            self._thread.start()
            print(f"[{self.name}] 🟢 Thread avviato in modalità REALE.")

    def _aggiorna_redis(self, ostacolo_rilevato):
        try:
            memoria_attuale_str = self.redis_client.db.get("brain_memory")
            dati = json.loads(memoria_attuale_str) if memoria_attuale_str else {}
            dati["ostacolo_lidar"] = ostacolo_rilevato
            self.redis_client.db.set("brain_memory", json.dumps(dati))
        except Exception:
            pass

    def _estrai_distanza_minima(self, sim_instance, nome_segnale):
        try:
            packed_data = sim_instance.getStringSignal(nome_segnale)
            if not packed_data:
                return 999.0 
            
            punti = sim_instance.unpackFloatTable(packed_data)
            min_dist = 999.0
            
            for i in range(0, len(punti), 3):
                x = punti[i]
                y = punti[i+1]
                z = punti[i+2]

                # --- SOFTWARE CROPPING ---
                # Lasciamolo spento per ora, così vediamo se legge
                # if y < 0.0:  
                #    continue
                # -------------------------

                dist = math.sqrt(x*x + y*y + z*z)
                if 0.1 < dist < min_dist:
                    min_dist = dist
                    
            return min_dist
        except Exception as e:
            print(f"[{self.name}] ❌ ERRORE LETTURA {nome_segnale}: {e}")
            return 999.0

    def _loop_lettura(self):
        # --- FIX: LA CONNESSIONE ZMQ DEVE STARE DENTRO IL THREAD! ---
        print(f"[{self.name}] 🔌 Connessione a CoppeliaSim ZMQ nel thread in corso...")
        try:
            client = RemoteAPIClient(host='host.docker.internal')
            sim_instance = client.getObject('sim')
            print(f"[{self.name}] ✅ ZMQ API collegata con successo e pronta a leggere!")
        except Exception as e:
            print(f"[{self.name}] ❌ Errore connessione ZMQ: {e}")
            return
        # ------------------------------------------------------------

        while self._running:
            # Passiamo l'istanza 'sim_instance' direttamente al metodo
            distanza_basso = self._estrai_distanza_minima(sim_instance, "lidarLow_data")
            distanza_alto = self._estrai_distanza_minima(sim_instance, "lidarHigh_data")
            
            distanza_minima = min(distanza_basso, distanza_alto)
            
            print(f"[{self.name}] 📏 Distanza: {distanza_minima:.2f}m")
            
            self.last_data["distanza"] = distanza_minima
            self.last_data["ostacolo"] = distanza_minima < self.soglia_sicurezza
            
            self._aggiorna_redis(self.last_data["ostacolo"])
            time.sleep(self.frequenza_lettura)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
            print(f"[{self.name}] 🔴 Thread fermato.")