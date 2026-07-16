import networkx as nx

class NavigatoreGrafo:
    def __init__(self):
        """Inizializza il navigatore costruendo automaticamente la mappa fissa."""
        self.grafo = nx.Graph()
        self._costruisci_grafo_statico()

    def _costruisci_grafo_statico(self):
        """Metodo interno per definire e popolare il grafo. 
        Il trattino basso iniziale (_) indica che è un metodo ad uso interno della classe."""
        grafo_dict = {
            "I1": [("E1", 200), ("I2", 130), ("I3", 530)],
            "I2": [("E2", 200), ("I1", 130), ("I7", 155)],
            "I3": [("I1", 530), ("I4", 130), ("I6", 1000)],
            "I4": [("I3", 130), ("E3", 200), ("I5", 130)],
            "I5": [("I4", 130), ("E4", 200), ("I6", 130)],
            "I6": [("I7", 155), ("EC", 200), ("I3", 1000)],
            "I7": [("I2", 155), ("ER", 200), ("I6", 155)],
            "E1": [("I1", 200)],
            "E2": [("I2", 200)],
            "E3": [("I4", 200)],
            "E4": [("I5", 200)],
            "ER": [("I7", 200)],
            "EC": [("I6", 200)]
        }

        # Popoliamo il grafo
        for nodo_origine, vicini in grafo_dict.items():
            for nodo_destinazione, peso in vicini:
                self.grafo.add_edge(nodo_origine, nodo_destinazione, weight=peso)

    def trova_percorso_minimo(self, nodo_partenza, nodo_arrivo):
        """Calcola il percorso più breve e la distanza totale."""
        try:
            percorso = nx.shortest_path(self.grafo, source=nodo_partenza, target=nodo_arrivo, weight="weight")
            distanza = nx.shortest_path_length(self.grafo, source=nodo_partenza, target=nodo_arrivo, weight="weight")
            return percorso, distanza
            
        except nx.NetworkXNoPath:
            print(f"Nessun percorso trovato tra {nodo_partenza} e {nodo_arrivo}.")
            return None, float('inf')
        except nx.NodeNotFound as e:
            print(f"Errore: Il nodo specificato non esiste nel grafo ({e}).")
            return None, float('inf')