class PositionController:
    # Coordinate (x, y) in centimetri per l'odometria del Create 3
    POSITION_TABLE = {
        "ER": [0, 0],
        "I7": [0, 200],
        "I2": [100, 200],
        "I1": [200, 200],
        "E2": [100, 0],
        "E1": [200, 0]
    }

    def get_position(self, tag: str):
        return self.POSITION_TABLE.get(tag.upper())