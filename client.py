import socket
import json
import re

from constants import MESSAGES

eliminated = False
matrices = {}
players_eliminated = []
initial_board = [[0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0],
                 [0, 0, 0, 0, 0]]


def format_boards(response):
    return


def is_valid_board(board_str):
    try:
        board = json.loads(board_str)
        if not isinstance(board, list):
            return False
        for row in board:
            if not isinstance(row, list):
                return False
            for value in row:
                if not isinstance(value, (int, str)):
                    return False
        return True
    except json.JSONDecodeError:
        return False


def parse_board(board_str):
    if is_valid_board(board_str):
        return json.loads(board_str)
    return None


def parse_coordinates(coord_str):
    pattern = r"\(\d+,\d+\)"
    if re.match(pattern, coord_str):
        x, y = map(int, coord_str.strip("()").split(","))
        return (int(x), int(y))
    return None


def get_client_board_input():
    print("Monte seu tabuleiro:")
    for row in initial_board:
        print(row)

    # Permite ao jogador alterar os valores da matriz
    new_board = []
    for i, row in enumerate(initial_board):
        new_row = input(
            f"Digite os valores para a linha {i+1} separados por vírgula (1 - barco; 0 - água): ").split(",")
        new_board.append([int(value.strip()) if value.strip(
        ).isdigit() else value.strip() for value in new_row])

    print("Tabuleiro final:")
    for row in new_board:
        print(row)
    return new_board


def process_turn(turn_result):
    global matrices

    for result in turn_result:
        coordinates = result["coordinates"]
        value = result["value"]
        target = result["target"]

        x, y = coordinates
        matrices[target][x][y] = value

    for port, matrix in matrices.items():
        print(f"Port: {port}")
        for row in matrix:
            print(' '.join(cell if cell else '.' for cell in row))
        print()  # Linha em branco para separar as matrizes


def initialize_players_matrices(players):
    global matrices

    for player in players:
        matrix = [['.' for _ in range(5)] for _ in range(5)]
        matrices[player] = matrix


client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server_address = ('localhost', 12345)
print('Conectando a {} na porta {}'.format(*server_address))
client_socket.connect(server_address)

try:
    board = get_client_board_input()
    client_socket.sendall(json.dumps({'matrix': board}).encode())
    while not eliminated:
        response = client_socket.recv(4096).decode()

        try:
            message = json.loads(response)
        except json.JSONDecodeError:
            message = response

        print('[SERVIDOR]:', message)

        if message == MESSAGES["no_players"]:
            break
        if isinstance(message, dict):
            if players := message.get("players"):  # MESSAGES['game_starting']:
                initialize_players_matrices(players)
                coord = parse_coordinates(
                    input('[CLIENT]: Escolha uma posição (x,y): '))
                if coord:
                    client_socket.sendall(json.dumps(
                        {'coordinates': coord}).encode())
                else:
                    print(
                        "[ATENÇÃO]: Formato inválido. Passe as coordenadas no formato (x,y)!")

            if turn := message.get("turn"):
                process_turn(turn)
                if eliminated_players := message.get("eliminated"):
                    new_eliminated = [
                        player for player in eliminated_players if player not in players_eliminated]
                    players_eliminated.extend(new_eliminated)
                    if new_eliminated:
                        print("Os jogadores", new_eliminated,
                              "foram eliminados.")
                coord = parse_coordinates(
                    input('[CLIENT]: Escolha uma posição (x,y): '))
                client_socket.sendall(json.dumps(
                    {'coordinates': coord}).encode())

            if winner := message.get("winner"):
                print(f"""Fim de jogo!\nVencedor: {winner}\nJogador que mais afundou navios: {
                      message.get("most_ships_sank")}""")
                break
finally:
    client_socket.close()
