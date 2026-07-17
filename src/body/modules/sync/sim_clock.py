import threading

class SimClock:
    """
    Un tick = un sim.step() completato. Sostituisce time.sleep() come
    primitiva di sincronizzazione per tutti i thread che leggono sensori
    o scrivono comandi agli attuatori.
    """
    def __init__(self):
        self._step = 0
        self._cond = threading.Condition()
        self._participants = {}   # nome -> periodo in step
        self._acked = set()

    def register(self, name, period_steps):
        with self._cond:
            self._participants[name] = period_steps
            self._cond.notify_all()

    def unregister(self, name):
        with self._cond:
            self._participants.pop(name, None)
            self._cond.notify_all()   # può sbloccare una barrier in attesa

    def _due_now(self):
        return {n for n, p in self._participants.items() if self._step % p == 0}

    def advance(self):
        """SOLO da chi chiama sim.step() (main loop e stepper di cleanup)."""
        with self._cond:
            self._step += 1
            self._acked = set()
            self._cond.notify_all()

    def wait_until(self, target_step):
        with self._cond:
            while self._step < target_step:
                self._cond.wait()
            return self._step

    def wait_for(self, names, step):
        """Dipendenza esplicita read-after-write dentro lo stesso tick."""
        with self._cond:
            while self._step == step and not set(names).issubset(self._acked):
                self._cond.wait()

    def ack(self, name):
        with self._cond:
            self._acked.add(name)
            self._cond.notify_all()

    def wait_barrier(self, timeout=None):
        """SOLO il main loop. due_now() ricalcolato ad ogni check: se un
        partecipante fa unregister() mentre siamo in attesa, si sblocca subito."""
        with self._cond:
            ok = self._cond.wait_for(
                lambda: self._due_now().issubset(self._acked), timeout=timeout
            )
            if not ok:
                missing = self._due_now() - self._acked
                raise RuntimeError(f"Barrier timeout: mancano ack da {missing} allo step {self._step}")

    @property
    def current_step(self):
        with self._cond:
            return self._step