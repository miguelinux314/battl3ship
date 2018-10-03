#!/usr/bin/env python3
#
# This file is part of the Battl3ship game.
# 
#     Battl3ship is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
# 
#     Battl3ship is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
# 
#     You should have received a copy of the GNU General Public License
#     along with Battl3ship. If not, see <http://www.gnu.org/licenses/>.
"""The Battl3ship class represents a state of the game and provides tools
to validate and process player's actions, and update the game state accordingly.
"""
__author__ = "Miguel Hernández Cabronero <mhernandez314@gmail.com>"

############################ Begin configurable part
# Be verbose?
be_verbose = False

default_board_width = 10
default_board_height = 10

required_boat_count_by_length = {
    4: 1,
    3: 2,
    2: 3,
    1: 4,
}


############################ End configurable part

class Battl3ship:
    """The Battl3ship class represents a state of the game and provides tools
    to validate and process player's actions, and update the game state accordingly.

    See `Battl3ship.is_is_valid_boat_layout` for a complete description of the boat
    placement rules.

    See `Battl3ship.Board.shot` for a complete description of the rules for shooting
    and the interpretation of the returned results.
    """
    default_board_width = default_board_width
    default_board_height = default_board_height
    required_boat_count_by_length = required_boat_count_by_length

    def __init__(self, player_a, player_b, starting_player,
                 board_width=None, board_height=None):
        """Initialize a game and make it ready to be start()'ed.
        """
        self.player_a = player_a
        self.player_b = player_b
        self.board_width = board_width if board_width is not None else default_board_width
        self.board_height = board_height if board_height is not None else default_board_height
        self.player_a_board = Battl3ship.Board(
            width=self.board_width, height=self.board_height)
        self.player_b_board = Battl3ship.Board(
            width=self.board_width, height=self.board_height)

        self.player_turn = starting_player
        self.winner_player = None  # set only after game is finished
        self.accepting_shots = False  # set to True after set_boats has been called for both players

    @property
    def other_player(self):
        """Return the "other player", that is, the player whose turn it is not.
        """
        if self.player_turn == self.player_a:
            return self.player_b
        elif self.player_turn == self.player_b:
            return self.player_a
        else:
            raise Exception(
                "[other_player] Error! self.player_turn = {} != player_a, player_b".format(self.player_turn))

    @property
    def id(self):
        """Get a game id derived from the players' ids and who is player_a and who is player_b.
        """
        return Battl3ship.players_to_id(self.player_a, self.player_b)

    @staticmethod
    def players_to_id(player_a, player_b):
        """Get a game id derived from player_a's and player_b's ids
        """
        if player_a is None:
            player_a_id = "None"
        else:
            player_a_id = player_a.id
        if player_b is None:
            player_b_id = "None"
        else:
            player_b_id = player_b.id

        return "{} vs {}".format(player_a_id, player_b_id)

    def set_boats(self, player, row_col_lists):
        """Set the boat placement for a player, which must be self.player_a or self.player_b, and valid.

        Note that all row and col indices must be in the [1, height] and [1, width]
          ranges, respectively.

        :raise ValueError: if the row_col_lists do not describe a valid boat placement or player is neither
          `self.player_a` nor `self.player_b`, or boats were already placed.
        """
        if not self.is_valid_boat_layout(row_col_lists=row_col_lists):
            raise ValueError(f"Invalid boat layout {row_col_lists}")

        if player.id == self.player_a.id:
            board = self.player_a_board
        elif player.id == self.player_b.id:
            board = self.player_b_board
        else:
            raise ValueError(f"player {player} not player_a {player_a} nor player_b {player_b}")

        if board.locked:
            raise ValueError("Attempting to set_boats to an already locked Board")

        # Input seems correct. Update board and lock it.
        board.set_boats(row_col_lists)
        board.boat_row_col_list = list(row_col_lists)
        board.locked = True

    def is_valid_boat_layout(self, row_col_lists, ignore_boat_count=False):
        """
        Verify whether a given boat layout is valid for the game.

        The rules for a valid boat placement are as follows:
          * Each boat is represented by a list of (row, col) pairs. The number
            of boats and their lenghts is given by `self.boat_count_by_length`.

          * All row and col indices must be in the [1, `self.board_height`]
            and [1, `self.board_width`] ranges, respectively.

          * All boats must be entirely horizontal or entirely vertical. No corners,
            no disjoint squares.

          * Boats cannot share any square.

          * No boat square can be in the vecinity (NW, N, NE, W, E, SW, S or SE)
            of another boat's square).

          * All boats must have at least one square outside the edge (edge being
            the first and last rows, and the first and last columsn).

        :param row_col_lists: a list of boats, each represented by a list of (row, col) coordinates
         in [1, height] and [1, width], respectively.
        :param ignore_boat_count: if True, the condition that all boats must be placed
          is ignored. That is, zero or more boats can be considered a valid layout
          as long as the number of boats of each length does not EXCEED the maximum
          (and satisfy other conditions). If False, the number of boats of each length
          must be EQUAL TO the maximum defined in Battl3ship.boat_count_by_length.

        :return: True or False, depending on whether the boat layout is valid..
        """
        boat_count_by_length = dict()
        # d[row,col] -> [[r,c],[r,c],...] every square of the boat contributes one entry with its row,col
        boat_row_col_list_by_row_col = dict()

        try:
            # Check boat lengths
            for row_col_list in row_col_lists:
                for row, col in row_col_list:
                    boat_row_col_list_by_row_col[row, col] = list(row_col_list)
                if len(row_col_list) in boat_count_by_length:
                    boat_count_by_length[len(row_col_list)] += 1
                else:
                    boat_count_by_length[len(row_col_list)] = 1

            if not ignore_boat_count:
                assert all([boat_count_by_length.get(length, 0) == required_count
                            for length, required_count in required_boat_count_by_length.items()])
            else:
                assert all([boat_count_by_length.get(length, 0) <= required_count
                            for length, required_count in required_boat_count_by_length.items()])

            # Boat lengths can only be as configured
            assert all(found_key in required_boat_count_by_length.keys()
                       for found_key in boat_count_by_length.keys())

            # pool of all used squares
            used_row_col_list = [tuple(row_col)
                                 for row_col_list in row_col_lists
                                 for row_col in row_col_list]
            # Check there are no duplicated squares
            assert len(used_row_col_list) == len(list(set(used_row_col_list)))

            for i in range(len(row_col_lists)):
                boat_a = row_col_lists[i]

                # Enforce the edge rule
                assert not all([row == 1 for row, col in boat_a])
                assert not all([row == 10 for row, col in boat_a])
                assert not all([col == 1 for row, col in boat_a])
                assert not all([col == 10 for row, col in boat_a])

                # Check that boat is a line and not disjoint
                if len(boat_a) > 1:
                    if all(row == boat_a[0][0] for row, col in boat_a[1:]):
                        # Horizontal boat
                        cols = sorted([col for _, col in boat_a])
                        assert cols == list(range(cols[0], cols[0] + len(cols)))
                    elif all(col == boat_a[0][1] for row, col in boat_a[1:]):
                        # Vertical boat
                        rows = sorted([row for row, _ in boat_a])
                        assert rows == list(range(rows[0], rows[0] + len(rows)))
                    else:
                        raise AssertionError("Row is not linear")

                # Check that this boat does not collide with any other
                for j in range(i+1, len(row_col_lists)):
                    boat_b = row_col_lists[j]

                    for r_a, c_a in boat_a:
                        for r_b, c_b in boat_b:
                            for dx_a in [-1, 0, 1]:
                                for dy_a in [-1, 0, 1]:
                                    assert (r_a + dy_a != r_b) or (c_a + dx_a != c_b)
            return True
        except AssertionError as ex:
            return False

    def shot(self, player_from, row_col_lists):
        """Make a shot in an active, accepting shots game, updating the receiving player's
        board and returning the combined shot results (and whether the game is finished).
        The value of `self.player_turn` is automatically updated by this method.

        The rules for shooting and the expected returned values are as follows:

                * A player cannot shot twice in the same square in the same game
                * If no shot hits a boat, both lists are empty
                * If a boat is hit by one or more shots and all its squares are hit,
                  the boat is "sunk" and its length appears in `sunk_length_list`.
                * The length of `sunk_length_list` is equal to the number
                  of boats sunk this turn. If two or more boats of the same length are sunk
                  in this turn, that length appears repeated those many times in
                  `sunk_length_list`.
                * If a boat is hit one or more times this turn but one or more squares
                  remain intact after this turn, it is "hit" (and not "sunk")
                  and its length is added once to `hit_length_list`.
                  For example, if a boat of length 3 is hit by two different shots
                  in a single turn and the third shot does not hit anything, the
                  result in that turn will be ([3], [])
                * If two or more boats of the same length are "hit" (but not "sunk"), their
                  length appears repeated those many times in `hit_length_list`.
                * If all boats of the receiving player are sunk, game_finished is True.
                  Otherwise it is false.

        This method verifies that the format and contents of the shots described by
        row_col_lists is valid. Otherwise, a ValueError is raised.

        :param player_from: must be equal to `self.player_turn` otherwise
          ValueError is raised.
        :param row_col_lists: a list of length-2 iterables (row, column) describing the
          shots made. Note that all row and col indices must be in the [1, height] and [1, width]
          ranges, respectively.

        :raise ValueError: if either the player or the shot is not valid.

        :return: hit_list, sink_list, game_finished
        """
        if not self.accepting_shots:
            raise ValueError("This board is not accepting shots")
        if player_from != self.player_turn:
            raise ValueError(f"Invalid player_from {player_from}. "
                             f"Is it their turn (player_turn={self.player_turn}?")

        # Check that the shooting player is in their turn
        if player_from.id == self.player_a.id:
            opponent_board = self.player_b_board
        elif player_from.id == self.player_b.id:
            opponent_board = self.player_a_board
        else:
            raise ValueError(f"Unknown player_from {player_from}")

        # Enforce correct format
        if len(row_col_lists) != 3 \
                or any(len(rc) != 2 for rc in row_col_lists) \
                or any((not 1 <= r <= self.board_height) or (not 1 <= c <= self.board_height)
                       for r, c in row_col_lists):
            raise ValueError(f"Invalid row_col_lists = {row_col_lists}")

        # Avoid duplicated shots
        if any(rc == row_col_lists[0] for rc in row_col_lists[1:]) \
                or any(opponent_board[r, c].shot_id_list for r, c in row_col_lists):
            raise ValueError("Invalid (repeated) shot")

        # Make actual shot
        hit_list, sink_list, game_finished = opponent_board.shot(row_col_lists)
        if game_finished:
            self.winner_player = self.player_turn

        # Switch turns
        self.player_turn = self.other_player

        return hit_list, sink_list, game_finished

    def __str__(self):
        return "[Battl3ship#{}:PlayerA={} vs PlayerB={}:player_turn={}".format(
            self.id, self.player_a, self.player_b, self.player_turn)

    class Board:
        """Represent a player's game board state and offer an interface to update it.

        The access method board[x,y] returns the corresponding Square instance, which in
        turn can be queried to obtain any boats or shots placed there.
        """

        def __init__(self, width=default_board_width, height=default_board_height):
            self.width = width
            self.height = height
            self.square_by_xy = {(x, y): Battl3ship.Square(x, y) for x in range(width + 1) for y in range(height + 1)}
            self.locked = False
            self.shots = []
            self.boat_row_col_list = None

        def shot(self, row_col_lists):
            """Make a shot on the board, updating the squares as necessary, and reporting the combined
            shot results as (hit_length_list, sunk_length_list, game_finished)
            as described in `Battl3ship.shot`.

            Some sanity checks are performed, but the caller is responsible for verifying input
            format and semantics.
            
            :param row_col_lists: the shot in format ((r1,c1), (r2,c2), (r3,c3)).
              Any number of shots can be fired in the same coordinates.
            :return: hit_length_list, a sorted list of the lengths of the hit ships (if any)
                     sunk_length_list, a sorted list of the lengths of the sunk ships (if any)
                     game_finished, true iff all boats have been sunk in this board
            """
            assert self.locked
            self.shots.append(row_col_lists)
            shot_id = len(self.shots)

            hit_boats = []
            sunk_boats = []

            for (row, col) in row_col_lists:
                # Add the shot to the corresponding square
                self[row, col].shot_id_list.append(shot_id)

                # Find any boat hit or sunk by this shot, and append it
                # to hit_boats and sunk_boats
                if len(self[row, col].shot_id_list) == 1:
                    # Only reporting the first shot on each square
                    boat_as_tuples = tuple([(r, c) for (r, c) in self[row, col].boat_row_col_list])
                    if len(boat_as_tuples) == 0:
                        continue

                    boat_shot_bools = [len(self[boat_row, boat_col].shot_id_list) > 0
                                       for (boat_row, boat_col) in self[row, col].boat_row_col_list]
                    if all(boat_shot_bools):
                        sunk_boats.append(boat_as_tuples)
                    if any(boat_shot_bools):
                        hit_boats.append(boat_as_tuples)

            # Each boat is reported only once.
            sunk_boats = list(set(sunk_boats))
            hit_boats = [b for b in list(set(hit_boats))
                         if b not in sunk_boats]

            game_finished = True
            for row_col_list in self.boat_row_col_list:
                if not game_finished:
                    break
                for row, col in row_col_list:
                    if len(self[row, col].shot_id_list) == 0:
                        game_finished = False
                        break

            return sorted(len(boat) for boat in hit_boats), \
                   sorted(len(boat) for boat in sunk_boats), \
                   game_finished

        def set_boats(self, row_col_lists):
            for row_col_list in row_col_lists:
                for row, col in row_col_list:
                    self[row, col].boat_row_col_list = list(row_col_list)

        def __getitem__(self, index):
            """Get the square or list of Squares at the positions given by
            a r,c slice.
            """
            if len(index) != 2:
                raise Exception("[Board.__getitem__] Error! This is a 2D board, please index by (x,y)")
            if isinstance(index[0], slice) or isinstance(index[1], slice):
                matching_squares = []
                if isinstance(index[0], slice):
                    x_coordinates = range(*index[0].indices(self.width))
                else:
                    x_coordinates = [index[0]]
                if isinstance(index[1], slice):
                    y_coordinates = range(*index[1].indices(self.height))
                else:
                    y_coordinates = [index[1]]

                for x in x_coordinates:
                    for y in y_coordinates:
                        matching_squares.append(self.square_by_xy[(x, y)])
                return matching_squares
            else:
                return self.square_by_xy[index]

        def __str__(self):
            """Return a textual representation of the board.

            Key:
                "·" : empty square
                "B" : boat square (not hit)
                "H" : boat square (hit or sunk)
                "M" : missed shot (no boat)
            """
            empty_char = "·"
            nothit_boat_char = "B"
            hit_boat_char = "H"
            missed_shot_char = "M"

            representation_chars = ["+"] + (["-"] * self.width) + ["+", "\n"]
            for r in range(1, self.height + 1):
                representation_chars.append("|")
                for c in range(1, self.height + 1):
                    if not self[r, c].boat_row_col_list:
                        if self[r, c].shot_id_list:
                            representation_chars.append(missed_shot_char)
                        else:
                            representation_chars.append(empty_char)
                    else:
                        if self[r, c].shot_id_list:
                            representation_chars.append(hit_boat_char)
                        else:
                            representation_chars.append(nothit_boat_char)
                representation_chars.append("|")
                representation_chars.append("\n")
            representation_chars += ["+"] + (["-"] * self.width) + ["+"]
            return "".join(representation_chars)

    class Square:
        """Represent a board's square, and provide fast access to the any boat or
        shot placed in it.

        * The `self.boat_row_col_list` property contains either an empty list (if no
          boat is placed in the squre, or a list of (x,y) coordinates representing
          the coordinates of the boat placed in this square.

        * The `self.shot_id_list` contains a (possibly) empty list of shot ids
          performed in this square.
        """

        def __init__(self, x, y, shot_id_list=None, boat_row_col_list=None):
            self.x = x
            self.y = y
            self.shot_id_list = shot_id_list
            if self.shot_id_list is None:
                self.shot_id_list = []
            self.boat_row_col_list = boat_row_col_list
            if self.boat_row_col_list is None:
                self.boat_row_col_list = []

        def __str__(self):
            s = "|Square({x},{y})".format(x=self.x, y=self.y)
            if self.boat_row_col_list is not None:
                s += "@ B={}".format(self.boat_row_col_list)
            if self.shot_id_list is not None:
                s += "<-{}".format(self.shot_id_list)
            return s + "|"

        def __repr__(self):
            return self.__str__()


def test_syntax():
    width = 10
    height = 30
    board = Battl3ship.Board(width=width, height=height)

    for x in range(width):
        for y in range(height):
            assert board[x, y].x == x
            assert board[x, y].y == y

    print(board[0, 0])
    import random
    boat_list = [random.randint(0, 10) for _ in range(random.randint(10, 20))]
    shot_id_list = [random.randint(0, 10) for _ in range(random.randint(25, 30))]
    board[0, 0].shot_id_list = list(shot_id_list)
    board[0, 0].boat_list = list(boat_list)
    print(board[0, 0])

    print("[game.py] Tests ok!")


if __name__ == '__main__':
    test_syntax()
