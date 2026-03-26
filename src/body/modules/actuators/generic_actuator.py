class GenericActuator:
    def __init__(self, name):
        """
        Classe base per tutti gli attuatori (motori, lift, bracci).
        :param name: Nome identificativo dell'attuatore.
        """
        self.name = name

    def move(self, *args, **kwargs):
        """
        Metodo astratto per il movimento. 
        Deve essere implementato dalle sottoclassi.
        """
        raise NotImplementedError("Le sottoclassi devono implementare il metodo move()")

    def stop(self):
        """
        Metodo astratto per fermare l'attuatore.
        """
        raise NotImplementedError("Le sottoclassi devono implementare il metodo stop()")