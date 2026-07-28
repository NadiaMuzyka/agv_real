class PositionController:
    # Coordinate (x, y) in centimetri per l'odometria del Create 3
    POSITION_TABLE = {
        "ER": [0, 0],
        "I7": [0, 160],
        "I2": [100, 180],
        "I1": [200, 180],
        "E2": [100, 20],
        "E1": [200, 20]
    }

    def get_position(self, tag: str):
        return self.POSITION_TABLE.get(tag.upper())