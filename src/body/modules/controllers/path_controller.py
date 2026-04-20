class PathController:
    """Prende in input il nodo attuale e il nodo successivo e decide la direzione da comunicare al TaskController."""

    TURN_TABLE = {
        "I1": {"E1": "LEFT", "I2": "STRAIGHT", "I3": "RIGHT"},
        "I2": {"E2": "LEFT", "I1": "STRAIGHT", "I6": "RIGHT"},
        "I3": {"I1": "LEFT", "I4": "STRAIGHT", "I7": "RIGHT"},
        "I4": {"I3": "LEFT", "E3": "STRAIGHT", "I5": "RIGHT"},
        "I5": {"I4": "LEFT", "E4": "STRAIGHT", "I6": "RIGHT"},
        "I6": {"I2": "LEFT", "ER": "STRAIGHT", "I7": "RIGHT"},
        "I7": {"I3": "LEFT", "EC": "STRAIGHT", "I6": "RIGHT"},
        "E1": {"I1": "STRAIGHT"},
        "E2": {"I2": "STRAIGHT"},
        "E3": {"I4": "STRAIGHT"},
        "E4": {"I5": "STRAIGHT"},
        "ER": {"I6": "STRAIGHT"},
        "EC": {"I7": "STRAIGHT"},
    }

    def get_next_step(self, current_node: str, target_node: str) -> str:
        """
        Logica semplificata per decidere la direzione da prendere.
        In un caso reale, questa funzione potrebbe essere molto più complessa e basata su una mappa del percorso.
        """
        # TODO: Implementare la logica di calcolo del percorso e della direzione da prendere.
        # Per ora, ritorniamo una direzione fittizia basata su una semplice ["STRAIGHT", "LEFT", "RIGHT"]

        return "STRAIGHT"

    def get_next_step2(
        self,
        current_node: str,
        target_node: str,
        previous_node: str | None = None,
    ) -> str:
        """
        Versione basata su tabella di verità sul grafo noto.

        Il parametro previous_node è opzionale e viene introdotto per compatibilità
        con l'evoluzione futura della logica di navigazione.
        """
        if current_node == target_node:
            return "STOP"

        node_turns = self.TURN_TABLE.get(current_node, {})
        return node_turns.get(target_node, "STRAIGHT")
