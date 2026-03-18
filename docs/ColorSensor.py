class ColorSensor:
    def __init__(self, sim, sensor_path):
        """Inizializza il sensore di colore."""
        self.sim = sim
        self.sensor_handle = self.sim.getObject(sensor_path)
        
    def read_normalized(self):
        """Legge dal sensore e restituisce i valori RGB normalizzati (0.0 - 1.0)."""
        res, p1, p2 = self.sim.handleVisionSensor(self.sensor_handle)
        
        if res >= 0 and p1 and len(p1) > 12:
            r = round(p1[10], 3)
            g = round(p1[11], 3)
            b = round(p1[12], 3)
            return r, g, b
            
        return None, None, None # Restituisce None se non ci sono dati validi

    def read_rgb255(self):
        """Restituisce i valori RGB in scala 0-255."""
        r, g, b = self.read_normalized()
        
        if r is not None:
            return int(r * 255), int(g * 255), int(b * 255)
            
        return None, None, None