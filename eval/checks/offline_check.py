"""No credentials, network, model downloads, or memory writes are needed."""
import ast
import importlib
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / 'eval'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
sys.dont_write_bytecode = True
sys.path.insert(0, str(EVAL))


def forbidden(*args, **kwargs):
    raise AssertionError('Network or model loading is forbidden in offline checks')


def main():
    for path in EVAL.glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    with patch.object(socket.socket, 'connect', forbidden), patch.object(socket, 'create_connection', forbidden):
        import openai
        import sentence_transformers
        with patch.object(openai, 'OpenAI', forbidden), patch.object(sentence_transformers, 'SentenceTransformer', forbidden):
            modules = {p.stem: importlib.import_module(p.stem) for p in EVAL.glob('*.py')}
        utils = modules['utils']
        # Mock dotenv before constructing clients: never read the real .env.
        with patch.object(utils, 'load_dotenv') as dotenv, patch.dict(os.environ, {}, clear=True):
            try:
                utils.OpenAIClient()
            except ValueError as error:
                assert all(name in str(error) for name in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL'))
            else:
                raise AssertionError('Missing configuration was accepted')
            dotenv.assert_called_once_with(ROOT / '.env', override=False)
        fake = dict(OPENAI_API_KEY='offline-placeholder', OPENAI_BASE_URL='https://offline.invalid/v1', OPENAI_MODEL='offline-model')
        with patch.object(utils, 'load_dotenv'), patch.object(utils, 'OpenAI') as sdk, patch.dict(os.environ, fake, clear=True):
            client = utils.OpenAIClient()
            sdk.assert_called_once_with(api_key=fake['OPENAI_API_KEY'], base_url=fake['OPENAI_BASE_URL'])
            assert client.client is sdk.return_value
            sdk.return_value.chat.completions.create.return_value.choices = [Mock(message=Mock(content=' offline '))]
            assert client.chat_completion(messages=[], temperature=0.3, max_tokens=100) == 'offline'
            sdk.return_value.chat.completions.create.assert_called_once_with(model='offline-model', messages=[], temperature=0.3, max_tokens=100)
        from dotenv import load_dotenv
        from io import StringIO
        with patch.object(utils, 'load_dotenv', side_effect=lambda path, override: load_dotenv(stream=StringIO('OPENAI_MODEL=file-model\n'), override=override)), patch.object(utils, 'OpenAI'), patch.dict(os.environ, fake, clear=True):
            assert utils.OpenAIClient().model == 'offline-model'
        utils._get_embedding_model.cache_clear()
        with patch.object(utils, 'SentenceTransformer') as factory:
            factory.return_value.encode.return_value = ['vector']
            assert utils.get_embedding('one') == 'vector'
            utils.get_embedding('two')
            factory.assert_called_once_with('all-MiniLM-L6-v2')
            assert factory.return_value.encode.call_args_list[0].args == (['one'],)
            assert factory.return_value.encode.call_args_list[0].kwargs == {'convert_to_numpy': True}
        utils._get_embedding_model.cache_clear()
        sample = next(s for s in json.loads((EVAL / 'locomo10.json').read_text()) if s['sample_id'] == 'conv-26')
        pages = modules['main_loco_parse'].process_conversation(sample['conversation'])
        eligible = sum(bool(p['user_input']) or bool(p['agent_response']) for p in pages)
        print(json.dumps({'status': 'offline_checks_passed', 'sample_id': 'conv-26', 'processed_pages': len(pages), 'eligible_pages': eligible, 'discarded_pages': len(pages) - eligible}, ensure_ascii=False))


if __name__ == '__main__':
    main()
