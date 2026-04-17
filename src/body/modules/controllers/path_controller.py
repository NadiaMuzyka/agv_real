class PathController:
    """Prende in input il nodo attuale e il nodo successivo e decide la direzione (FORWARD, LEFT, RIGHT) da comunicare al TaskController."""


    def get_next_step(self, current_node: str, target_node: str) -> str:
        """
        Logica semplificata per decidere la direzione da prendere.
        In un caso reale, questa funzione potrebbe essere molto più complessa e basata su una mappa del percorso.
        """
        # TODO: Implementare la logica di calcolo del percorso e della direzione da prendere.
        # Per ora, ritorniamo una direzione fittizia basata su una semplice ["STRAIGHT", "LEFT", "RIGHT"] 
        
        return "STRAIGHT"