# 📖 Guida Operativa Body: Integrazione CoppeliaSim ↔ Redis

Questo documento definisce il "Contratto di Interfaccia" e le best practice per far comunicare il sistema logico (Brain / Behavior Tree) con il simulatore fisico (Body / CoppeliaSim) tramite Redis, evitando problemi di desincronizzazione e lag.

## 📡 1. Architettura di Comunicazione

Il sistema usa un approccio ibrido su Redis:
* **Comandi (Da Brain a Body):** Inviati tramite **Pub/Sub** sul canale `agv_command_channel`. I comandi sono eventi istantanei ("Fai questo ora").
* **Sensori (Da Body a Brain):** Salvati tramite normale **Key-Value** (GET/SET) sulla chiave `agv_sensors`. I sensori rappresentano lo stato persistente del robot.

---

## 📦 2. Formato dei Messaggi (JSON)

### Cosa invia il Brain (Comandi Pub/Sub)
Il Body deve mettersi in ascolto su `agv_command_channel` e aspettarsi dizionari JSON come questi:
* Navigazione: `{"type": "MOVE_TO", "next_node": "I6"}`
* Prelievo: `{"type": "PICKUP"}`
* Consegna: `{"type": "DROP"}`
* Arresto: `{"type": "STOP"}`

### Cosa deve scrivere il Body (Stato Sensori)
Ad ogni ciclo utile, il Body deve aggiornare la chiave `agv_sensors` con un JSON che descrive la realtà fisica del simulatore:
```json
{
  "current_position": "I6", 
  "am_i_in_a_node": true,
  "carico_sollevato": false,
  "battery_level": 85.5
}
⚠️ Nota vitale: Il Brain rimane bloccato in stato RUNNING finché non legge su Redis che l'azione è completata (es. current_position coincide con la destinazione, o carico_sollevato diventa true).

🛠️ 3. I 4 "Pilastri" per il ciclo di CoppeliaSim
Il Brain ragiona ad altissima frequenza (es. 10+ Tick al secondo), mentre la fisica di CoppeliaSim ha tempi reali. Per evitare che il simulatore esploda o accumuli minuti di ritardo, il main_body.py deve rispettare queste 4 regole:

1. Ascolto Non Bloccante
Poiché CoppeliaSim richiede chiamate continue a sim.step() per far avanzare la fisica, il listener di Redis non deve mai bloccare il thread.

❌ Assolutamente NO: for msg in pubsub.listen(): (Blocca l'esecuzione finché non arriva un messaggio).

✅ SÌ: msg = pubsub.get_message(ignore_subscribe_messages=True) (Legge al volo; se non c'è nulla restituisce None e il ciclo procede).

2. Svuotamento della Coda (Queue Draining)
Se l'AGV impiega 3 secondi per percorrere un tratto, nel frattempo il Brain potrebbe aver pubblicato 30 messaggi identici (MOVE_TO I6) che si impilano nella memoria di Redis.
Se il Body ne legge uno alla volta, accumulerà ritardo (eseguendo oggi i comandi di 1 minuto fa).
Soluzione: Leggere velocemente l'ultimo comando valido e poi, mentre l'azione è in corso, svuotare e buttare via tutti i messaggi residui accumulati nella coda Pub/Sub.

3. Idempotenza (Scudo Anti-Spam)
Il Body deve avere una memoria locale (es. ultimo_nodo_destinazione).
Se riceve l'ordine MOVE_TO I3 ma i motori stanno già spingendo il robot verso I3, il comando va ignorato silenziosamente per non riavviare continuamente i controller PID o i pathfollower.

4. Spegnimento Pulito (Graceful Shutdown)
Quando Docker si spegne, invia un SIGTERM. Se il codice Python muore improvvisamente, CoppeliaSim potrebbe rimanere appeso.
Usare la libreria signal per intercettare l'arresto e chiamare sim.stopSimulation().

💻 4. Esempio di Struttura Architetturale
Questa è la struttura base testata e funzionante per il ciclo while principale del Body:

Python
import time
import json
import signal
import sys

is_running = True

def spegni_tutto(sig, frame):
	global is_running
	print("🛑 Spegnimento richiesto, fermo CoppeliaSim...")
	is_running = False
	# sim.stopSimulation()
	sys.exit(0)

signal.signal(signal.SIGTERM, spegni_tutto)
signal.signal(signal.SIGINT, spegni_tutto)

ultimo_nodo_destinazione = None

while is_running:
	# 1. LETTURA NON BLOCCANTE (Un solo messaggio alla volta)
	msg = pubsub.get_message(ignore_subscribe_messages=True)
    
	if msg:
		comando = json.loads(msg['data'])
		tipo = comando.get("type")

		if tipo == "MOVE_TO":
			destinazione = comando.get("next_node")
            
			# 2. ANTI-SPAM (Ignoro se sto già andando lì)
			if destinazione and destinazione != ultimo_nodo_destinazione:
				ultimo_nodo_destinazione = destinazione
				print(f"Avvio motori verso: {destinazione}")
                
				# ... codice CoppeliaSim per muovere il robot ...
                
				# 3. QUEUE DRAINING: Svuoto la coda dai messaggi urlati dal Brain mentre viaggiavo
				while pubsub.get_message(ignore_subscribe_messages=True):
					pass

		elif tipo == "PICKUP":
			print("Attivazione attuatori forche in su...")
			# ... codice CoppeliaSim per prelevare ...
            
			# Resetto l'ultima destinazione perché l'azione di movimento è finita
			ultimo_nodo_destinazione = None 
			while pubsub.get_message(ignore_subscribe_messages=True): pass

	# 4. AVANZAMENTO SIMULATORE E SENSORI
	# sim.step()
	# leggi_sensori_e_scrivi_su_redis(r, SENSOR_KEY)
    
	time.sleep(0.05) # Pausa per non saturare la CPU
