import time
import py_trees
from py_trees.common import Status

# =============================================================================
# 0. NODI DI GESTIONE DATI REDIS
# =============================================================================

class RedisDataNotReady(py_trees.behaviour.Behaviour):
    """
    Controlla se i dati necessari sono pronti su Redis.
    Restituisce SUCCESS se i dati non sono pronti (attivando la sequenza di attesa).
    """
    def __init__(self):
        super(RedisDataNotReady, self).__init__(name="Controllo Dati Redis")
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key(key="logic_controller", access=py_trees.common.Access.READ)
    
    def setup(self):
        print("Setup Controllo Dati Redis")
        return True

    def initialise(self):
        pass

    def update(self):
        esito = self.blackboard.logic_controller.check_redis_data()
        if not esito:
            print("[ControlloDatiRedis] Dati non pronti su Redis. Attivo sequenza di attesa.")
            return Status.SUCCESS
        else:
            return Status.FAILURE   
        
class WaitRedis(py_trees.behaviour.Behaviour):
    """
    Nodo di attesa che rimane in RUNNING finché i dati non sono pronti su Redis.
    """
    def __init__(self):
        super(WaitRedis, self).__init__(name="Wait Redis")
        self.duration = 1.0 # Durata dell'attesa in secondi
        self.start_time = None

    def setup(self):
        print("Setup Wait Redis")
        return True

    def initialise(self):
        self.start_time = time.time()
        print("[WaitRedis] Attendo che i dati siano pronti su Redis...")

    def update(self):
        elapsed_time = time.time() - self.start_time
        if elapsed_time >= self.duration:
            print("[WaitRedis] Dati ora pronti su Redis. Passo alla fase successiva.")
            return Status.SUCCESS
        else:
            return Status.RUNNING
