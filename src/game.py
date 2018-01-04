#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
#     along with Foobar.  If not, see <http://www.gnu.org/licenses/>.
"""Represent the state of a game
"""
__author__ = "Miguel Hernández Cabronero <mhernandez314@gmail.com>"
__date__ = "25/09/2017"

############################ Begin configurable part
# Be verbose?
be_verbose = True


############################ End configurable part

class Game3Shots:
    default_board_width = 10
    default_board_height = 10
    required_boat_count_by_length = {
        4: 1,
        3: 2,
        2: 3,
        1: 4,
    }

    def __init__(self, player_a, player_b, starting_player):
        """Initialize a game and make it ready to be start()ed
        """
        self.player_a = player_a
        self.player_b = player_b
        self.player_a_board = Game3Shots.Board(width=self.default_board_width, height=self.default_board_height)
        self.player_b_board = Game3Shots.Board(width=self.default_board_width, height=self.default_board_height)

        self.player_turn = starting_player
        self.winner_player = None # set only after game is finished
        self.accepting_shots = False

    @property
    def other_player(self):
        if self.player_turn == self.player_a:
            return self.player_b
        elif self.player_turn == self.player_b:
            return self.player_a
        else:
            raise Exception(
                "[other_player] Error! self.player_turn = {} != player_a, player_b".format(self.player_turn))

    @property
    def id(self):
        return Game3Shots.players_to_id(self.player_a, self.player_b)

    @staticmethod
    def players_to_id(player_a, player_b):
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
        """Set the boat placement for a player, which must be self.player_a or self.player_b..
        """
        assert self.is_valid_boat_layout(row_col_lists=row_col_lists)

        if player.id == self.player_a.id:
            board = self.player_a_board
        elif player.id == self.player_b.id:
            board = self.player_b_board
        else:
            raise Exception("[set_boats] Error! player {} not player_a {} nor player_b {}".format(
                player, self.player_a, self.player_b))

        print "Setting boats for", player, ":", row_col_lists
        assert not board.locked
        for row_col_list in row_col_lists:
            for row, col in row_col_list:
                board[row, col].boat_row_col_list = list(row_col_list)
        board.boat_row_col_list = list(row_col_lists)
        board.locked = True

    def is_valid_boat_layout(self, row_col_lists):
        boat_count_by_length = dict()
        boat_row_col_list_by_row_col = dict()  # d[row,col] -> [[r,c],[r,c],...] every square of the boat contributes one entry with its row,col

        try:
            # Check boat lengths
            for row_col_list in row_col_lists:
                for row, col in row_col_list:
                    boat_row_col_list_by_row_col[row, col] = list(row_col_list)
                if len(row_col_list) in boat_count_by_length:
                    boat_count_by_length[len(row_col_list)] += 1
                else:
                    boat_count_by_length[len(row_col_list)] = 1
            assert len(boat_count_by_length.values()) == len(self.required_boat_count_by_length.values())
            assert all([v == boat_count_by_length[k] for k, v in self.required_boat_count_by_length.iteritems()])

            # pool of all used squares (check no duplicates)
            used_row_col_list = [tuple(row_col)
                                 for row_col_list in row_col_lists
                                 for row_col in row_col_list]
            assert len(used_row_col_list) == len(list(set(used_row_col_list)))
            used_row_col_list = list(set(used_row_col_list))
            for row_col_list in row_col_lists:
                for row, col in row_col_list:
                    # For each boat square, check that all surrounding space is valid (empty or same boat)
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            for ddx in [-1, 0, 1]:
                                for ddy in [-1, 0, 1]:
                                    if [row + dy + ddy, col + dx + ddx] in used_row_col_list:
                                        assert boat_row_col_list_by_row_col[row, col] == \
                                               boat_row_col_list_by_row_col[row + dy + ddy, col + dx + ddx]

                # Enforce the edge rule
                assert not all([row == 1 for row, col in row_col_list])
                assert not all([row == 10 for row, col in row_col_list])
                assert not all([col == 1 for row, col in row_col_list])
                assert not all([col == 10 for row, col in row_col_list])

                # Check that all boat is a line
                assert all([row == row_col_list[0][0] for row, col in row_col_list]) \
                       or all([col == row_col_list[0][1] for row, col in row_col_list])

            return True
        except AssertionError:
            return False

    def shot(self, player_from, row_col_lists):
        """Make a shot in an active, accepting shots game

        :return: hit_list, sink_list, game_finished
        """
        assert self.accepting_shots
        assert player_from == self.player_turn

        if player_from.id == self.player_a.id:
            opponent_board = self.player_b_board
        elif player_from.id == self.player_b.id:
            opponent_board = self.player_a_board
        else:
            raise Exception("[shot] Error! Unknown player_from {}".format(player_from))

        if len(row_col_lists) != 3:
            raise Exception("[shot] Error! Invalid row_col_lists = {} (len != 3)".format(row_col_lists))

        hit_list, sink_list, game_finished = opponent_board.shot(row_col_lists)
        if game_finished:
            self.winner_player = self.player_turn
        self.player_turn = self.other_player

        return hit_list, sink_list, game_finished

    def __str__(self):
        return "[Game3Shots#{}:PlayerA={} vs PlayerB={}:player_turn={}".format(
            self.id, self.player_a, self.player_b, self.player_turn)

    class Board:
        def __init__(self, width, height):
            self.width = width
            self.height = height
            self.square_by_xy = {(x, y): Game3Shots.Square(x, y) for x in xrange(width + 1) for y in xrange(height + 1)}
            self.locked = False
            self.shots = []
            self.boat_row_col_list = None

        def shot(self, row_col_lists):
            """Make a shot on the board, updating the squares as necessary
            
            :param row_col_lists: the shot in format [[r1,c1], [r2,c2], [r3,c3]]
            :return: hit_length_list, a list of the lengths of the hit ships (if any) 
                     sunk_length_list, a list of the lengths of the sunk ships (if any) 
                     game_finished, true iff all boats have been sunk in this board
            """
            assert self.locked
            self.shots.append(row_col_lists)
            shot_id = len(self.shots)

            hit_boats = []
            sunk_boats = []

            for (row, col) in row_col_lists:
                self[row, col].shot_id_list.append(shot_id)
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

            return map(len, hit_boats), map(len, sunk_boats), game_finished

        def __getitem__(self, xy_tuple):
            if len(xy_tuple) != 2:
                raise Exception("[Board.__getitem__] Error! This is a 2D board, please index by (x,y)")
            if isinstance(xy_tuple[0], slice) or isinstance(xy_tuple[1], slice):
                matching_squares = []
                if isinstance(xy_tuple[0], slice):
                    x_coordinates = xrange(*xy_tuple[0].indices(self.width))
                else:
                    x_coordinates = [xy_tuple[0]]
                if isinstance(xy_tuple[1], slice):
                    y_coordinates = xrange(*xy_tuple[1].indices(self.height))
                else:
                    y_coordinates = [xy_tuple[1]]

                for x in x_coordinates:
                    for y in y_coordinates:
                        matching_squares.append(self.square_by_xy[(x, y)])
                return matching_squares
            else:
                return self.square_by_xy[xy_tuple]

    class Square:
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


def test():
    width = 10
    height = 30
    board = Game3Shots.Board(width=width, height=height)

    for x in range(width):
        for y in range(height):
            assert board[x, y].x == x
            assert board[x, y].y == y

    print board[0, 0]
    import random
    boat_list = [random.randint(0, 10) for _ in range(random.randint(10, 20))]
    shot_id_list = [random.randint(0, 10) for _ in range(random.randint(25, 30))]
    board[0, 0].shot_id_list = list(shot_id_list)
    board[0, 0].boat_list = list(boat_list)
    print board[0, 0]

    print "[game.py] Tests ok!"


if __name__ == '__main__':
    test()
