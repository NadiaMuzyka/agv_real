import cv2
import json
import redis
from ultralytics import YOLO

class PersonDetectorNode:
    """
    Microservizio di Percezione: 
    Analizza il flusso video e aggiorna in tempo reale Redis se rileva una persona.
    """

    # --- COSTANTI TECNICHE ---
    FOCALE_WEBCAM = 1100.0  # Valore stimato per 720p (FOV 60°)
    LARGHEZZA_SPALLE = 0.5   # Metri (W)
    SOGLIA_STOP = 3.0        # Metri (Soglia di sicurezza)

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

    def aggiorna_redis(self, persona_rilevata: bool, distanza: float = 0.0):
        """ 
        Legge il JSON, aggiorna rilevamento e distanza, e riscrive.
        """
        # Se lo stato non è cambiato e la distanza è simile, potremmo evitare l'update.
        # Ma per ora aggiorniamo sempre se c'è una persona per avere la distanza fresca.
        if persona_rilevata == False and self.ultimo_stato_inviato == False:
            return

        chiave_memoria = "brain_memory"
        memoria_str = self.r.get(chiave_memoria)
        memoria = json.loads(memoria_str) if memoria_str else {}

        # Aggiornamento dati
        memoria["person_detected"] = persona_rilevata
        memoria["person_distance"] = round(distanza, 2) if persona_rilevata else 0.0
        
        # Logica di STOP forzato se troppo vicino
        if persona_rilevata and distanza < self.SOGLIA_STOP:
            print(f"[VisionNode] 🛑 EMERGENZA: Persona a {distanza:.2f}m! Sotto soglia {self.SOGLIA_STOP}m.")
        
        self.r.set(chiave_memoria, json.dumps(memoria))
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
                distanza_rilevata = 0.0

                for r in risultati:
                    for box in r.boxes:
                        id_classe = int(box.cls[0])
                        confidenza = float(box.conf[0])
                        
                        if id_classe == 0 and confidenza > 0.60:
                            # CALCOLO DISTANZA
                            x1, y1, x2, y2 = box.xyxy[0]
                            w_pixel = float(x2 - x1)
                            
                            # Formula: D = (W * f) / w
                            distanza_rilevata = (self.LARGHEZZA_SPALLE * self.FOCALE_WEBCAM) / w_pixel
                            persona_trovata = True
                            break # Gestiamo la persona più vicina

                # Invio dati a Redis
                self.aggiorna_redis(persona_trovata, distanza_rilevata)

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