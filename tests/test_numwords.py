"""Numbers written as words, read the same way by the rules and the AI quote check."""

import pytest

from second_opinion.numwords import fraction_amounts, number_value, word_numbers


@pytest.mark.parametrize("text, value", [
    ("seven", 7), ("Twelve", 12), ("ninety-seven", 97), ("fifty eight", 58), ("twenty-one", 21),
    ("eleven hundred", 1100), ("a hundred and thirty-nine", 139), ("one hundred", 100),
    ("one thousand two hundred and forty-seven", 1247), ("nine hundred and ninety-nine", 999),
    ("a dozen", 12), ("five dozen", 60), ("two thousand", 2000), ("a thousand", 1000), ("zero", 0),
])
def test_number_value_reads_a_whole_phrase(text, value):
    assert number_value(text) == value


@pytest.mark.parametrize("text", ["", "a", "and", "one two", "hundred and", "dozen dozen", "tumours"])
def test_number_value_is_none_for_anything_else(text):
    assert number_value(text) is None


def test_word_numbers_finds_the_longest_phrases_with_their_place():
    text = "Nearly eleven hundred tumours, a hundred and thirty-nine normals and ninety-seven others."
    found = [(text[n.start:n.end], n.value) for n in word_numbers(text)]
    assert found == [("eleven hundred", 1100), ("a hundred and thirty-nine", 139), ("ninety-seven", 97)]


def test_word_numbers_leaves_the_article_and_and_outside_a_number():
    text = "A tumour and a sample, and one in six, and barely a dozen men."
    found = [(text[n.start:n.end], n.value) for n in word_numbers(text)]
    assert found == [("one", 1), ("six", 6), ("a dozen", 12)]


def test_word_numbers_does_not_read_inside_other_words():
    assert word_numbers("Someone often attended; tenfold, eighteenth, nonetheless.") == []


@pytest.mark.parametrize("text, percent", [
    ("one in six", 100 / 6), ("one in fifteen", 100 / 15), ("Nine in every hundred", 9.0),
    ("one tumour in eight", 12.5), ("two out of three", 200 / 3), ("1 in 4", 25.0), ("one patient in twenty", 5.0),
])
def test_fraction_amounts(text, percent):
    [found] = fraction_amounts(text)
    assert found.value == pytest.approx(percent)
    assert (found.start, found.end) == (0, len(text))


@pytest.mark.parametrize("text", ["5 in 1,000 samples", "seven in six", "one in a million chances", "one of the six"])
def test_fraction_amounts_skips_counts_and_impossible_shares(text):
    assert fraction_amounts(text) == []
