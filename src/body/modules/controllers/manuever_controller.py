import math
from modules.controllers.path_controller import PathController
from modules.controllers.position_controller import PositionController

class ManueverControllerCreate3:
    def __init__(self, robot, redis_client):
        self.robot = robot  # Istanza del robot Create3
        self.redis_client = redis_client
        self.path_controller = PathController()
        self.position_controller = PositionController()

        self.TURN_ANGLES = {"LEFT": 90.0, "RIGHT": -90.0, "STRAIGHT": 0.0}

    async def execute_turn(self, delta_degrees):
        """Usa il giroscopio e gli encoder interni per ruotare di un angolo esatto."""
        if delta_degrees > 0:
            await self.robot.turn_left(abs(delta_degrees))
        elif delta_degrees < 0:
            await self.robot.turn_right(abs(delta_degrees))

    async def move_to(self, current_position, next_node, previous_node):
        """Esegue il movimento tra due nodi leggendo la distanza dalla tabella odometrica."""
        print(f"🧭 [move_to] Tratta: {current_position} -> {next_node} (da {previous_node})")

        # 1. Rotazione topologica all'incrocio (Fase 1)
        turn = self.path_controller.get_next_step2(current_position, next_node, previous_node)[cite: 1, 2]
        angle = self.TURN_ANGLES.get(turn, 0.0)[cite: 1]
        
        if angle != 0.0:
            print(f"🔄 Rotazione odometrica: {turn} ({angle}°)")
            await self.execute_turn(angle)[cite: 1]

        # 2. Calcolo odometrico della distanza lineare
        pos_curr = self.position_controller.get_position(current_position)
        pos_next = self.position_controller.get_position(next_node)

        if pos_curr and pos_next:
            dx = pos_next[0] - pos_curr[0]
            dy = pos_next[1] - pos_curr[1]
            distanza_cm = math.hypot(dx, dy)  # Teorema di Pitagora
            
            print(f"⬆️ Avanzamento odometrico: {distanza_cm:.1f} cm")
            # Il robot avanza controllando gli encoder ruota fino al cm esatto
            await self.robot.move(distanza_cm)
        else:
            print(f"⚠️ Coordinate non trovate nella tabella per: {current_position} -> {next_node}")

    async def stop(self):
        """Arresto immediato tramite comando nativo."""
        await self.robot.stop()