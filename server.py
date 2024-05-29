import socket
import threading
import json
from json import JSONDecodeError
from constants import MAX_PLAYERS, MESSAGE_TYPE
from player import Player


class Server:
    def __init__(self, host='0.0.0.0', port=12345):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.leader = None
        self.players = []
        self.shots = {}
        self.players_ready_for_next_turn = 0
        self.turn_result = []
        self.barrier = None
        self.turn_barrier = None

    def start(self):
        '''
        Lida com as configurações do servidor
        '''
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(MAX_PLAYERS)
        print(f'Server started and listening on port {self.port}')

        while True:
            conn, addr = self.server_socket.accept()
            if len(self.players) < MAX_PLAYERS:
                player = Player(conn, addr)
                self.broadcast(json.dumps({'address': addr}), player)
                threading.Thread(target=self.handle_client,
                                 args=(player,)).start()
            else:
                self.broadcast('Server is full. Try again later.\n', player)
                conn.close()

    def handle_client(self, player):
        '''
        Lida com as mensagens recebidas dos clientes
        '''
        print(f'New connection from {player.address}')
        self.check_leader(player)
        self.players.append(player)

        while True:
            try:
                message = player.connection.recv(1024).decode()
                try:
                    response = json.loads(message)
                except JSONDecodeError:
                    response = message

                if not response:
                    break
                else:
                    self.handle_response(player, response)
            except ConnectionResetError:
                break

        self.disconnect(player)

    def handle_keywords_response(self, player, response):
        '''
        Lida com as mensagens recebidas utilizando palavras-chave
        '''
        if player.is_leader and response == 'go':
            self.broadcast(MESSAGE_TYPE['ready'])
        elif player.is_leader and response == 'start':
            self.barrier = threading.Barrier(len(self.players))
            self.turn_barrier = threading.Barrier(len(self.players))
            self.broadcast(MESSAGE_TYPE['player_turn'])

    def check_game_is_over(self):
        winner = None
        player_with_most_ships_sank = None
        remaining_players = [p for p in self.players if not p.has_lost]
        if (len(remaining_players) == 1):
            winner = remaining_players[0]
            player_with_most_ships_sank = self.get_player_with_most_ships_sank()
        return winner

    def handle_response(self, player, response):
        '''
        Lida com as mensagens genéricas recebidas
        '''
        if isinstance(response, dict):
            self.handle_dict_response(player, response)
        elif response == MESSAGE_TYPE['turn_ready']:
            self.players_ready_for_next_turn += 1
            if len(self.players) == self.players_ready_for_next_turn:
                self.broadcast(MESSAGE_TYPE['player_turn'])
        else:
            self.handle_keywords_response(player, response)

    def handle_dict_response(self, player, response):
        '''
        Lida com as mensagens recebidas do tipo dict
        '''
        if matrix := response.get('matrix'):
            player.matrix = matrix
            all_matrices_non_empty = all(p.matrix for p in self.players)
            other_non_empty_matrices = [
                p for p in self.players if p != player and p.matrix]
            if all_matrices_non_empty:
                self.broadcast(MESSAGE_TYPE['ready_ships'], self.leader)
            elif not other_non_empty_matrices:
                self.broadcast(MESSAGE_TYPE['not_ready_ships'], player)
        if coord := response.get('coordinates'):
            self.shots[player] = coord
            try:
                self.barrier.wait()
                # Todos os tiros que não são do próprio player
                other_shots = {p: c for p,
                               c in self.shots.items() if p != player}
                self.play_turn(player, other_shots)
                self.turn_barrier.wait()

                self.players_ready_for_next_turn = 0
                if player.has_lost:
                    self.broadcast('Você foi eliminado!', player)

                if winner := self.check_game_is_over():
                    self.broadcast(
                        MESSAGE_TYPE['game_over'] + """Vencedor: {0}\nJogador que afundou mais navios: {1}""".format(winner.address[1], 0, player))
                    self.disconnect(player)
                else:
                    self.broadcast(json.dumps(
                        {'turn_result': self.turn_result}), player)

                self.shots = {}
                self.turn_result = []
            except threading.BrokenBarrierError:
                print("Erro na barreira")

        # if coord := response.get('coordinates'):
            # self.shots.append((player, coord))
            # wait for all players make their shots
            # if len(self.shots) == len(self.players) - self.players_alive:
            #     self.play_turn(self.shots)
            #     self.players_ready_for_next_turn = 0
            #     self.shots = []
            # else:
            #     self.broadcast(MESSAGE_TYPE['wait_players'])

    def broadcast(self, message, specific_player=None):
        '''
        Executa o envio de mensagens para o(s) cliente(s)
        '''
        if specific_player:
            try:
                if not specific_player.has_lost:
                    specific_player.connection.sendall(message.encode('utf-8'))
            except:
                pass
        else:
            for player in self.players:
                if not player.has_lost:
                    try:
                        player.connection.sendall(message.encode('utf-8'))
                    except:
                        pass

    def check_leader(self, player):
        '''
        Verifica quem é o líder do jogo
        '''
        if len(self.players) == 0:
            self.leader = player
            player.is_leader = True
            self.broadcast(MESSAGE_TYPE['leader'], player)
        else:
            self.broadcast(MESSAGE_TYPE['player'], player)

    def disconnect(self, player):
        '''
        Desconecta jogador do servidor e passa o líder o próximo jogador da lista
        '''
        print(f'Connection closed from {player.address}')
        self.players.remove(player)
        player.connection.close()
        if player.is_leader and len(self.players) > 0:
            # player.is_leader = False
            new_leader = self.players[0]
            new_leader.is_leader = True
            self.broadcast(MESSAGE_TYPE['new_leader'], new_leader)

    def play_turn(self, target, shots):
        '''
        Executa o turno para os jogadores
        '''
        for player, coord in shots.items():
            x, y = self.parse_coordinates(coord)
            value = ''
            if target.matrix[x][y] == '*':
                value = 'X'
                target.matrix[x][y] = value
                # player.ships_sank += 1
            else:
                value = 'O'
                target.matrix[x][y] = value

            result = {
                'x': x,
                'y': y,
                'value': value,
                'from': str(player.address[1]),
                'to': str(target.address[1])
            }
            
            print(result)
            self.turn_result.append(result)
            if self.was_player_eliminated(target):
                target.has_lost = True

    def parse_coordinates(self, response):
        coord = response.replace('(', '').replace(')', '')
        x, y = coord.split(',')
        return int(x), int(y)

    def get_player_with_most_ships_sank(self):
        '''
        Retorna o jogador que afundou mais navios e o número de navios afundados
        '''
        most_ships_sank_player = max(
            self.players, key=lambda client: client.ships_sank)
        return most_ships_sank_player

    def was_player_eliminated(self, player):
        return not self.matrix_has_ships(player.matrix)

    def matrix_has_ships(self, matrix):
        for linha in matrix:
            if '*' in linha:
                return True
        return False


if __name__ == '__main__':
    server = Server()
    server.start()
