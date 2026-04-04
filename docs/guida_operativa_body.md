# Guida Operativa Body

## Il "Pizzino" da passare a Nadia

Puoi letteralmente copiare e incollare questi 3 consigli d'oro da mandare a Nadia per il suo `main_body.py`. Le salveranno ore di mal di testa con CoppeliaSim:

### 1. Mai usare `pubsub.listen()` bloccante

Poiche' CoppeliaSim ha bisogno di un ciclo continuo per aggiornare la fisica e i motori, il Body non puo' rimanere bloccato ad aspettare un messaggio da Redis.

Deve usare `pubsub.get_message()` (che legge al volo e va avanti se non c'e' nulla) oppure leggere una semplice chiave `GET` ad ogni ciclo di simulazione.

### 2. Idempotenza (Il controllo Anti-Spam)

Il Body deve avere una variabile `azione_in_corso`.

Se il Brain manda `MOVE_TO I3` e il Body sta gia' andando a `I3`, il comando va ignorato silenziosamente.

Se invece il Brain improvvisamente manda `STOP` o un nodo diverso, il Body deve annullare l'azione precedente e iniziare quella nuova.

### 3. Spegnimento Pulito (Graceful Shutdown)

Esattamente come hai fatto tu, anche lei dovra' importare `signal` e catturare il `SIGTERM`.

Questo e' vitale per lei, perche' quando spegnete Docker, il suo script deve inviare il comando di stop a CoppeliaSim (`sim.stopSimulation()`), altrimenti il simulatore potrebbe crashare o rimanere appeso in background.
