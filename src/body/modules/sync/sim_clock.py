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
        self._participants = {}   # nome -> (periodo, primo_step_dovuto)
        self._acked = set()

    def register(self, name, period_steps):
        """
        Registra un partecipante gating. Calcola e RITORNA atomicamente il
        primo step per cui sarà richiesto il suo ack (step_corrente + periodo).
        Il chiamante DEVE usare questo valore come primo target di
        wait_until(), invece di rileggere current_step separatamente: una
        lettura separata introdurrebbe di nuovo la finestra di race condition
        che causava il deadlock (il main loop può considerare il partecipante
        "dovuto" già per lo step in corso, mentre il thread si preparava ad
        aspettare quello successivo).
        """
        with self._cond:
            first_due_step = self._step + period_steps
            self._participants[name] = (period_steps, first_due_step)
            self._cond.notify_all()
            return first_due_step

    def unregister(self, name):
        with self._cond:
            self._participants.pop(name, None)
            self._cond.notify_all()

    def _due_now(self):
        due = set()
        for n, (period, first_due) in self._participants.items():
            if self._step >= first_due and (self._step - first_due) % period == 0:
                due.add(n)
        return due

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
        """SOLO il main loop."""
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