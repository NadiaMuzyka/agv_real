import os
import asyncio
import threading

from irobot_edu_sdk.backend.bluetooth import Bluetooth
from irobot_edu_sdk.robots import event, Create3


class Create3Connector:
    """
    Gestisce la connessione BLE persistente al robot reale iRobot Create3
    (Singleton: a differenza di CoppeliaConnector, qui esiste un solo robot
    fisico, quindi non ha senso avere istanze multiple).

    L'SDK (irobot_edu_sdk) è asyncio-nativo e gira solo tramite robot.play(),
    che è bloccante: qui lo eseguiamo in un thread dedicato con un loop che
    resta vivo finché non chiamiamo disconnect(), così il resto del codice
    (sincrono/thread-based, come gli Actuator) può chiedere comandi al robot
    in qualsiasi momento tramite run_coro()/i metodi di comodo sotto.
    """
    _instance = None
    _lock = threading.Lock()

    CONNECT_TIMEOUT = 30  # secondi di attesa per la connessione BLE iniziale
    CALL_TIMEOUT = 10     # secondi di attesa per ogni comando inviato al robot

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Create3Connector, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # Impedisce la riconnessione se l'istanza esiste già
        if self._initialized:
            return

        self.name = os.getenv('CREATE3_NAME') or None
        self.address = os.getenv('CREATE3_ADDRESS') or None

        self._robot = Create3(Bluetooth(name=self.name, address=self.address))
        self._loop = self._robot._loop

        self._connected_event = threading.Event()
        self._stopped_event = threading.Event()

        @event(self._robot.when_play)
        async def _on_play(robot):
            print(f"[Create3Connector] Connesso al robot (name={self.name}, address={self.address}).")
            self._connected_event.set()

        self._thread = threading.Thread(target=self._run, name="Create3Connector", daemon=True)
        self._thread.start()

        if not self._connected_event.wait(timeout=self.CONNECT_TIMEOUT):
            raise ConnectionError("Create3Connector: connessione BLE al robot non riuscita in tempo.")

        self._initialized = True

    def _run(self):
        """Esegue il loop asyncio del robot nel thread dedicato, finché disconnect() non lo ferma."""
        try:
            self._robot.play()
        except RuntimeError:
            # disconnect() ferma il loop (robot._loop.stop()) prima che _main() finisca:
            # asyncio solleva sempre questo errore in quel caso, ma è innocuo.
            pass
        finally:
            self._stopped_event.set()
            print("[Create3Connector] Loop del robot terminato.")

    def run_coro(self, coro):
        """Esegue una coroutine sul loop del robot da un altro thread e ne attende il risultato."""
        if self._stopped_event.is_set():
            raise ConnectionError("Create3Connector: la connessione al robot non è più attiva.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=self.CALL_TIMEOUT)

    # --- Comandi base ----------------------------------------------------

    def get_battery_level(self):
        """Ritorna (millivolt, percentuale)."""
        return self.run_coro(self._robot.get_battery_level())

    def move(self, distance):
        """Muove il robot in linea retta: distanza in mm (negativa per andare indietro)."""
        return self.run_coro(self._robot.move(distance))

    def turn_left(self, angle):
        """Angolo in gradi."""
        return self.run_coro(self._robot.turn_left(angle))

    def turn_right(self, angle):
        """Angolo in gradi."""
        return self.run_coro(self._robot.turn_right(angle))

    def set_wheel_speeds(self, left, right):
        """Velocità ruote in mm/s."""
        return self.run_coro(self._robot.set_wheel_speeds(left, right))

    def stop(self):
        """Ferma il robot (reset velocità), senza chiudere la connessione BLE."""
        return self.run_coro(self._robot.stop())

    def dock(self):
        return self.run_coro(self._robot.dock())

    def undock(self):
        return self.run_coro(self._robot.undock())

    # --- Ciclo di vita della connessione ----------------------------------

    def disconnect(self):
        """Disconnette il robot e ferma il loop in modo pulito, senza bisogno di Ctrl+C."""
        if self._stopped_event.is_set():
            return

        async def _clean_disconnect(robot):
            try:
                await robot.stop()
                await robot.disconnect()
                await robot._backend.disconnect()
            except Exception as e:
                # bleak/dbus-fast a volte sollevano EOFError durante la disconnessione
                # BLE da BlueZ: è un bug noto lato bleak (github.com/hbldh/bleak/issues/1698),
                # non nostro. A questo punto il lavoro utile è già fatto, quindi ignoriamo.
                print(f"[Create3Connector] Disconnessione BLE non pulita (ignorato): {e!r}")
            finally:
                robot._run = False
                robot._loop.stop()

        self.run_coro(_clean_disconnect(self._robot))
        self._thread.join(timeout=self.CONNECT_TIMEOUT)
