class PositionController:

    POSITION_TABLE = {
        "E1": [3.75, 3.6],
        "E2": [5.85, 3.6],
        "E3": [3.75, 8.325],
        "E4": [5.85, 8.325],
        "EC": [9.175, 6.675],
        "ER": [9.425, 4.3],
        "I1": [3.75, 2],
        "I2": [5.85, 2],
        "I3": [1.65, 6.675],
        "I4": [3.75, 6.675],
        "I5": [5.85, 6.675],
        "I6": [7.9, 6.675],
        "I7": [7.9, 4.3]
    }

    def get_position(self, tag: str):
        return self.POSITION_TABLE.get(tag)