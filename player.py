class Player:
    def __init__(self, conn, addr):
        self.connection = conn
        self.address = addr
        self.matrix = []
        self.is_leader = False
        self.ships_sank = 0
        self.has_lost = False
