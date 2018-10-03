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
"""Module to help generate random boat placements.
"""
__author__ = "Miguel Hernández Cabronero <mhernandez@deic.uab.cat>"

import itertools
import random
import time

from game import Battl3ship

# -------------------------- Begin configurable part

# Be verbose?
be_verbose = True


# -------------------------- End configurable part

def unique_permutations(sequence):
    """Knuth's "Algorithm L", that provides all permutations in lexicographical order
    """
    unique_permutations = []

    i_indices = range(len(sequence) - 1, -1, -1)
    # we'll be cheking seq[k] and seq[k+1], k should not point to the last element
    k_indices = range(len(sequence) - 2, -1, -1)

    # First element is the lexicographically sorted sequence
    sequence = sorted(sequence)

    while True:
        # The list constructor must be called because
        unique_permutations.append(list(sequence))

        # Find the last strictly ordered consecutive pair, seq[k] < seq[k+1]
        k = None
        for k_prime in k_indices:
            if sequence[k_prime] < sequence[k_prime + 1]:
                k = k_prime
                break
        if k is None:
            # No ordered pair: this is the last element in lexycographical order,
            # we're done
            break

        # Index i is that of the last element strictly larger than seq[k]
        seq_k = sequence[k]
        for i in i_indices:
            if seq_k < sequence[i]:
                break
        # Values are swapped to "break the ordering"
        (sequence[k], sequence[i]) = (sequence[i], sequence[k])

        # After the swap, seq[k] and seq[k+1] is a new "unordering"
        # Also, values seq[k+1] onwards are (by definition of k)
        # weakly ordered in descending order. They are inverted
        # so that sequence is actually the next one in lexicographical
        # ordering
        sequence[k + 1:] = sequence[-1:k:-1]

    return unique_permutations

class RandomBoatPlacer:
    """Class to produce random and valid boat placements.
    """
    # Used to avoid delays when generating boards.
    max_exploration_count = 100

    def __init__(self, width=None, height=None):
        """Initialize, optionally defining the board dimensions.
        :param width, height: board dimensions. If none, the defaults defined in game.Battl3ship are used.
        """
        self.width = width if width is not None else Battl3ship.default_board_width
        self.height = height if height is not None else Battl3ship.default_board_height

        # Used to validate positions without having to create a game
        # object every time
        self.dummy_game = Battl3ship(player_a=None, player_b=None, starting_player=None,
                                     board_width=width, board_height=height)

        lengths_sequence = list(itertools.chain(*(
            [length] * count for length, count in Battl3ship.required_boat_count_by_length.items())))
        # List of all unique permutations of the required boat lengths
        self.unique_length_permutations = unique_permutations(lengths_sequence)

        # List of all possible positions
        forbidden_positions = [(r, c)
                               for r in [1, Battl3ship.default_board_height]
                               for c in [1, Battl3ship.default_board_width]]
        self.remaining_positions = [(r, c)
                                    for r in range(1, Battl3ship.default_board_height + 1)
                                    for c in range(1, Battl3ship.default_board_width + 1)
                                    if (r, c) not in forbidden_positions]

    def get_random_placement(self):
        """Get a random valid boat placement.

        :return: a list of boats, each boat being a list of (row,col) coordinates.
          This is the format specified by `game.Battl3ship.set_boats`.
        """
        remaining_positions = list(self.remaining_positions)

        placement = None
        # Some configurations do not yield valid placements. Random configurations
        # are tried until one that yields a valid placement is found.
        # Most usually, 3 or less iterations are needed.
        while placement is None:
            # Boats are placed in a random order
            remaining_lengths = random.sample(self.unique_length_permutations, 1)[0]
            # Positions are explored in a random order
            random.shuffle(remaining_positions)

            placement, exploration_count = self._recursive_get_one_valid_placement(
                remaining_positions=remaining_positions,
                remaining_lengths=remaining_lengths,
                current_boat_placement=[],
                exploration_count=0)

        return placement

    def _recursive_get_one_valid_placement(self,
                                           remaining_positions,
                                           remaining_lengths,
                                           current_boat_placement,
                                           exploration_count):
        """Recursively obtain a valid boat placement placement.

        The number of function calls is limited by `self.max_exploration_count`
        to avoid overly lengthy computations. If no valid placement can be found
        after those many calls, None is returned instead of a board placement.

        :return: boat_placement, exploration_count, where exploration_count is the
          number of calls (based on the value of the `exploration_count` paramenter)
        """
        # Avoid overly lengthy computations
        exploration_count += 1
        if exploration_count > self.max_exploration_count:
            return None, exploration_count

        if not remaining_positions:
            return None, exploration_count

        # Base case: remaining boats and remaining positions.
        next_position = remaining_positions[0]
        next_length = remaining_lengths[0]

        orientation_order = [False, True]
        random.shuffle(orientation_order)
        for is_boat_horizontal in orientation_order:
            # Build tentative placement assuming next_length and next_position
            try:
                boat_row_cols, extended_row_cols = self._get_boat_rowcols(
                    position=next_position, length=next_length, is_horizontal=is_boat_horizontal)
            except ValueError as ex:
                continue

            tentative_placement = current_boat_placement + [boat_row_cols]

            if not self.dummy_game.is_valid_boat_layout(
                    row_col_lists=tentative_placement, ignore_boat_count=True):
                # Boat cannot be placed there. Horizontal and vertical orientations
                # are attempted, otherwise None is returned after the while loop
                continue

            if not remaining_lengths[1:]:
                # All boats are validly placed, no need to go any deeper
                return tentative_placement, exploration_count

            # There are boats left to place. Need to go one level deeper.
            # Remove redundant positions
            remaining_valid_positions = [(r, c)
                                         for r, c in remaining_positions[1:]
                                         if (r, c) not in boat_row_cols
                                         and (r, c) not in extended_row_cols]

            needed_position_count = sum(3 * (l + 1) for l in remaining_lengths[1:])
            if len(remaining_positions) < needed_position_count:
                # Not enough space, don't need to keep searching
                return None, exploration_count

            for position_sublist in (remaining_valid_positions[i:]
                                     for i in range(len(remaining_valid_positions))):
                placement, exploration_count = self._recursive_get_one_valid_placement(
                    remaining_positions=position_sublist,
                    remaining_lengths=remaining_lengths[1:],
                    current_boat_placement=tentative_placement,
                    exploration_count=exploration_count)
                if placement is not None:
                    return placement, exploration_count

        return None, exploration_count

    def _get_boat_rowcols(self, position, length, is_horizontal):
        """Get a list of (row, col) tuples that represent a boat with the top left corner
        placed at `position` and with orientation determined by `is_horizontal`.
        Also get the list of (row, col) tuples that represent the extra squares
        surrounding the boat.

        :return boat_rowcols, surrounding_rowcols

        :raise ValueError: if the boat would be outside the board
        """
        origin_r, origin_c = position
        if is_horizontal:
            boat_row_cols = [(origin_r, origin_c + i) for i in range(length)]
            surrounding_row_cols = \
                [(origin_r - 1, origin_c + i) for i in range(-1, length + 1)] + \
                [(origin_r + 1, origin_c + i) for i in range(-1, length + 1)] + \
                [(origin_r, origin_c - 1), (origin_r, origin_c + length)]
        else:
            boat_row_cols = [(origin_r + i, origin_c) for i in range(length)]
            surrounding_row_cols = \
                [(origin_r + i, origin_c - 1) for i in range(-1, length + 1)] + \
                [(origin_r + i, origin_c + 1) for i in range(-1, length + 1)] + \
                [(origin_r - 1, origin_c), (origin_r + length, origin_c)]

        if any((not 1 <= r <= Battl3ship.default_board_height)
               or (not 1 <= c <= Battl3ship.default_board_width)
               for r, c in boat_row_cols):
            raise ValueError("Cannot place boat here")

        surrounding_row_cols = [(r, c)
                                for r, c in surrounding_row_cols
                                if 1 <= r <= Battl3ship.default_board_height
                                and 1 <= c <= Battl3ship.default_board_width]

        return boat_row_cols, surrounding_row_cols

def test_random_generation():
    from matplotlib import pyplot as plt
    import numpy as np

    time_before = time.time()

    placement_count = 100

    boat_placement_count = np.zeros(
        (Battl3ship.default_board_height, Battl3ship.default_board_width))

    boat_placer = RandomBoatPlacer()

    for i in range(placement_count):
        if i % 10 == 0:
            print(".")
        boat_placement = boat_placer.get_random_placement()

        # board = Battl3ship.Board(Battl3ship.default_board_width, Battl3ship.default_board_height)
        # board.set_boats(boat_placement)
        # print(board)

        for boat_row_cols in boat_placement:
            for r, c in boat_row_cols:
                boat_placement_count[r - 1, c - 1] += 1
    print("")

    boat_placement_count /= placement_count

    total_time = time.time() - time_before
    print("[watch] Time/placement = {}".format(total_time / placement_count))

    plt.imshow(boat_placement_count)
    plt.savefig("distribution.png")

if __name__ == '__main__':
    test_random_generation()