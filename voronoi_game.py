from voronoi_server import VoronoiServer

import time, sys, math, socket
import numpy as np

class VoronoiGame:
  def __init__(self, num_stones, num_players, grid_size, min_dist, host, port, use_graphic):
    # game variables
    self.num_stones = num_stones
    self.num_players = num_players
    self.grid_size = grid_size
    self.min_dist = min_dist # minimum distance allowed between stones
    self.grid = np.zeros((grid_size, grid_size), dtype=np.int)
    self.score_grid = np.zeros((grid_size, grid_size), dtype=np.int)
    self.scores = [0] * num_players
    self.player_times = [120.0] * num_players
    # store moves played, each move corresponds to 3 entries
    self.moves = []
    # gravitational pull, pull[i] is 2d-array of the pull player i has in total
    self.pull = np.zeros((num_players, grid_size, grid_size), dtype=np.float32)
    self.current_player = 0
    self.moves_made = 0
    self.game_over = False

    # server that communicates to client
    self.server = VoronoiServer(host, port, num_players)
    # socket connection to web front end (udp)
    self.use_graphic = use_graphic
    self.graphic_socket = None
    if use_graphic:
      self.graphic_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.graphic_socket.connect(('localhost', 8080))

    # Used for compute pull. row_numbers and col_numbers are simply constant matrices with the value of the current row/col index
    self.row_numbers = np.zeros((grid_size, grid_size), dtype=np.float32)
    for i in range(grid_size):
      self.row_numbers[i] = self.row_numbers[i] + i
    self.col_numbers = np.transpose(self.row_numbers)

  def __get_game_info(self):
    # game over flag
    game_info = ("1" if self.game_over else "0") + " "
    # scores
    game_info += " ".join(str(i) for i in self.scores) + " "
    # new moves - go through move history in reverse order and stop when a move by current player is found
    new_moves = []
    for i in range(len(self.moves) - 1, 1, -3):
      if (self.moves[i] == self.current_player + 1):
        break
      for j in range(3):
        new_moves.append(self.moves[i - 2 + j])
    game_info += " ".join(str(i) for i in new_moves) + "\n"
    return game_info

  def __broadcast_game_info(self):
    game_info = self.__get_game_info()
    if self.game_over:
      for i in range(num_players):
        self.server.send(game_info, i)
    else:
      self.server.send(game_info, self.current_player)

  def __send_update_to_node(self, move_row, move_col):
    data = ''
    for score_row in self.score_grid:
      data += ' '.join(map(str, score_row)) + ' '
    data += ' '.join(map(str, self.scores)) + ' '
    data += '{} {} '.format(self.num_players, self.current_player + 1)
    data += '{} {}'.format(move_row, move_col)
    data += '\n' # signify the end of the message

    self.graphic_socket.sendall(data.encode('utf-8'))

  def __compute_distance(self, row1, col1, row2, col2):
    return math.sqrt((row2 - row1)**2 + (col2 - col1)**2)

  def __is_legal_move(self, row, col):
    if self.grid[row][col] != 0:
      print("({}, {}) is already occupied".format(row, col))
      return False
    if row < 0 or row >= self.grid_size:
      print("({}, {}) is out of bounds".format(row, col))
      return False
    if col < 0 or col >= self.grid_size:
      print("({}, {}) is out of bounds".format(row, col))
      return False
    # check for min dist requirement
    for move_start in range(0, len(self.moves), 3):
      move_row = self.moves[move_start]
      move_col = self.moves[move_start + 1]
      if (self.__compute_distance(row, col, move_row, move_col) < self.min_dist):
        print("({}, {}) is less than 66 unit distances away from ({}, {})".format(row, col, move_row, move_col))
        return False

    return True

  def __get_player_move(self):
    player_name = self.server.names[self.current_player]
    player_time = self.player_times[self.current_player]
    print("Waiting for {}".format(player_name))
    print("They have {} seconds remaining".format(player_time))

    start_time = time.time()
    client_response = self.server.receive(self.current_player)
    end_time = time.time()
    self.player_times[self.current_player] -= (end_time - start_time)

    data = client_response.split()
    return int(data[0]), int(data[1])

  def compute_pull(self, row, col):
    # squared_distance_matrix[i][j] is the squared distance from (i, j) to (row, col)
    squared_distance_matrix = np.square(self.row_numbers - row) + np.square(self.col_numbers - col)
    # This value would otherwise have been 0 and would therefore have caused an exception when taking the reciprocal
    squared_distance_matrix[row][col] = 0.1e-30
    # After taking the reciprocal it correctly indicates the pull added at at (i, j) by having a stone at (row, col)
    return np.reciprocal(squared_distance_matrix)

  def __update_scores(self, move_row, move_col):
    # Add pull from new stone to current pull
    self.pull[self.current_player] = self.pull[self.current_player] + self.compute_pull(move_row, move_col)
    print("New pull for player:")
    for row in self.pull[self.current_player]:
        for elem in row:
            if elem > 2:
                print('inf.', end=' ')
            else:
                print('{:.2f}'.format(elem), end=' ')
        print()
    # Update each point in the grid to be owned by the player with the highest pull
    self.score_grid = np.argmax(self.pull, axis=0) + 1
    print("New score grid:")
    for row in self.score_grid:
        for elem in row:
            print(elem, end=' ')
        print()

    # For each player set the score to be the sum of owned squares on the grid
    for i in range(self.num_players):
      self.scores[i] = np.sum(self.score_grid == (i+1))
    print("New scores:")
    print(self.scores)

  def __declare_winner(self):
    max_score = -1
    winners = []
    for i in range(self.num_players):
      player_name = self.server.names[i]
      player_score = self.scores[i]
      if self.scores[i] == -1:
        print("Illegal move by {}".format(player_name))
      elif self.scores[i] == -2:
        print("{} timed out".format(player_name))
      else:
        print("{} score: {}".format(player_name, player_score))

      if player_score == max_score:
        winners.append(i + 1)
      elif player_score > max_score:
        max_score = player_score
        winners = [i + 1]

    if len(winners) == 1:
      print("\nWinner: {}".format(self.server.names[winners[0] - 1]))
    else:
      print("Tied between: ")
      for winner in winners:
        print(" ".join([self.server.names[w - 1] for w in winners]))

  def start(self):
    self.server.establish_connection(self.num_players, self.num_stones)
    if self.use_graphic:
      graphic_init_msg = ' '.join(self.server.names) + '\n'
      self.graphic_socket.sendall(graphic_init_msg.encode('utf-8'))
    print('\nStarting...\n')

    while True:
      self.current_player = self.current_player % self.num_players
      self.__broadcast_game_info()
      if (self.game_over):
        break

      # get and validate move
      move_row, move_col = self.__get_player_move()
      print("{} has placed their stone on: {}, {}\n".format(self.server.names[self.current_player] , move_row, move_col))
      if not self.__is_legal_move(move_row, move_col):
        self.scores[self.current_player] = -1
        self.game_over = True
        continue

      # move is legal, do some book-keeping
      self.moves_made += 1
      self.grid[move_row][move_col] = self.current_player + 1
      self.moves.append(move_row)
      self.moves.append(move_col)
      self.moves.append(self.current_player + 1)
      self.__update_scores(move_row, move_col)
      if self.moves_made == 2:
          break

      # send data to node server
      if self.use_graphic:
        self.__send_update_to_node(move_row, move_col)

      # check for game over conditions
      if self.player_times[self.current_player] < 0:
        self.scores[self.current_player] = -2
        self.game_over = True
      if self.moves_made == self.num_players * self.num_stones:
        self.game_over = True

      # switch player
      self.current_player += 1

    self.__declare_winner()
    print("\nGame over")

if __name__ == "__main__":
  GRID_SIZE = 20
  MIN_DIST = 0
  num_stones = int(sys.argv[1])
  num_players = int(sys.argv[2])
  host = sys.argv[3]
  port = int(sys.argv[4])
  use_graphic = False
  if len(sys.argv) == 6 and int(sys.argv[5]) == 1:
      use_graphic = True

  game = VoronoiGame(num_stones, num_players, GRID_SIZE, MIN_DIST, host, port, use_graphic)
  game.start()
