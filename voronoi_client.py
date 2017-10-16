import socket, time, random, sys, math

class Client:
  def __init__(self, host, port, name):
    self.host = host
    self.port = port
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.name = name

    # hard-coded game info
    self.grid_size = 20
    self.min_dist = 0

    # connect to server and get game info
    self.sock.connect((host, port))
    self.num_players, self.num_stone, self.player_number = map(int, self.__receive_move())
    self.grid = [[0] * self.grid_size for i in range(self.grid_size)]
    self.moves = [] # store history of moves

    # send name to serer
    self.__send(self.name)
    print("Client initialized")

  def __receive(self):
    return self.sock.recv(2048).decode('utf-8')

  def __send(self, string):
    self.sock.sendall(string.encode('utf-8'))

  def __receive_move(self):
    return self.__receive().split()

  def __send_move(self, move_row, move_col):
    self.__send("{} {}".format(move_row, move_col))

  def __compute_distance(self, row1, col1, row2, col2):
    return math.sqrt((row2 - row1)**2 + (col2 - col1)**2)

  def __is_valid_move(self, move_row, move_col):
    for move in self.moves:
      if (self.__compute_distance(move_row, move_col, move[0], move[1])) < self.min_dist:
        return False
    return True

  # your algorithm goes here
  # a naive random algorithm is provided as a placeholder
  def __getMove(self):
    move_row = 0
    move_col = 0
    while True:
      move_row = random.randint(0, self.grid_size - 1)
      move_col = random.randint(0, self.grid_size - 1)
      if (self.__is_valid_move(move_row, move_col)):
        break

    return move_row, move_col

  def start(self):
    while True:
      move_data = self.__receive_move()
      # check if game is over
      if int(move_data[0]) == 1:
        print("Game over")
        break

      # scores
      scores = []
      for i in range(self.num_players):
        scores.append(move_data[i + 1])
      # new moves
      new_moves = move_data[self.num_players + 1 : ]
      num_new_moves = int(len(new_moves) / 3)
      # sanity check
      if num_new_moves * 3 != len(new_moves):
        print("Error: error parsing list of new moves")

      # insert new moves into the grid
      for i in range(num_new_moves):
        move_row = int(new_moves[3 * i])
        move_col = int(new_moves[3 * i + 1])
        player = int(new_moves[3 * i + 2])
        # sanity check, this should always be true
        if player > 0:
          self.grid[move_row][move_col] = player
          self.moves.append((move_row, move_col, player))
        else:
          print("Error: player info incorrect")

      # make move
      my_move_row, my_move_col = self.__getMove()
      self.moves.append((my_move_row, my_move_col, self.player_number))
      self.__send_move(my_move_row, my_move_col)
      print("Played at row {}, col {}".format(my_move_row, my_move_col))

    self.sock.close()

if (__name__ == "__main__"):
  host = sys.argv[1]
  port = int(sys.argv[2])
  name = sys.argv[3]
  # note: whoever connects to the server first plays first
  client = Client(host, port, name)
  client.start()
