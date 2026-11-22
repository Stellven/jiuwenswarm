"""Offline tests of the pinned benchmark inputs and scoring boundary."""
import copy
import json

import pytest

from jiuwenswarm.factory import benchmark_data as bd


def question(identity='one'):
    return dict(id=identity, question='Which object is hot?',
                choices=dict(label=['1', '2', '3', '4', '5'],
                             text=['ice', 'snow', 'steam', 'frost', 'hail']), answerKey='3')


def test_sample_is_order_independent_and_seeded():
    rows = [question(str(i)) for i in range(30)]
    selected = bd.select_rows(rows, 12)
    assert selected == bd.select_rows(list(reversed(rows)), 12)
    assert selected != bd.select_rows(rows, 12, seed=43)
    assert len({row['id'] for row in selected}) == 12
    for count in (0, 31, True):
        with pytest.raises(ValueError):
            bd.select_rows(rows, count)
    with pytest.raises(ValueError):
        bd.select_rows([rows[0], rows[0]], 1)


def test_ground_truth_does_not_enter_prompt_and_numeric_choices_map_to_letters():
    row = question()
    allowed, expected, choices = bd.normalize_question(row)
    assert allowed == list('ABCDE') and expected == 'C'
    assert choices[2] == ('C', 'steam')
    prompt = bd.quality_prompt(row)
    row['answerKey'] = '1'
    assert bd.quality_prompt(row) == prompt
    assert prompt.startswith(bd.CHAT_PREFIX) and prompt.endswith(bd.CHAT_SUFFIX)
    assert 'E. hail' in prompt
    row['answerKey'] = 'absent'
    with pytest.raises(ValueError):
        bd.normalize_question(row)
    row = question()
    row['choices']['label'][1] = '1'
    with pytest.raises(ValueError):
        bd.normalize_question(row)


@pytest.mark.parametrize('text,answer', [('A', 'A'), (' a.\n', 'A'), ('C)', 'C'),
    ('B because it is hot', None), ('Answer: B', None), ('A or B', None),
    ('<think>A</think>B', None), ('', None), ('1', None), ('E', None)])
def test_strict_answer_extraction(text, answer):
    assert bd.extract_answer(text, 'ABCD') == answer


class CharacterTokenizer:
    special_ids = {'bos': 0, 'eos': 1}

    def encode(self, text, parse_special=True):
        return [ord(char) + 2 for char in text]

    def decode(self, ids):
        return ''.join(chr(token - 2) for token in ids)


def test_decoder_stops_at_eos_and_strips_only_known_leading_bos():
    tokenizer = CharacterTokenizer()
    assert bd.decode_answer([0, *tokenizer.encode(' C.'), 1, *tokenizer.encode('D')], tokenizer) == {
        'text': ' C.', 'answer': 'C'}
    assert bd.decode_answer(tokenizer.encode('<think>A</think>B'), tokenizer)['answer'] is None
    with pytest.raises(ValueError):
        bd.decode_answer([True], tokenizer)
    with pytest.raises(ValueError):
        bd.decode_answer([-1], tokenizer)


def page(rows):
    return dict(partial=False, num_rows_total=len(rows), rows=[
        dict(row_idx=index, row=row, truncated_cells=[]) for index, row in enumerate(rows)])


def install_download(monkeypatch, document, revision=bd.REVISION):
    calls = []
    def download(url):
        calls.append(url)
        return bd.canonical(document), {'Content-Type': 'application/json'}, revision
    monkeypatch.setattr(bd, '_download', download)
    return calls


def test_fetch_retains_verified_bytes_reuses_cache_and_detects_tampering(tmp_path, monkeypatch):
    rows = [question('one'), question('two')]
    calls = install_download(monkeypatch, page(rows))
    actual, provenance = bd.fetch_split(tmp_path, 'test')
    assert actual == rows and provenance['total_rows'] == 2
    assert provenance['canonical_rows_sha256'] == bd.digest(bd.canonical(rows))
    assert len(calls) == 1
    assert bd.fetch_split(tmp_path, 'test')[0] == rows and len(calls) == 1
    (tmp_path / 'test-0000.json').write_bytes(b'{}')
    with pytest.raises(ValueError, match='identity differs'):
        bd.fetch_split(tmp_path, 'test')


@pytest.mark.parametrize('failure', ['revision', 'partial', 'truncated', 'index', 'duplicate', 'count'])
def test_fetch_rejects_incomplete_or_unpinned_source(tmp_path, monkeypatch, failure):
    document = page([question('one'), question('two')])
    revision = bd.REVISION
    if failure == 'revision': revision = 'different'
    elif failure == 'partial': document['partial'] = True
    elif failure == 'truncated': document['rows'][0]['truncated_cells'] = ['question']
    elif failure == 'index': document['rows'][0]['row_idx'] = 99
    elif failure == 'duplicate': document['rows'][1]['row']['id'] = 'one'
    elif failure == 'count': document['num_rows_total'] = 3
    install_download(monkeypatch, document, revision)
    with pytest.raises(ValueError):
        bd.fetch_split(tmp_path, 'test')


def test_quality_case_retains_ground_truth_separate_from_wire_prompt():
    row = question()
    tokenizer = CharacterTokenizer()
    case = bd.make_quality_case(row, tokenizer, 'test')
    assert case['ids'] == tokenizer.encode(case['prompt'])
    assert case['max_new_tokens'] == 8 and case['expected_letter'] == 'C'
    assert case['allowed_letters'] == list('ABCDE')
    changed = copy.deepcopy(row)
    changed['answerKey'] = '5'
    assert bd.make_quality_case(changed, tokenizer, 'test')['ids'] == case['ids']


def test_speed_is_four_identical_complete_512_token_chats_with_one_warmup():
    cases = bd.make_speed_cases(CharacterTokenizer(), 'a bb ccc dddd ' * 200)
    assert [case['phase'] for case in cases] == ['warmup', 'measured', 'measured', 'measured']
    assert len({tuple(case['ids']) for case in cases}) == 1
    assert len({case['id'] for case in cases}) == 4
    for case in cases:
        assert len(case['ids']) == 512 and case['max_new_tokens'] == 128
        assert case['prompt'].startswith(bd.CHAT_PREFIX)
        assert case['prompt'].endswith(bd.CHAT_SUFFIX)
        assert 'at least 500 words' in case['prompt']


def test_decode_only_byte_mapping_and_special_literals():
    decoder=bd.DecodeOnlyTokenizer({'A':0,'Ġ':1,'Ã©':2,'<｜User｜>':3},[1,1,1,3],{'bos':3})
    assert decoder.decode([0,1,2,3])=='A é<｜User｜>'
    assert bd.decode_answer([3,0],decoder,'AB',eos_id=99)=={'text':'A','answer':'A'}
    for bad in (-1,4,True,'0'):
        with pytest.raises(ValueError):decoder.decode([bad])


@pytest.mark.parametrize('vocab,types', [({'A':1},[1]),({'A':0},[]),({},[])])
def test_decode_only_rejects_malformed_vocabulary(vocab,types):
    with pytest.raises(ValueError):bd.DecodeOnlyTokenizer(vocab,types)


def test_decoder_requires_all_frozen_table_identities(tmp_path,monkeypatch):
    monkeypatch.setattr(bd,'PACK',tmp_path)
    directory=tmp_path/'tokenizer';directory.mkdir()
    for name,value in [('vocab.json',{'A':0}),('token_type.json',[1]),('tokenizer.json',{'special_ids':{}})]:
        (directory/name).write_text(json.dumps(value))
    files={str(p):bd.digest(p.read_bytes()) for p in directory.iterdir()}
    assert bd.load_decoder(tmp_path,files).decode([0])=='A'
    with pytest.raises(ValueError,match='missing'):bd.load_decoder(tmp_path,{})
    (directory/'vocab.json').write_text('{}')
    with pytest.raises(ValueError,match='changed'):bd.load_decoder(tmp_path,files)
