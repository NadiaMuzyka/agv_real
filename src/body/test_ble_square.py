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
    robot._loop.stop()  # Ferma il loop così che play() ritorni da solo, senza bisogno di Ctrl+C.

robot.play()
