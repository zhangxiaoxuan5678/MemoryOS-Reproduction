"""Pure data conversion: no configuration, model imports, or network."""
import re


def process_conversation(conversation_data):
    """Pair A then B within a session; preserve every other turn as a single-sided page."""
    a, b = conversation_data['speaker_a'], conversation_data['speaker_b']
    sessions = sorted((k for k in conversation_data if re.fullmatch(r'session_\d+', k)), key=lambda k: int(k.split('_')[1]))
    pages = []
    for session in sessions:
        pending = None
        for index, turn in enumerate(conversation_data[session]):
            speaker = turn['speaker']
            if speaker not in (a, b):
                raise ValueError('Unknown speaker in ' + session)
            text = turn['text']
            if turn.get('blip_caption'):
                text += f" (image description: {turn['blip_caption']})"
            source = {'index': index, 'dia_id': turn.get('dia_id'), 'speaker': speaker}
            if speaker == b and pending is not None:
                pending['agent_response'] = text
                pending['source_turns'].append(source)
                pending = None
            else:
                page = {'user_input': text if speaker == a else '', 'agent_response': text if speaker == b else '', 'timestamp': conversation_data.get(session + '_date_time', ''), 'session_key': session, 'source_turns': [source]}
                pages.append(page)
                pending = page if speaker == a else None
    return pages
