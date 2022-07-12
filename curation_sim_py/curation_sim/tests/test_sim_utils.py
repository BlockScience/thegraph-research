import unittest

from curation_sim.sim_utils import snake_to_camel


class TestSnakeToCamel(unittest.TestCase):

    def test_snake_to_camel(self):
        word0 = "word"
        self.assertEqual(snake_to_camel(word0), "word")
        self.assertEqual(snake_to_camel(word0.upper()), "word")

        word1 = "WORD_ONE"
        self.assertEqual(snake_to_camel(word1), "wordOne")

        word2 = "these_two_words"
        self.assertEqual(snake_to_camel(word2), "theseTwoWords")
