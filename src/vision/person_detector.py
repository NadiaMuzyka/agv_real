import cv2
import json
import redis
from ultralytics import YOLO

class PersonDetectorNode:
    """
    Microservizio di Percezione: 
    Analizza il flusso video e aggiorna in tempo reale Redis se rileva una persona.
    """
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0):
        # 1. Inizializzazione della connessione a Redis
        try:
            self.r = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
            self.r.ping()
            print("[VisionNode] ✅ Connesso a Redis con successo.")
        except redis.ConnectionError:
            print("[VisionNode] ❌ ERRORE: Impossibile connettersi a Redis.")
            exit(1)

        # 2. Caricamento del modello IA
        print("[VisionNode] Caricamento modello YOLOv8n in corso...")
        self.model = YOLO("yolov8n.pt")
        
        # 3. Inizializzazione della videocamera
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("[VisionNode] ❌ ERRORE CRITICO: Webcam non trovata o occupata.")
            exit(1)

        # Memorizziamo l'ultimo stato per evitare di spammare Redis a ogni millisecondo
        self.ultimo_stato_inviato = None

    def aggiorna_redis(self, persona_rilevata: bool):
        """ 
        Legge il JSON attuale da Redis, modifica solo il campo person_detected e lo riscrive.
        """
        # Se lo stato non è cambiato dal frame precedente, non disturbiamo Redis
        if persona_rilevata == self.ultimo_stato_inviato:
            return

        chiave_memoria = "brain_memory"
        
        # Lettura sicura dello stato attuale
        memoria_str = self.r.get(chiave_memoria)
        if memoria_str:
            try:
                memoria = json.loads(memoria_str)
            except json.JSONDecodeError:
                memoria = {}
        else:
            memoria = {}

        # Aggiornamento del sensore
        memoria["person_detected"] = persona_rilevata
        
        # Scrittura su Redis
        self.r.set(chiave_memoria, json.dumps(memoria))
        
        # Log visivo sul terminale
        stato_txt = "⚠️ RILEVATA!" if persona_rilevata else "✅ Nessuno."
        print(f"[VisionNode] 🔄 Stato aggiornato su Redis: Persona {stato_txt}")
        
        self.ultimo_stato_inviato = persona_rilevata

    def run(self):
        """ Ciclo infinito di percezione """
        print("[VisionNode] 👁️ Avvio ciclo di percezione visiva. Premi CTRL+C nel terminale per uscire.")
        
        try:
            while True:
                successo, frame = self.cap.read()
                if not successo:
                    print("[VisionNode] Errore di lettura dalla webcam.")
                    break

                # Inferenza YOLO ottimizzata
                risultati = self.model(frame, stream=True, verbose=False)
                persona_trovata = False

                for r in risultati:
                    for box in r.boxes:
                        id_classe = int(box.cls[0])
                        # Estraiamo la confidenza (YOLO la restituisce come tensore, la convertiamo in float)
                        confidenza = float(box.conf[0])
                        
                        # Accettiamo la rilevazione solo se è una persona (0) E la confidenza è > 60%
                        if id_classe == 0 and confidenza > 0.60:
                            persona_trovata = True
                            break

                # Sincronizza con il resto del robot
                #print(f"[VisionNode] {'⚠️ Persona Rilevata!' if persona_trovata else '✅ Nessuno in vista.'}")
                self.aggiorna_redis(persona_trovata)

                # NOTA: Per le massime performance in produzione, rimuovi queste righe di imshow.
                # L'interfaccia grafica consuma CPU e nei container Docker senza monitor farà crashare lo script.
                # cv2.imshow("Debug Visivo AGV", frame)
                # if cv2.waitKey(1) & 0xFF == ord('q'):
                #     break

        except KeyboardInterrupt:
            print("\n[VisionNode] Spegnimento del nodo richiesto dall'utente.")
        finally:
            self.cap.release()
            cv2.destroyAllWindows()
            print("[VisionNode] Risorse liberate. Arrivederci.")

if __name__ == "__main__":
    import os
    
    # Legge l'indirizzo di Redis dal docker-compose (variabile d'ambiente). 
    # Se non lo trova (es. test senza docker), usa "localhost" come fallback.
    indirizzo_redis = os.getenv("REDIS_HOST", "localhost")
    
    print(f"[Boot] Inizializzazione nodo visivo. Indirizzo Redis: {indirizzo_redis}")
    
    # Passiamo l'indirizzo corretto al costruttore
    nodo_visivo = PersonDetectorNode(redis_host=indirizzo_redis)
    nodo_visivo.run()