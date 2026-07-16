class PathController:
    """Controller basato su tabelle statiche di svolta.

    Tabella principale (get_next_step2):
    TURN_TABLE[current_position][next_node][previous_node] -> direction

    Dove:
    - current_position: nodo in cui si trova il robot
    - next_node: nodo verso cui il robot deve uscire
    - previous_node: nodo da cui il robot e' entrato in current_position
    - direction: LEFT | STRAIGHT | RIGHT

    La tabella include solo combinazioni coerenti con il grafo attuale.
    Se una combinazione non e' presente, il fallback e' STRAIGHT.
    """

    LEGACY_TURN_TABLE = {
        "I1": {"E1": "LEFT", "I2": "STRAIGHT", "I3": "RIGHT"},
        "I2": {"E2": "LEFT", "I1": "STRAIGHT", "I7": "RIGHT"},
        "I3": {"I1": "LEFT", "I4": "STRAIGHT", "I6": "RIGHT"},
        "I4": {"I3": "LEFT", "E3": "STRAIGHT", "I5": "RIGHT"},
        "I5": {"I4": "LEFT", "E4": "STRAIGHT", "I6": "RIGHT"},
        "I6": {"I7": "LEFT", "EC": "STRAIGHT", "I3": "RIGHT"},
        "I7": {"I2": "LEFT", "ER": "STRAIGHT", "I6": "RIGHT"},
        "E1": {"I1": "STRAIGHT"},
        "E2": {"I2": "STRAIGHT"},
        "E3": {"I4": "STRAIGHT"},
        "E4": {"I5": "STRAIGHT"},
        "EC": {"I6": "STRAIGHT"},
        "ER": {"I7": "STRAIGHT"},
    }

    # TURN_TABLE[current_position][next_node][previous_node] -> direction
    TURN_TABLE = {
        "I1": {
            "E1": {"I2": "RIGHT", "I3": "LEFT"},
            "I2": {"E1": "LEFT", "I3": "STRAIGHT"},
            "I3": {"E1": "RIGHT", "I2": "STRAIGHT"},
        },
        "I2": {
            "E2": {"I1": "LEFT", "I7": "RIGHT"},
            "I1": {"E2": "RIGHT", "I7": "STRAIGHT"},
            "I7": {"E2": "LEFT", "I1": "STRAIGHT"},
        },
        "I3": {
            "I1": {"I4": "LEFT", "I6": "RIGHT"},
            "I4": {"I1": "RIGHT", "I6": "LEFT"},
            "I6": {"I1": "STRAIGHT", "I4": "RIGHT"},
        },
        "I4": {
            "I3": {"E3": "RIGHT", "I5": "RIGHT"},
            "E3": {"I3": "LEFT", "I5": "RIGHT"},
            "I5": {"I3": "STRAIGHT", "E3": "RIGHT"},
        },
        "I5": {
            "I4": {"E4": "RIGHT", "I6": "STRAIGHT"},
            "E4": {"I4": "LEFT", "I6": "RIGHT"},
            "I6": {"I4": "STRAIGHT", "E4": "LEFT"},
        },
        "I6": {
            "I7": {"EC": "LEFT", "I3": "STRAIGHT", "I5": "RIGHT"},
            "EC": {"I7": "RIGHT", "I3": "LEFT", "I5": "STRAIGHT"},
            "I3": {"I7": "STRAIGHT", "EC": "RIGHT", "I5": "LEFT"},
            "I5": {"I7": "LEFT", "EC": "STRAIGHT", "I3": "RIGHT"},
        },
        "I7": {
            "I2": {"ER": "RIGHT", "I6": "STRAIGHT"},
            "ER": {"I2": "LEFT", "I6": "RIGHT"},
            "I6": {"I2": "STRAIGHT", "ER": "LEFT"},
        },
        "E1": {
            "I1": {"I1": "STRAIGHT"},
        },
        "E2": {
            "I2": {"I2": "STRAIGHT"},
        },
        "E3": {
            "I4": {"I4": "STRAIGHT"},
        },
        "E4": {
            "I5": {"I5": "STRAIGHT"},
        },
        "EC": {
            "I6": {"I6": "STRAIGHT"},
        },
        "ER": {
            "I7": {"I7": "STRAIGHT"},
        },
    }

    def get_next_step(self, current_position: str, target_node: str) -> str:
        """Compatibilita' con codice legacy senza previous_node."""
        return self.LEGACY_TURN_TABLE.get(current_position, {}).get(target_node, "LEFT")

    def get_next_step2(
        self,
        current_position: str,
        target_node: str,
        previous_node: str | None = None,
    ) -> str:
        """Metodo stupido: sola lettura da TURN_TABLE[current][next][previous]."""
        return self.TURN_TABLE.get(current_position, {}).get(target_node, {}).get(previous_node, "STRAIGHT")
