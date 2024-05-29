import socket
import json
from constants import MESSAGE_TYPE, SHIP_TYPE, X_AXIS, Y_AXIS


class Client:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_address = None
        self.matrices = {}  # visualização dos tabuleiros de todos os jogadores da partida
        self.connected = False
        self.has_lost = False

    def connect(self):
        self.client.connect((self.host, self.port))
        self.connected = True

    def receive_message(self):
        return self.client.recv(1024).decode('utf-8')

    def send_message(self, message):
        self.client.sendall(message.encode('utf-8'))

    def handle_response(self, response):
        if isinstance(response, dict):
            if address := response.get('address'):
                self.player_address = address
            if turn_result := response.get('turn_result'):
                self.handle_turn_result(turn_result)
        else:
            print('[SERVIDOR]: ' + response)
            self.handle_text_response(response)

    def handle_turn_result(self, turn_result):
        self.build_matrices(turn_result)
        formatted_result = self.format_results()
        print(formatted_result)
        self.send_message(MESSAGE_TYPE['turn_ready'])

    def handle_text_response(self, response):
        if response == MESSAGE_TYPE['leader']:
            message = input(f'[{self.player_address[1]}]: ')
            self.send_message(message)
        elif response == MESSAGE_TYPE['ready']:
            self.start_placing_ships()
        elif response == MESSAGE_TYPE['player_turn']:
            message = input(f'[{self.player_address[1]}]: ')
            self.send_message(json.dumps({'coordinates': message}))
        elif response == MESSAGE_TYPE['ready_ships']:
            message = input(f'[{self.player_address[1]}]: ')
            self.send_message(message)
        elif response == MESSAGE_TYPE['player_lost']:
            self.disconnect()
        elif MESSAGE_TYPE['game_over'] in response:
            print("Jogo terminado.")
            return

    def disconnect(self):
        self.connected = False
        self.client.close()

    def start(self):
        self.connect()
        try:
            while self.connected:
                try:
                    message = self.receive_message()

                    try:
                        response = json.loads(message)
                    except json.JSONDecodeError:
                        response = message

                    if not response:
                        break
                    if not self.has_lost:
                        self.handle_response(response)
                except ConnectionResetError:
                    break
        finally:
            self.disconnect()

    def format_results(self):
        '''
        Formata as matrizes para mostrar no terminal para os jogadores
        '''
        headers = []
        formatted_boards = []
        max_rows = max(len(matrix) for matrix in self.matrices.values())

        # Adiciona os headers com os endereços centralizados
        for address, matrix in self.matrices.items():
            client_addr = str(self.player_address[1])
            if address == client_addr:
                headers.append(str('Você').center(len(matrix[0]) * 2 - 1))
            else:
                headers.append(str(address).center(len(matrix[0]) * 2 - 1))

        formatted_boards.append(' | '.join(headers))

        # Formata cada linha das matrizes
        for row in range(max_rows):
            row_parts = []
            for address, matrix in self.matrices.items():
                if row < len(matrix):
                    row_parts.append(' '.join(matrix[row]))
                else:
                    row_parts.append(' ' * (len(matrix[0]) * 2 - 1))
            formatted_boards.append(' | '.join(row_parts))

        return '\n'.join(formatted_boards)

    def update_ship_matrix(self, matrix, coordinates):
        for x, y in coordinates:
            matrix[x][y] = '*'

    def parse_ship_coordinates(self, response):
        positions = []
        for position in response.split(')('):
            coordinates = self.parse_coordinates(position)
            positions.append(coordinates)
        return positions

    def request_ship_position(self, ship_type, ship_number):
        print(f'Selecione a posicao do {ship_type} {
            ship_number} (ex: (linha,col)(linha,col)):\n')
        message = input()
        coordinates = self.parse_ship_coordinates(message)
        return coordinates

    def parse_coordinates(self, response):
        coord = response.replace('(', '').replace(')', '')
        x, y = coord.split(',')
        return (int(x), int(y))

    def handle_ship_placement(self, matrix):
        for ship, quantity in SHIP_TYPE.items():
            for i in range(quantity):
                coords = self.request_ship_position(ship, i+1)
                self.update_ship_matrix(matrix, coords)
                print(self.format_ship_matrix(matrix))

        self.matrices[str(self.player_address[1])] = matrix
        self.client.sendall(json.dumps({'matrix': matrix}).encode())

    def initialize_ship_matrix(self):
        return [['_' for _ in range(X_AXIS)] for _ in range(Y_AXIS)]

    def format_ship_matrix(self, matrix):
        return '\n'.join([' '.join(row) for row in matrix]) + '\n'

    def start_placing_ships(self):
        matrix = self.initialize_ship_matrix()
        formatted_matrix = self.format_ship_matrix(matrix)
        print(formatted_matrix)
        self.handle_ship_placement(matrix)

    def parse_ship_positions(self, response):
        positions = []
        for position in response.split(')('):
            position = position.replace('(', '').replace(')', '')
            x, y = position.split(',')
            positions.append((int(x), int(y)))
        return positions

    def build_matrices(self, result):
        addresses = []
        for shot in result:
            addresses.append(shot['from'])

        for shot in result:
            x = shot['x']
            y = shot['y']
            who_shot = shot['from']
            target = shot['to']
            value = shot['value']

            if self.matrices.get(target):
                self.matrices[target][x][y] = value
            else:
                matrix = self.initialize_ship_matrix()
                matrix[x][y] = value
                self.matrices[target] = matrix


            # for addr in addresses:
            #     if (who_shot != addr):
            #         if self.matrices.get(addr):
            #             self.matrices[addr][x][y] = value
            #         else:
            #             matrix = self.initialize_ship_matrix()
            #             matrix[x][y] = value
            #             self.matrices[addr] = matrix
if __name__ == '__main__':
    client = Client('localhost', 12345)
    client.start()
