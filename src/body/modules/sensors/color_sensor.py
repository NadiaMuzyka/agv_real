from modules.sensors.generic_sensor import GenericSensor

class ColorSensor(GenericSensor):
    def __init__(self, sim, name):
        # Richiama il costruttore della classe base (GenericSensor)
        super().__init__(name)
        self.sim = sim
        # In CoppeliaSim, 'name' sarà il percorso o il nome dell'oggetto
        self.handle = self.sim.getObject(name)

    def read(self):
        """
        Implementazione del metodo obbligatorio della classe base.
        Restituisce i valori normalizzati per default.
        """
        return self.read_rgb255()

    def read_normalized(self):
        """Legge dal sensore e restituisce i valori RGB normalizzati (0.0 - 1.0)."""
        # Nota: handleVisionSensor è corretto per le vecchie API, 
        # nelle nuove ZMQ si usa spesso sim.handleVisionSensor o sim.readVisionSensor
        res, p1, p2 = self.sim.handleVisionSensor(self.handle)
        
        if res >= 0 and p1 and len(p1) > 12:
            # I dati del sensore di visione di Coppelia restituiscono 
            # i valori RGB medi nelle posizioni 10, 11, 12 del pacchetto p1
            r = round(p1[10], 3)
            g = round(p1[11], 3)
            b = round(p1[12], 3)
            return r, g, b
            
        return None, None, None

    def read_rgb255(self):
        """Restituisce i valori RGB in scala 0-255."""
        r, g, b = self.read_normalized()
        if r is not None:
            return int(r * 255), int(g * 255), int(b * 255)
        return None, None, None