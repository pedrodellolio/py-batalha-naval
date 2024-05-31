import socket
import json
import threading

from constants import MAX_PLAYERS, MIN_PLAYERS, MESSAGES

connected = 0
leader = None
players = []
eliminated = []

ships_sank = {}
boards = {}
shots = {}
turns = []
turn_number = 0

shot_barrier = threading.Barrier(MIN_PLAYERS)
board_barrier = threading.Barrier(MIN_PLAYERS)
turn_barrier = threading.Barrier(MIN_PLAYERS)


def update_barrier():
    global shot_barrier, board_barrier, turn_barrier
    if (connected >= MIN_PLAYERS):
        shot_barrier = threading.Barrier(connected-len(eliminated))
        board_barrier = threading.Barrier(connected-len(eliminated))
        turn_barrier = threading.Barrier(connected-len(eliminated))


def is_player_eliminated(target):
    port = target.getpeername()[1]
    print(boards)
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
    ships_sank = {conn.getpeername()[1]: 0 for conn in players}
    print(ships_sank)


def get_player_with_most_ships_sank():
    if not ships_sank:
        return None
    return max(ships_sank, key=ships_sank.get)


def play_turn(target):
    global turns, turn_number
    target_port = target.getpeername()[1]
    other_shots = [(port, shot["coordinates"])
                   for port, shot in shots.items() if port != target_port]

    for port, coordinates in other_shots:
        x, y = coordinates
        if boards[target_port][x][y] == 1:
            value = 'X'
            boards[target_port][x][y] = value
            ships_sank[port] += 1
            if target not in eliminated and is_player_eliminated(target):
                eliminated.append(target)
        else:
            value = 'O'
            boards[target_port][x][y] = value

        shots[port]["value"] = value
        shots[port]["target"] = target_port

        turns.append({
            "turn": turn_number,
            "coordinates": coordinates,
            "value": value,
            "target": target_port,
            "origin": port
        })


def get_turn_by_number(number):
    return [turn for turn in turns if turn["turn"] == number]


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
                        board_barrier.wait()
                    except threading.BrokenBarrierError:
                        print("[ATENÇÃO]: Erro ao aguardar por outros jogadores.")

                    if board_barrier.broken:
                        conn.sendall(MESSAGES["no_players"].encode())
                        break

                    if connected == len(boards):
                        initialize_ships_sank_dict()
                        conn.sendall(json.dumps({"message": MESSAGES["game_starting"], "players": [
                                     conn.getpeername()[1] for conn in players]}).encode())

                if coordinates := message.get("coordinates"):
                    global turn_number

                    shots[port] = {"coordinates": coordinates,
                                   "value": "", "target": 0}

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
                             "most_ships_sank": player_with_most_ships_sank}).encode())
                    elif conn in eliminated:
                        conn.sendall(MESSAGES["eliminated"].encode())
                        update_barrier()
                    else:
                        eliminated_ports = [conn.getpeername()[1]
                                            for conn in eliminated]
                        conn.sendall(json.dumps(
                            {"turn": get_turn_by_number(turn_number),
                             "eliminated": eliminated_ports}).encode())

                    if conn == leader:
                        turn_number += 1
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
    update_barrier()

    if not players:
        leader = conn

    players.append(conn)
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
