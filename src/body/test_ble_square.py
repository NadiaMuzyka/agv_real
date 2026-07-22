#
# Licensed under 3-Clause BSD license available in the License file. Copyright (c) 2021-2023 iRobot Corporation. All rights reserved.
#

# Want to draw a square?

from irobot_edu_sdk.backend.bluetooth import Bluetooth
from irobot_edu_sdk.robots import event, Create3

robot = Create3(Bluetooth())

@event(robot.when_play)
async def go_to_dock(robot):
    millivolt, percent = await robot.get_battery_level()
    print(f'Battery level: {percent}% ({millivolt} mV)')
    #print('Vado alla stazione di ricarica')
    #result = await robot.dock()
    #print(f'Risultato docking: {result}')
    print('Fatto, mi disconnetto.')
    try:
        await robot.stop()
        await robot.disconnect()
        await robot._backend.disconnect()
    except Exception as e:
        # bleak/dbus-fast a volte sollevano EOFError (o simili) durante la
        # disconnessione BLE da BlueZ: è un bug noto lato bleak, non nostro
        # (es. https://github.com/hbldh/bleak/issues/1698). A questo punto
        # il lavoro utile è già fatto, quindi ignoriamo e usciamo comunque.
        print(f'Disconnessione BLE non pulita (ignorato): {e!r}')
    finally:
        # go_to_dock gira come task a sé (creato da _main()): un'eccezione
        # qui non risalirebbe mai al try/except di robot.play() qui sotto,
        # quindi il try/except sopra e questo finally devono stare per forza
        # dentro la coroutine stessa.
        robot._run = False  # Fa sì che _finished() salti la sua disconnessione.
        robot._loop.stop()  # Ferma il loop così che play() ritorni da solo, senza Ctrl+C.

try:
    robot.play()
except RuntimeError:
    # robot._loop.stop() ferma il loop prima che _main() finisca:
    # asyncio solleva sempre questo errore in quel caso, ma è innocuo.
    pass
