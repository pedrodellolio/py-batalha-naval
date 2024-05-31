import socket
import json
import threading

from constants import MAX_PLAYERS, MIN_PLAYERS, MESSAGES

connected = 0

players = []
eliminated = []

ships_sank = {}
boards = {}
shots = {}

shot_barrier = threading.Barrier(MIN_PLAYERS)
board_barrier = threading.Barrier(MIN_PLAYERS)
turn_barrier = threading.Barrier(MIN_PLAYERS)


def update_barrier():
    global shot_barrier, board_barrier, turn_barrier
    if (connected >= MIN_PLAYERS):
        shot_barrier = threading.Barrier(connected)
        board_barrier = threading.Barrier(connected)
        turn_barrier = threading.Barrier(connected)


def is_player_eliminated(target):
    port = target.getpeername()[1]
    for row in boards[port]:
        if 1 in row:
            return False
    return True


def is_game_over():
    winner = None
    player_with_most_ships_sank = None
    if (len(eliminated) == connected - 1):
        winner = [player for player in players if player not in eliminated][0]
        player_with_most_ships_sank = get_player_with_most_ships_sank()
    return winner, player_with_most_ships_sank


def initialize_ships_sank_dict():
    global ships_sank
    ships_sank = {conn.getpeername(): 0 for conn in players}


def get_player_with_most_ships_sank():
    if not ships_sank:
        return None
    return max(ships_sank, key=ships_sank.get)


def play_turn(target):
    for player, coordinates in shots.items():
        if player != target:
            port = target.getpeername()[1]
            x, y = coordinates
            value = ''
            if boards[port][x][y] == 1:
                value = 'X'
                boards[port][x][y] = value
                ships_sank[port] += 1
                if is_player_eliminated(target):
                    eliminated.append(target)
            else:
                value = 'O'
                boards[port][x][y] = value


def handle_client(conn, port):
    try:
        while True:
            response = conn.recv(4096).decode()

            try:
                message = json.loads(response)
            except json.JSONDecodeError:
                message = response

            print(message)

            if not message:
                break
            if isinstance(message, dict):
                if board := message.get("matrix"):
                    boards[port] = board

                    try:
                        board_barrier.wait(timeout=3)
                    except threading.BrokenBarrierError:
                        print("[ATENÇÃO]: Erro ao aguardar por outros jogadores.")

                    if board_barrier.broken:
                        conn.sendall(MESSAGES["no_players"].encode())
                        break

                    conn.sendall(MESSAGES["game_starting"].encode())
                    if connected == len(boards):
                        initialize_ships_sank_dict()
                        conn.sendall(MESSAGES["game_starting"].encode())

                if coordinates := message.get("coordinates"):
                    shots[conn] = coordinates

                    try:
                        shot_barrier.wait()
                    except threading.BrokenBarrierError:
                        print("[ATENÇÃO]: Erro ao aguardar por outros jogadores.")

                    if len(shots) == connected:
                        play_turn(conn)

                    try:
                        turn_barrier.wait()
                    except threading.BrokenBarrierError:
                        print("[ATENÇÃO]: Erro ao aguardar por outros jogadores.")

                    winner, player_with_most_ships_sank = is_game_over()
                    if winner:
                        conn.sendall(json.dumps(
                            {"winner": winner.getpeername()[1],
                             "most_ships_sank": player_with_most_ships_sank.getpeername()[1]}).encode())
                    elif conn in eliminated:
                        conn.sendall(MESSAGES["eliminated"].encode())
                    else:
                        eliminated_ports = [conn.getpeername()[1]
                                            for conn in eliminated]
                        conn.sendall(json.dumps(
                            {"boards": boards, "eliminated": eliminated_ports}).encode())
    finally:
        conn.close()


server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server_address = ('localhost', 12345)
print('Iniciando servidor em {} na porta {}'.format(*server_address))
server_socket.bind(server_address)

server_socket.listen(MAX_PLAYERS)

while True:
    print('Aguardando por uma conexão...')
    conn, addr = server_socket.accept()
    connected += 1
    players.append(conn)
    update_barrier()
    try:
        print('Conexão de', addr)
        threading.Thread(
            target=handle_client, args=(conn, addr[1])).start()
    except Exception as e:
        print('Erro:', e)
        connected -= 1
        update_barrier()
        players.remove(conn)
        conn.close()
