#
# Licensed under 3-Clause BSD license available in the License file. Copyright (c) 2021-2023 iRobot Corporation. All rights reserved.
#

# Want to draw a square?

from modules.connection.create3_connector import Create3Connector

connector = Create3Connector()  # Si connette e resta bloccato finché non è pronto.

millivolt, percent = connector.get_battery_level()
print(f'Battery level: {percent}% ({millivolt} mV)')
#print('Vado alla stazione di ricarica')
#connector.dock()

print('Fatto, mi disconnetto.')
connector.disconnect()  # Disconnessione pulita, senza bisogno di Ctrl+C.
