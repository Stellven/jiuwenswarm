"""Authoring record for heldout/cases-trap.json (8 spec-trap cases, a separate frozen case set).

Order of work for every case: (1) the spec, with one rule that a model is likely to misread or default wrongly;
(2) the reference implementation in reference_trap.py; (3) the tests. Every expected value below was worked out by
hand from the spec sentence; reference_trap.py must agree with all of them (asserted in test_heldout.py).

Two disjoint suites per case, both exercising the trap rule on DIFFERENT inputs:
  gate   4 tests: what the CC arm's check runs and may quote in its retry.
  score  6 to 10 tests: never shown to any arm and never used by any check; the final pass or fail is decided here.

Honest limit: one author wrote the spec, the reference, the gate and the score suite. The gate is independent of the
WORKER (it was fixed before any model call and never sees the worker's reading), not of the case author.

  python author_trap_cases.py --out DIR     writes DIR/cases-trap.json (then `run_heldout.py freeze --cases cases-trap.json`)
"""
import argparse
import json
from pathlib import Path


def T(args, expect=None, raises=None):
    return {'args': args, 'raises': raises} if raises else {'args': args, 'expect': expect}


CASES = []


def add(cid, trap, spec, examples, gate, score):
    CASES.append(dict(id=cid, function=cid, trap=trap, spec=spec, examples=examples, gate=gate, score=score))


# 1. optional separator: the number and the unit may touch.
add('parse_size', 'separator between number and unit is optional (zero or more spaces)',
    "parse_size(s) converts a size string to a number of bytes (int). The string is a non-negative integer written with digits 0-9, then zero or more space characters, then one unit: B, KB, MB or GB (uppercase only). Leading and trailing spaces are allowed. 1 KB is 1024 B, 1 MB is 1024 KB, 1 GB is 1024 MB. Raise ValueError for anything else: an empty string, a number with no unit, a unit with no number, an unknown unit, a lowercase unit, a sign, or a fractional number.",
    ["parse_size('3 B') == 3", "parse_size('2 KB') == 2048"],
    [T(['1KB'], 1024), T(['2 MB'], 2097152), T(['5B'], 5), T(['12'], raises='ValueError')],
    [T(['3GB'], 3221225472), T(['10  KB'], 10240), T([' 7MB '], 7340032), T(['0B'], 0), T(['1kb'], raises='ValueError'),
     T(['1.5KB'], raises='ValueError'), T([''], raises='ValueError'), T(['4 TB'], raises='ValueError'), T(['KB'], raises='ValueError'),
     T(['-1KB'], raises='ValueError')])

# 2. inclusive vs exclusive bounds: every bin is half-open except the last, which is closed.
add('bucket_counts', 'the last bin includes its upper edge; all other bins exclude theirs',
    "bucket_counts(values, edges) counts numbers into bins. edges is a strictly increasing list of at least 2 numbers e0 < e1 < ... < en. There are n bins. Bin i covers e_i <= v < e_(i+1) (lower edge included, upper edge excluded), except the LAST bin, which also includes its upper edge: e_(n-1) <= v <= e_n. A value below e0 or above e_n is ignored. Return a list of n integer counts, one per bin, in order.",
    ["bucket_counts([1], [0, 5, 10]) == [1, 0]", "bucket_counts([7, 8], [0, 5, 10]) == [0, 2]"],
    [T([[1, 2, 3], [0, 2, 4]], [1, 2]), T([[4], [0, 2, 4]], [0, 1]), T([[], [0, 1]], [0]), T([[-1, 5], [0, 2, 4]], [0, 0])],
    [T([[0, 5, 10], [0, 5, 10]], [1, 2]), T([[10, 10, 9.5], [0, 5, 10]], [0, 3]), T([[3, 3, 3], [3, 6, 9, 12]], [3, 0, 0]),
     T([[6, 9, 12], [3, 6, 9, 12]], [0, 1, 2]), T([[1], [0, 1]], [1]), T([[12.0001, 2.9999], [3, 6, 9, 12]], [0, 0, 0]),
     T([[5.999, 6, 6.001], [3, 6, 9, 12]], [1, 2, 0])])

# 3. ties: equal scores share one rank and the next rank skips.
add('competition_rank', 'tied scores share the lowest rank number and the next rank skips ahead (1, 2, 2, 4)',
    "competition_rank(scores) returns the rank of every score, in input order, as a list of ints. The highest score has rank 1. The rank of a score is 1 plus the number of scores in the list that are strictly greater than it. So equal scores get the same rank, and the rank after a tie skips ahead. An empty list gives an empty list.",
    ["competition_rank([10, 30, 20]) == [3, 1, 2]", "competition_rank([4]) == [1]"],
    [T([[10, 20, 30]], [3, 2, 1]), T([[5, 5, 3]], [1, 1, 3]), T([[]], []), T([[7]], [1])],
    [T([[3, 5, 5, 5, 1]], [4, 1, 1, 1, 5]), T([[1, 1, 1]], [1, 1, 1]), T([[9, 8, 8, 7, 7, 7, 1]], [1, 2, 2, 4, 4, 4, 7]),
     T([[2, 2, 1, 1]], [1, 1, 3, 3]), T([[-1, -1, 0]], [2, 2, 1]), T([[1.5, 1.5, 2]], [2, 2, 1]), T([[4, 3, 3, 2]], [1, 2, 2, 4])])

# 4. empty input with a defined result that differs from the library default (all([]) is True).
add('consistent_groups', 'an empty list is NOT consistent (all([]) would say True) and zero breaks the sign',
    "consistent_groups(groups) takes a dict that maps a name to a list of numbers and returns the sorted list of names whose list is consistent. A list is consistent when it is not empty and either every number in it is strictly greater than 0 or every number in it is strictly less than 0. Zero is neither positive nor negative, so a list that contains a zero is not consistent. An empty list is not consistent. An empty dict gives an empty list.",
    ["consistent_groups({'a': [4, 9]}) == ['a']", "consistent_groups({'a': [3, -3]}) == []"],
    [T([{'a': [1, 2], 'b': []}], ['a']), T([{'p': [-1], 'q': [1, -1]}], ['p']), T([{'m': [3, 4], 'n': [-3, -4]}], ['m', 'n']), T([{}], [])],
    [T([{'x': [], 'y': [-1], 'z': [0]}], ['y']), T([{'a': [], 'b': []}], []), T([{'k': [1, 0, 2]}], []), T([{'k': [0.5, 2], 'j': []}], ['k']),
     T([{'u': [-2, -0.1], 'v': [5], 'w': []}], ['u', 'v']), T([{'b': [1], 'a': [2]}], ['a', 'b']), T([{'e': []}], []),
     T([{'n': [-1, -1, 1], 'o': [-9]}], ['o'])])

# 5. Unicode: NFKC then full case folding, then whitespace removal.
add('is_anagram', 'strings are compared after NFKC normalization and full case folding (casefold), not lower()',
    "is_anagram(a, b) returns True when two strings use the same characters the same number of times after this normalization, applied to each string in this order: (1) Unicode NFKC normalization (unicodedata.normalize('NFKC', ...)); (2) full case folding as done by Python str.casefold(), so 'ß' becomes 'ss'; (3) removal of every character for which str.isspace() is True. Order does not matter, only the count of each character. Return a bool.",
    ["is_anagram('Dusty', 'study') == True", "is_anagram('abc', 'abcd') == False"],
    [T(['listen', 'Silent'], True), T(['Straße', 'ESSTRAS'], True), T(['abc', 'abd'], False), T(['a b', 'ba'], True)],
    [T(['ﬁsh', 'HSIF'], True), T(['Maße', 'ssame'], True), T(['ς', 'Σ'], True), T(['１２３', '321'], True),
     T(['ab', 'ABc'], False), T(['x y', 'yx'], True), T(['ss', 'ß'], True), T(['straße', 'strase'], False),
     T(['é', 'é'], True)])

# 6. rounding mode: half to even on the exact decimal value.
add('to_cents', "ties round half to EVEN (banker's rounding), on the exact decimal, not half up",
    "to_cents(amount) takes a money amount written as a decimal string: an optional leading '-', one or more digits, and optionally a '.' followed by one or more digits (for example '12', '-0.5', '3.14159'). It returns the amount in cents as an int: amount times 100, rounded to the nearest integer. When the value is exactly halfway between two integers it rounds to the even one (round half to even, so 2.5 -> 2 and 3.5 -> 4 and -2.5 -> -2). Work on the exact decimal value, not on a binary float. Zero is returned as 0.",
    ["to_cents('1.23') == 123", "to_cents('-0.5') == -50"],
    [T(['1.005'], 100), T(['2.50'], 250), T(['0.015'], 2), T(['12'], 1200)],
    [T(['0.025'], 2), T(['0.035'], 4), T(['-0.125'], -12), T(['-0.135'], -14), T(['2.675'], 268), T(['0.004'], 0), T(['-0.004'], 0),
     T(['0.0051'], 1), T(['100.995'], 10100)])

# 7. sign handling: a result that is zero after formatting never carries a sign.
add('format_delta', 'a value that formats as zero (including -0.0 and -0.04) is "0.0" with no sign',
    "format_delta(x) takes a float and returns a string for display. Format x with one digit after the decimal point exactly as Python's '%.1f' % x does. If the formatted number is not zero, a positive number is written with a leading '+' and a negative number keeps its '-'. If the formatted number is zero (this includes '-0.0', which arises from -0.0 and from small negative values such as -0.04), return '0.0' with no sign at all.",
    ["format_delta(2.25) == '+2.2'", "format_delta(-7.5) == '-7.5'"],
    [T([1.5], '+1.5'), T([-2.0], '-2.0'), T([0.0], '0.0'), T([-0.04], '0.0')],
    [T([-0.0], '0.0'), T([0.04], '0.0'), T([0.06], '+0.1'), T([-0.06], '-0.1'), T([-0.049], '0.0'), T([10.0], '+10.0'),
     T([100.04], '+100.0'), T([-100.04], '-100.0')])

# 8. duplicates: only runs of consecutive equal items collapse; later equal items are kept.
add('collapse_adjacent', 'only ADJACENT equal items collapse; equal items that are apart are all kept',
    "collapse_adjacent(items) takes a list and returns a new list in which every run of consecutive equal items (compared with ==) is replaced by a single copy of that item. Equal items that are not next to each other are NOT removed. Order is kept. An empty list gives an empty list.",
    ["collapse_adjacent([3, 3]) == [3]", "collapse_adjacent(['p', 'q']) == ['p', 'q']"],
    [T([[1, 1, 2]], [1, 2]), T([[1, 2, 1]], [1, 2, 1]), T([[]], []), T([['a', 'a', 'a']], ['a'])],
    [T([['a', 'b', 'a', 'a']], ['a', 'b', 'a']), T([[1, 1, 2, 2, 1, 1]], [1, 2, 1]), T([[None, None]], [None]), T([['x']], ['x']),
     T([[[1], [1], [2]]], [[1], [2]]), T([['a', 'A', 'a']], ['a', 'A', 'a']), T([[0, 0, 0, 1, 0]], [0, 1, 0]), T([['', '', ' ']], ['', ' '])])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'cases-trap.json').write_bytes((json.dumps(CASES, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    print('wrote', args.out / 'cases-trap.json', len(CASES), 'cases')


if __name__ == '__main__':
    main()
