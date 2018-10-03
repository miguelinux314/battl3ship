#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module to create training and test samples of Battl3ship games.

BoardDB contains a table of

Each data instance is a 10x10x2 tensor:
  * [r,c,0] contains a map of the turns in which the square at row=r, col=c has been shot.
    0 means the square has not been shot yet.
  * [r,c,1] contains a map of the result codes obtained at each position.
    See code_to_hits_sunks() and hits_sunks_to_code().


"""
__author__ = "Miguel Hernández Cabronero <mhernandez@deic.uab.cat>"
__date__ = "24/09/2018"

import sys
import os
import sqlite3
import numpy as np
import pickle
import multiprocessing
import itertools
import time

sys.path.append("..")
import generation
import game

# -------------------------- Begin configurable part

# Path to the board database file
base_board_db_path = "board_database.sq3"

# Be verbose?
be_verbose = True

base_board_table_name = "placements"


# -------------------------- End configurable part

class BoardDB:
    """Class to create, store and retrieve valid board layouts.
    """
    # Table of valid placements
    base_board_creation_query = f"""
        CREATE TABLE {base_board_table_name} (
         binary_map       TEXT     NOT NULL,
         rc_lists_pickle  TEXT     NOT NULL,
         CONSTRAINT unique_boards UNIQUE(binary_map)
        );"""
    base_board_insertion_query = f"""
        INSERT INTO {base_board_table_name} 
        (binary_map, rc_lists_pickle) VALUES (?, ?);"""
    base_board_count_query = f"SELECT COUNT(ALL) FROM {base_board_table_name};"

    def __init__(self):
        """Connect to the database, creating tables as necessary.
        """
        self.board_placer = generation.RandomBoatPlacer()
        try:
            self.conn = self._open_database(create_ok=not os.path.exists(base_board_db_path))
        except IOError as ex:
            raise IOError("Database seemed corrupted") from ex

    def insert_placement(self, boat_placement, commit=True):
        """Insert a placement in `base_board_table`. Its validity is not verified

        :raise ValueError: if the placement was already contained in the table
        """
        binary_map = self._placement_to_binary_map(boat_placement)
        rc_lists_str = pickle.dumps((sorted(boat_placement)))

        try:
            self.conn.execute(self.base_board_insertion_query, (binary_map, rc_lists_str))
        except sqlite3.IntegrityError as ex:
            raise ValueError("Duplicated board") from ex

        if commit:
            self.conn.commit()

    def count_placements(self):
        """Return the number of placements currently available in the DB.
        """
        cur = self.conn.execute(self.base_board_count_query)
        for r in cur:
            return int(r[0])

    def generate_placements(self, target_placement_count):
        """Generate random boat placements until the database contains at least
        `min_count` entries. If the database of placements contains at least
        that number of entries, this function does not add any additional ones.
        """
        current_count = self.count_placements()
        missing_placements = target_placement_count - current_count
        batch_size = 512

        with multiprocessing.Pool() as pool:
            while missing_placements > 0:
                time_before = time.time()
                new_placements = list(itertools.chain(*pool.imap_unordered(
                    func=BoardDB._get_placement_batch,
                    iterable=[batch_size for _ in range(os.cpu_count())],
                    chunksize=1)))

                new_placements = new_placements[:missing_placements]
                time_placement = time.time() - time_before

                time_before = time.time()
                discarded_placements = 0
                for placement in new_placements:
                    try:
                        self.insert_placement(boat_placement=placement, commit=False)
                    except ValueError:
                        discarded_placements += 1
                self.conn.commit()
                time_insert = time.time() - time_before

                if be_verbose:
                    print(f"Completed batch. Times: "
                          f"placement={time_placement}, "
                          f"insert={time_insert}, "
                          f"discarded={discarded_placements}, "
                          f"per board={(time_placement + time_insert) / (len(new_placements) - discarded_placements)}")
                    print(f"There are {board_db.count_placements()} placements"
                          f" ({100*board_db.count_placements()/target_placement_count}%)")

                missing_placements -= len(new_placements) - discarded_placements

    def binary_map_to_array(self, binary_map_str):
        """Return a zero-indexed binary array that represents all boat positions
        given a binary map stored in the database.
        """
        square_count = game.Battl3ship.default_board_height * game.Battl3ship.default_board_width
        assert len(binary_map_str) == square_count
        board = np.zeros(square_count, dtype=int)
        for i, c in enumerate(binary_map_str):
            board[i] = int(c)
        return board.reshape((game.Battl3ship.default_board_height, game.Battl3ship.default_board_width))

    @staticmethod
    def _get_placement_batch(batch_size: int):
        """Get a list of placements of length batch_size.
        """
        board_placer = generation.RandomBoatPlacer()
        return [board_placer.get_random_placement() for _ in range(batch_size)]

    def _placement_to_binary_map(self, boat_placement):
        """Translate a list of row,col lists into a string containing only 1 and 0
        representing the board state
        """
        board = np.zeros((game.Battl3ship.default_board_height + 1,
                          game.Battl3ship.default_board_width + 1),
                         dtype=int)
        for row_col_list in boat_placement:
            for row, col in row_col_list:
                board[row, col] = 1
        return "".join(f"{v}" for v in board[1:, 1:].flatten())

    def _open_database(self, create_ok=False):
        """Open the database and return a connection to it.

        :param create_ok: If not present, tables are created if create_ok is True, otherwise an IOError  is raised.

        :raise IOError: if tables do not exist but create_ok=False

        :return: a connection to the database
        """
        conn = sqlite3.connect(base_board_db_path)

        cur = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table';")
        existing_table_names = [r[0] for r in cur]

        # Table of valid placements
        if base_board_table_name not in existing_table_names:
            if not create_ok:
                raise IOError(f"{base_board_table_name} does not exist but create_ok is False")
            print(f"Creating {base_board_table_name}")
            conn.execute(self.base_board_creation_query)

        return conn


def __build_resultcode_dicts():
    """Create the result code to hit,sunk lists
    and the hit,sunk to result code data structures.

    * `code_to_hit_sunk_list` is a list indexed by result code,
      each entry being a tuple (hit_tuple, sunk_tuple).
        * The first one, `hit_tuple`, contains the lengths of the
          hit boats
        * The second one, `sunk_tuple`, contains the lengths of the
          sunk boats
      Any or both of the tuples can be empty.
      Repeated values can appear within and across the two tuples.
      Codes cover all possible shot results.

    * `hit_sunk_to_code_dict` is a dict indexed by `(hit_tuple, sink_tuple)`,
      with the semantics as defined for `code_to_hit_sunk_list`.
      Only valid (hit_tuple, sink_tuple) indices are available in the dictionary,
      that is, those contained as entries in `code_to_hit_sunk_list`.

    :return: code_to_hit_sunk_list, hit_sunk_to_code_dict
    """
    valid_lengths = list(game.Battl3ship.required_boat_count_by_length.keys())

    # Build all possible individual results for each shot
    # The format of each result is (is_hit, length).
    #   * If is_hit is False, it means the boat is sunk.
    #   * If length is 0, it means nothing was hit.
    assert 0 not in valid_lengths
    one_shot_results = [(is_hit, length)
                        for is_hit in [True, False]
                        for length in valid_lengths + [0]]

    # Build all 3-shot combinations
    three_shot_combinations = [(s1, s2, s3)
                               for s1 in one_shot_results
                               for s2 in one_shot_results
                               for s3 in one_shot_results]

    # Filter all invalid combinations and create the list of valid values
    valid_shots = []
    for shots in three_shot_combinations:
        try:
            # Boats of length 1 can only be sunk
            if any(s[0] and s[1] == 1 for s in shots):
                raise ValueError("Boats of length 1 can only be sunk")

            # To avoid duplicates, missed shots can only appear as "sunk"
            if any(s[0] and s[1] == 0 for s in shots):
                raise ValueError("Missed shots shall only appear as sunk to avoid duplicity.")

            # To avoid duplicates, length in shots can only appear in ascending order
            shot_lengths = [l for _, l in shots]
            if shot_lengths != sorted(shot_lengths):
                raise ValueError("Length in shots can only appear in ascending order")

            # Check that the number of boats of each type is
            # consistent with the maximum number of boats
            # that can be placed
            affected_boats_by_length = {
                length: sum(1 for s in shots if (s is not None and s[1] == length))
                for length in valid_lengths
            }
            for length, placed_boats in game.Battl3ship.required_boat_count_by_length.items():
                if affected_boats_by_length[length] > placed_boats:
                    raise ValueError(f"affected_boats_by_length = {affected_boats_by_length}"
                                     f" violates the maximum number of boats per length, "
                                     f" {game.Battl3ship.required_boat_count_by_length.items()}")

            # To avoid duplicates, hits of a given length cannot appear after sunks of that length
            for i in range(len(shots) - 1):
                if shots[i][1] == shots[i + 1][1] \
                        and (shots[i][0], shots[i + 1][0]) == (False, True):
                    raise ValueError("Hits cannot be reported after sunks")

            # The sample passes al tests, therefore it must be valid
            valid_shots.append(shots)
        except ValueError as ex:
            # print(f"Discarded {shots} because of: {ex}")
            pass
    valid_shots = sorted(valid_shots)

    # code_to_hit_sunk_list, hit_sunk_to_code_dict can now be generated
    code_to_hit_sunk_list = []
    hit_sunk_to_code_dict = {}
    for valid_shot in valid_shots:
        hit_tuple = tuple(length
                          for is_hit, length in valid_shot
                          if length != 0 and is_hit)
        sunk_tuple = tuple(length
                           for is_hit, length in valid_shot
                           if length != 0 and not is_hit)

        hit_sunk_to_code_dict[(hit_tuple, sunk_tuple)] = len(code_to_hit_sunk_list)
        code_to_hit_sunk_list.append((hit_tuple, sunk_tuple))

    for code in range(len(code_to_hit_sunk_list)):
        assert hit_sunk_to_code_dict[code_to_hit_sunk_list[code]] == code
    for h_s_lists, code in hit_sunk_to_code_dict.items():
        assert code_to_hit_sunk_list[code] == h_s_lists

    return code_to_hit_sunk_list, hit_sunk_to_code_dict


if __name__ == '__main__':
    # board_db = BoardDB()
    # boat_placer = generation.RandomBoatPlacer()
    # board_db.generate_placements(int(1e5))

    print("[watch] len(code_to_hit_sunk_list) = {}".format(len(code_to_hit_sunk_list)))
