"""Lossless-data and single-sided-memory regression checks; no API calls."""
import json
from pathlib import Path
import sys
from unittest.mock import Mock, patch
import socket
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'eval'))
from study_data import process_conversation
from prepare_study import prepare


def audit(conversation):
    pages = process_conversation(conversation)
    expected = []
    for key in sorted((k for k in conversation if k.startswith('session_') and not k.endswith('_date_time')), key=lambda k: int(k.split('_')[1])):
        for index, turn in enumerate(conversation[key]):
            text = turn['text'] + (f" (image description: {turn['blip_caption']})" if turn.get('blip_caption') else '')
            expected.append((key, index, turn['speaker'], text, conversation.get(key + '_date_time', '')))
    actual = [(p['session_key'], t['index'], t['speaker'], p['user_input'] if t['speaker'] == conversation['speaker_a'] else p['agent_response'], p['timestamp']) for p in pages for t in p['source_turns']]
    assert actual == expected, 'Lost/reordered text, speaker, timestamp, or session'
    return pages


def main():
    def forbidden(*a, **k):
        raise AssertionError('Network forbidden')
    with patch.object(socket.socket, 'connect', forbidden), patch.object(socket, 'create_connection', forbidden):
        for sample in json.loads((ROOT / 'eval/locomo10.json').read_text()):
            audit(sample['conversation'])
        # Explicit cases: B opens a session; consecutive A/B; image caption.
        audit({'speaker_a': 'A', 'speaker_b': 'B', 'session_1': [{'speaker': 'A', 'text': 'a'}], 'session_2': [{'speaker': s, 'text': str(i), 'blip_caption': 'image'} for i, s in enumerate(['B', 'B', 'A', 'A', 'B'])]})
        from dynamic_update import DynamicUpdate
        for page in ({'user_input': 'a only', 'agent_response': ''}, {'user_input': '', 'agent_response': 'b only'}):
            short, mid = Mock(), Mock()
            short.is_full.side_effect = [True, False]
            short.pop_oldest.return_value = page
            updater = DynamicUpdate(short, mid, Mock(), client=Mock())
            updater._generate_meta_info = Mock(return_value='mock meta')
            with patch('dynamic_update.gpt_generate_multi_summary', return_value={'summaries': [{'content': 'mock summary', 'keywords': ['mock']}]}) as themes:
                updater.bulk_evict_and_update_mid_term()
                assert page.get('user_input') or page.get('agent_response')
                assert ('a only' if page['user_input'] else 'b only') in themes.call_args.args[0]
                assert len(mid.insert_pages_into_session.call_args.args[2]) == 1
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / 'first', Path(tmp) / 'second'
            a, b = prepare(first), prepare(second)
            assert a['files_sha256'] == b['files_sha256']
            assert a['question_count'] == 25 and a['categories'] == {1:6, 2:6, 3:6, 4:7}
            assert all(set(q) == {'question_id', 'question'} for q in json.loads((first / 'questions.json').read_text()))
            assert not any(k in json.loads((first / 'build_input/conversation.json').read_text()) for k in ('qa', 'answer', 'evidence'))
            try:
                prepare(first)
            except FileExistsError:
                pass
            else:
                raise AssertionError('Existing preparation overwritten')
    print('PASS: all 10 conversations lossless; edge cases; one-sided eviction; deterministic 25 questions; split references; overwrite refused; no API')


if __name__ == '__main__':
    main()
