import unittest

import numpy as np

from curation_sim.sim_utils import snake_to_camel, get_stakers


class TestSnakeToCamel(unittest.TestCase):

    def test_snake_to_camel(self):
        word0 = "word"
        self.assertEqual(snake_to_camel(word0), "word")
        self.assertEqual(snake_to_camel(word0.upper()), "word")

        word1 = "WORD_ONE"
        self.assertEqual(snake_to_camel(word1), "wordOne")

        word2 = "these_two_words"
        self.assertEqual(snake_to_camel(word2), "theseTwoWords")


class TestGetStakers(unittest.TestCase):

    def test_get_stakers(self):
        stakers = get_stakers(10, 100, 1)

        self.assertEqual([i[0] for i in stakers],
                         [f'curator{i}' for i in range(10)])

        vals = [i[1] for i in stakers]

        self.assertTrue(np.isclose(sum(vals) / 10, 100, atol=2))
        self.assertTrue(np.isclose(np.std(vals), 1, .5))

    def test_zeros(self):
        st = get_stakers(10, 0, 0)
        self.assertEqual(st, [(f'curator{i}', 0) for i in range(10)])
