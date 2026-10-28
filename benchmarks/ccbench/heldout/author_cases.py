"""Authoring record for heldout/cases.json (the frozen gold). Run once; then `run_heldout.py freeze`.

Every expected value below was worked out by hand from the spec sentence, before any model call and before the
bench's check or retry code existed. reference.py (a separate implementation) must agree with all of them; that
is asserted in test_heldout.py. Two disjoint suites per case: `gate` (what the CC arm's held-out check runs and
may show in a retry) and `score` (never shown to any arm; the final pass/fail is decided on it).

  python author_cases.py --out DIR      writes DIR/cases.json (copy it over cases.json only to author a new version)
"""
import argparse
import json
from pathlib import Path


def T(args, expect=None, raises=None):
    return {'args': args, 'raises': raises} if raises else {'args': args, 'expect': expect}


CASES = []


def add(cid, spec, examples, gate, score):
    CASES.append(dict(id=cid, function=cid, spec=spec, examples=examples, gate=gate, score=score))


add('merge_intervals',
    "merge_intervals(intervals) takes a list of [start, end] integer pairs (start <= end) in any order and returns the merged list sorted by start. Intervals that overlap or merely touch (one ends exactly where the next starts) are merged into one. Return a list of [start, end] lists. An empty input gives an empty list.",
    ["merge_intervals([[1, 4], [6, 8]]) == [[1, 4], [6, 8]]", "merge_intervals([[1, 5], [2, 3]]) == [[1, 5]]"],
    [T([[[1, 3], [2, 6], [8, 10]]], [[1, 6], [8, 10]]), T([[[1, 2], [2, 3]]], [[1, 3]]), T([[]], []), T([[[5, 7], [1, 2]]], [[1, 2], [5, 7]])],
    [T([[[1, 4], [0, 4]]], [[0, 4]]), T([[[1, 10], [2, 3], [4, 5]]], [[1, 10]]), T([[[1, 2], [3, 4]]], [[1, 2], [3, 4]]),
     T([[[3, 3], [1, 1], [3, 5]]], [[1, 1], [3, 5]]), T([[[-5, -1], [-2, 2]]], [[-5, 2]]), T([[[2, 3], [4, 5], [6, 7], [1, 10]]], [[1, 10]])])

add('compare_versions',
    "compare_versions(a, b) compares two dotted version strings made of non-negative integer parts, such as '1.2.10'. Parts are compared as integers from left to right. A missing trailing part counts as 0, so '1.0' equals '1.0.0'. Leading zeros do not matter. Return -1 if a < b, 0 if equal, 1 if a > b.",
    ["compare_versions('1.2', '1.3') == -1", "compare_versions('2.0', '2.0') == 0"],
    [T(['1.2.3', '1.2.4'], -1), T(['1.0', '1.0.0'], 0), T(['1.10', '1.9'], 1), T(['2', '1.9.9'], 1)],
    [T(['1.0.0.0', '1'], 0), T(['0.9', '0.10'], -1), T(['1.02', '1.2'], 0), T(['10.0', '9.99.99'], 1), T(['1.0.1', '1'], 1), T(['3.4', '3.4.0.0.1'], -1)])

add('round_half_up',
    "round_half_up(value, ndigits) takes a decimal number written as a string (for example '-2.345') and an integer ndigits >= 0. It rounds to ndigits places with ties rounded away from zero (2.5 -> 3, -2.5 -> -3) and works on the exact decimal value, not on a binary float. It returns a string with exactly ndigits digits after the decimal point, and no decimal point when ndigits is 0. A result that is zero is never written with a minus sign.",
    ["round_half_up('1.234', 2) == '1.23'", "round_half_up('0.5', 0) == '1'"],
    [T(['2.5', 0], '3'), T(['2.345', 2], '2.35'), T(['-2.5', 0], '-3'), T(['1', 2], '1.00')],
    [T(['0.125', 2], '0.13'), T(['-0.125', 2], '-0.13'), T(['1.005', 2], '1.01'), T(['0.4', 0], '0'), T(['-0.4', 0], '0'),
     T(['999.995', 2], '1000.00'), T(['12.3456', 3], '12.346'), T(['2.675', 2], '2.68')])

add('rle_decode',
    "rle_decode(s) decodes a run-length string. The input has lowercase letters a-z and decimal digits. A letter may be preceded by a decimal count of any length (the full run of digits right before it); the letter is then repeated that many times. A letter with no count is repeated once. A count of 0 produces nothing for that letter. The count applies only to the single letter after it. Return the decoded string. The input never ends with digits.",
    ["rle_decode('2a') == 'aa'", "rle_decode('b2c') == 'bcc'"],
    [T(['3a2b'], 'aaabb'), T(['abc'], 'abc'), T(['12x'], 'x' * 12), T(['a3b'], 'abbb')],
    [T([''], ''), T(['10a1b'], 'a' * 10 + 'b'), T(['0a2b'], 'bb'), T(['2ab'], 'aab'), T(['1a1b1c'], 'abc'), T(['11z'], 'z' * 11), T(['z2y'], 'zyy')])

add('business_days',
    "business_days(start, end, holidays) counts business days in the half-open range [start, end): start is included, end is excluded. start and end are ISO dates 'YYYY-MM-DD'. A business day is Monday to Friday and not in holidays (a list of ISO date strings, possibly with duplicates, possibly on weekends or outside the range). If end <= start the result is 0. Return an int.",
    ["business_days('2024-01-01', '2024-01-02', []) == 1  # 2024-01-01 is a Monday", "business_days('2024-01-05', '2024-01-08', []) == 1"],
    [T(['2024-01-01', '2024-01-08', []], 5), T(['2024-01-06', '2024-01-08', []], 0), T(['2024-01-01', '2024-01-08', ['2024-01-03']], 4), T(['2024-01-08', '2024-01-01', []], 0)],
    [T(['2024-01-01', '2024-01-02', []], 1), T(['2024-01-01', '2024-02-01', []], 23), T(['2024-01-01', '2024-01-08', ['2024-01-06', '2024-01-06']], 5),
     T(['2024-01-01', '2024-01-08', ['2024-01-08']], 5), T(['2024-01-03', '2024-01-03', []], 0), T(['2024-02-26', '2024-03-04', ['2024-02-29', '2024-02-29']], 4),
     T(['2023-12-29', '2024-01-02', []], 2), T(['2024-01-01', '2024-01-08', ['2024-01-01', '2024-01-02']], 3)])

add('top_k_words',
    "top_k_words(text, k) returns the k most frequent words as a list of [word, count] lists. Lowercase the text. A word is a maximal run of the characters a-z and the apostrophe ('); every other character separates words. Strip apostrophes from both ends of each word, and drop words that become empty. Sort by count descending, then by word ascending (alphabetical). If there are fewer than k distinct words return all of them. k = 0 gives an empty list.",
    ["top_k_words('a b a', 2) == [['a', 2], ['b', 1]]", "top_k_words('Hi hi.', 1) == [['hi', 2]]"],
    [T(['a b a', 1], [['a', 2]]), T(['The the THE cat', 2], [['the', 3], ['cat', 1]]), T(['b a b a c', 3], [['a', 2], ['b', 2], ['c', 1]]), T(['', 3], [])],
    [T(["Don't stop, don't!", 1], [["don't", 2]]), T(["'tis 'tis ok", 2], [['tis', 2], ['ok', 1]]), T(['a-b a_b', 5], [['a', 2], ['b', 2]]),
     T(['x y z', 0], []), T(['one two', 10], [['one', 1], ['two', 1]]), T(["It's it's IT'S its", 2], [["it's", 3], ['its', 1]]), T(["''' a", 1], [['a', 1]])])

add('wrap_text',
    "wrap_text(text, width) splits text into lines by greedy word wrapping. Words are separated by any whitespace; collapse all whitespace so words in a line are joined by a single space and no line has leading or trailing spaces. Put as many words on a line as fit within width characters. A word longer than width goes on a line of its own and is not broken. Return a list of lines. Empty or all-whitespace text gives an empty list.",
    ["wrap_text('aa bb cc', 5) == ['aa bb', 'cc']", "wrap_text('abcdefgh', 3) == ['abcdefgh']"],
    [T(['aaa bbb ccc', 7], ['aaa bbb', 'ccc']), T(['hello world', 5], ['hello', 'world']), T(['', 10], []), T(['a  b\n c', 10], ['a b c'])],
    [T(['aaa bbb ccc', 8], ['aaa bbb', 'ccc']), T(['abcdefghij kl', 4], ['abcdefghij', 'kl']), T(['a b c d e', 3], ['a b', 'c d', 'e']),
     T(['ab cd ef', 5], ['ab cd', 'ef']), T(['xx yy', 4], ['xx', 'yy']), T(['  lead and trail  ', 20], ['lead and trail']),
     T(['aaaa bb cc', 4], ['aaaa', 'bb', 'cc']), T(['a bb ccc dddd', 6], ['a bb', 'ccc', 'dddd'])])

add('parse_duration',
    "parse_duration(s) converts a duration string to total seconds (int). The string has one or more terms, each a non-negative integer followed by one unit letter: d (86400 s), h (3600 s), m (60 s), s (1 s). Terms may appear in any order and may be separated by spaces; leading and trailing spaces are allowed. Each unit may appear at most once. Raise ValueError for anything else: an empty string, a number with no unit, an unknown unit, a repeated unit, a sign, or a fractional number.",
    ["parse_duration('2m') == 120", "parse_duration('1h 1s') == 3601"],
    [T(['1h30m'], 5400), T(['90s'], 90), T(['2d'], 172800), T([''], raises='ValueError')],
    [T(['1d 1h 1m 1s'], 90061), T(['30m1h'], 5400), T(['1h1h'], raises='ValueError'), T(['90'], raises='ValueError'), T(['1.5h'], raises='ValueError'),
     T(['0s'], 0), T(['5x'], raises='ValueError'), T(['-1s'], raises='ValueError'), T([' 2m '], 120), T(['100h'], 360000)])

add('dedupe_records',
    "dedupe_records(records, key) removes duplicate records from a list of dicts. Two records are duplicates when both have the field `key` and the values are equal (1 and '1' are different values; None equals None). For each group of duplicates the result keeps one record: the content of the LAST record of the group, placed at the position where the FIRST record of the group appeared. Records that lack the field `key` are never duplicates of anything and are all kept in place. Return a new list.",
    ["dedupe_records([{'id': 1, 'v': 'a'}, {'id': 1, 'v': 'b'}], 'id') == [{'id': 1, 'v': 'b'}]", "dedupe_records([], 'id') == []"],
    [T([[{'id': 1, 'v': 'a'}, {'id': 2, 'v': 'b'}, {'id': 1, 'v': 'c'}], 'id'], [{'id': 1, 'v': 'c'}, {'id': 2, 'v': 'b'}]), T([[], 'id'], []), T([[{'id': 1}], 'id'], [{'id': 1}]),
     T([[{'k': 'x', 'n': 1}, {'k': 'x', 'n': 2}, {'k': 'x', 'n': 3}], 'k'], [{'k': 'x', 'n': 3}])],
    [T([[{'id': 2, 'v': 1}, {'id': 1, 'v': 2}, {'id': 2, 'v': 3}, {'id': 1, 'v': 4}], 'id'], [{'id': 2, 'v': 3}, {'id': 1, 'v': 4}]),
     T([[{'id': 1, 'v': 'a'}, {'id': '1', 'v': 'b'}], 'id'], [{'id': 1, 'v': 'a'}, {'id': '1', 'v': 'b'}]),
     T([[{'v': 1}, {'v': 2}, {'id': 1, 'v': 3}], 'id'], [{'v': 1}, {'v': 2}, {'id': 1, 'v': 3}]),
     T([[{'id': None, 'v': 1}, {'id': None, 'v': 2}], 'id'], [{'id': None, 'v': 2}]),
     T([[{'a': 1, 'b': 1}, {'a': 1, 'b': 2}, {'a': 2, 'b': 3}, {'a': 1, 'b': 4}], 'a'], [{'a': 1, 'b': 4}, {'a': 2, 'b': 3}]),
     T([[{'id': 1}, {'id': 1}], 'id'], [{'id': 1}])])

add('brackets_balanced',
    "brackets_balanced(s) returns True when the round, square and curly brackets in s are balanced and correctly nested, otherwise False. All other characters are ignored. Text inside double quotes is a string literal: brackets in it are ignored. Inside a string literal a backslash escapes the next character (so a backslash followed by a double quote does not end the string). A string literal that is never closed makes the result False. Single quotes have no special meaning.",
    ["brackets_balanced('([])') == True", "brackets_balanced('(]') == False"],
    [T(['([]{})'], True), T(['(]'], False), T([''], True), T(['(('], False)],
    [T(['("(")'], True), T(['"abc'], False), T(['("\\")")'], True), T(['a(b)c]'], False), T(['{[()]}('], False), T([')('], False), T(['")"'], True),
     T(['x = f(a[1], {k: "}"})'], True)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'cases.json').write_bytes((json.dumps(CASES, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    print('wrote', args.out / 'cases.json', len(CASES), 'cases')


if __name__ == '__main__':
    main()
