import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, APIStatusError

import ai_retry
import parser
import tag_selector
import lambda_function


def api_error(status=503, code=None, headers=None, kind=None):
    return APIStatusError(
        'secret-provider-message',
        response=httpx.Response(status, headers=headers, request=httpx.Request('POST', 'https://example.com')),
        body={'error': {'code': code, 'type': kind}},
    )


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    sleep = Mock()
    monkeypatch.setattr(ai_retry.time, 'sleep', sleep)
    return sleep


@pytest.mark.parametrize('error', [
    api_error(500), api_error(503), api_error(429, 'rate_limit_exceeded'),
    APIConnectionError(request=httpx.Request('POST', 'https://example.com')),
    APITimeoutError(request=httpx.Request('POST', 'https://example.com')),
])
def test_transient_retries_and_succeeds(error, no_sleep):
    action = Mock(side_effect=[error, 'ok'])
    assert ai_retry.run_ai_operation('embedding', action) == 'ok'
    assert action.call_count == 2
    no_sleep.assert_called_once()


def test_exhausts_three_attempts_and_logs_without_secrets(caplog, no_sleep):
    action = Mock(side_effect=api_error())
    with pytest.raises(ai_retry.AIServiceError, match=ai_retry.SAFE_MESSAGE):
        ai_retry.run_ai_operation('embedding', action)
    assert action.call_count == 3
    assert no_sleep.call_count == 2
    records = [json.loads(record.message) for record in caplog.records]
    assert [record['attempt'] for record in records] == [1, 2, 3]
    assert all(record['operation'] == 'embedding' and record['http_status'] == 503 for record in records)
    assert 'secret-provider-message' not in caplog.text


@pytest.mark.parametrize('status,code', [
    (400, None), (401, None), (403, None), (502, None),
    *[(429, code) for code in ai_retry.PERMANENT_CODES], (429, 'unknown_quota_error'),
])
def test_permanent_failure_never_retries(status, code, no_sleep):
    action = Mock(side_effect=api_error(status, code))
    with pytest.raises(ai_retry.AIServiceError):
        ai_retry.run_ai_operation('llm_parsing', action)
    action.assert_called_once()
    no_sleep.assert_not_called()


@pytest.mark.parametrize('header,expected', [('7', 7), ('0', 0), ('Thu, 01 Jan 1970 00:00:10 GMT', 10)])
def test_retry_after_precedes_backoff(header, expected, monkeypatch, no_sleep):
    monkeypatch.setattr(ai_retry.time, 'time', lambda: 0)
    jitter = Mock(side_effect=AssertionError('must not calculate backoff'))
    monkeypatch.setattr(ai_retry.random, 'uniform', jitter)
    action = Mock(side_effect=[api_error(headers={'Retry-After': header}), 'ok'])
    assert ai_retry.run_ai_operation('embedding', action) == 'ok'
    no_sleep.assert_called_once_with(expected)


def test_backoff_is_exponential_with_jitter(monkeypatch, no_sleep):
    monkeypatch.setattr(ai_retry.random, 'uniform', lambda a, b: 0.25)
    action = Mock(side_effect=[api_error(headers={'Retry-After': 'bad'}), api_error(), 'ok'])
    ai_retry.run_ai_operation('embedding', action)
    assert [call.args[0] for call in no_sleep.call_args_list] == [1.25, 2.25]


VALID = {'category': 'writing', 'must_have': {'price_type': [], 'language': [], 'use_cases': []},
         'nice_to_have': {'use_cases': []}, 'functions': []}


def completion(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.mark.parametrize('invalid', ['not json', '{}', json.dumps({**VALID, 'category': 'invalid'})])
def test_validation_retries_and_shares_api_budget(invalid, caplog):
    client = Mock()
    client.chat.completions.create.side_effect = [api_error(), completion(invalid), completion(json.dumps(VALID))]
    result = parser.parse_query_with_retry('prompt', client, 'model', {'categories': ['writing']})
    assert result == VALID
    assert client.chat.completions.create.call_count == 3
    logs = [json.loads(record.message) for record in caplog.records if record.name == 'ai_retry']
    assert logs[-1]['attempt'] == 2
    assert logs[-1]['validation_error']


def test_validation_exhaustion_stops_at_three():
    client = Mock()
    client.chat.completions.create.return_value = completion('not json')
    with pytest.raises(ai_retry.AIServiceError):
        parser.parse_query_with_retry('prompt', client, 'model', {})
    assert client.chat.completions.create.call_count == 3


def test_embedding_call_uses_shared_retry():
    client = Mock()
    client.embeddings.create.side_effect = [api_error(), SimpleNamespace(data=[SimpleNamespace(embedding=[1] * 1536)])]
    assert tag_selector._get_query_embedding('query', client).shape == (1536,)
    assert client.embeddings.create.call_count == 2


@pytest.mark.parametrize('operation', ['embedding', 'llm_parsing'])
def test_handler_returns_safe_error_and_closes_database(operation, monkeypatch):
    for key, value in {'endpoint': 'host', 'dbname': 'db', 'username': 'user', 'pwd': 'secret',
                       'portnum': '3306', 'OPENAI_API_KEY': 'secret-key', 'openai_model': 'model'}.items():
        monkeypatch.setenv(key, value)
    client = Mock()
    factory = Mock(return_value=client)
    monkeypatch.setattr(lambda_function, 'OpenAI', factory)
    connection = Mock()
    monkeypatch.setattr(lambda_function.db, 'get_db_connection', Mock(return_value=connection))
    close = Mock()
    monkeypatch.setattr(lambda_function.db, 'close_db_connection', close)
    monkeypatch.setattr(lambda_function.db, 'get_taxonomy_context', Mock(return_value={}))
    if operation == 'embedding':
        client.embeddings.create.side_effect = api_error(401)
    else:
        monkeypatch.setattr(tag_selector, 'select_candidate_tags', Mock(return_value={'use_cases': [], 'functions': []}))
        client.chat.completions.create.return_value = completion('invalid json')
    result = lambda_function.lambda_handler({'httpMethod': 'POST', 'body': '{"query":"write a blog"}'}, None)
    assert result['statusCode'] == 503
    body = json.loads(result['body'])
    assert body['error']['message'] == ai_retry.SAFE_MESSAGE
    assert body['error']['detail'] == ai_retry.SAFE_MESSAGE
    assert 'secret' not in result['body']
    factory.assert_called_once_with(api_key='secret-key', max_retries=0)
    close.assert_called_once_with(connection)

@pytest.mark.parametrize('field,value', [
    ('price_type', ['unknown']), ('language', ['unknown']),
    ('use_cases', [{'primary_tag': ' ', 'secondary_tag': None}]),
])
def test_invalid_taxonomy_retries(field, value):
    invalid = {**VALID, 'must_have': {**VALID['must_have'], field: value}}
    client = Mock()
    client.chat.completions.create.side_effect = [completion(json.dumps(invalid)), completion(json.dumps(VALID))]
    result = parser.parse_query_with_retry('prompt', client, 'model', {
        'categories': ['writing'], 'price_types': ['free'], 'languages': ['english']})
    assert result == VALID
    assert client.chat.completions.create.call_count == 2


def test_permanent_429_type_does_not_retry(no_sleep):
    action = Mock(side_effect=api_error(429, kind='insufficient_quota'))
    with pytest.raises(ai_retry.AIServiceError):
        ai_retry.run_ai_operation('embedding', action)
    action.assert_called_once()
    no_sleep.assert_not_called()

@pytest.mark.parametrize('operation', ['embedding', 'llm_parsing'])
@pytest.mark.parametrize('exhaust', [False, True])
def test_request_timeout_uses_existing_retry_flow(operation, exhaust, no_sleep, caplog):
    from openai import OpenAI

    requests = []

    def transport(request):
        requests.append(request)
        if exhaust or len(requests) == 1:
            raise httpx.ReadTimeout('private transport details', request=request)
        if operation == 'embedding':
            payload = {'object': 'list', 'data': [
                {'object': 'embedding', 'index': 0, 'embedding': [1.0] * 1536}],
                'model': 'text-embedding-3-small', 'usage': {'prompt_tokens': 1, 'total_tokens': 1}}
        else:
            payload = {'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': 'test',
                       'choices': [{'index': 0, 'finish_reason': 'stop',
                                    'message': {'role': 'assistant', 'content': json.dumps(VALID)}}]}
        return httpx.Response(200, json=payload)

    with OpenAI(api_key='test-key', max_retries=0,
                http_client=httpx.Client(transport=httpx.MockTransport(transport))) as client:
        def invoke():
            if operation == 'embedding':
                return tag_selector._get_query_embedding('query', client)
            return parser.parse_query_with_retry('prompt', client, 'test', {})

        if exhaust:
            with pytest.raises(ai_retry.AIServiceError) as caught:
                invoke()
            assert str(caught.value) == ai_retry.SAFE_MESSAGE
            assert isinstance(caught.value.__cause__, APITimeoutError)
        else:
            result = invoke()
            if operation == 'embedding':
                assert result.shape == (1536,)
            else:
                assert result == VALID

    assert len(requests) == (3 if exhaust else 2)
    assert no_sleep.call_count == (2 if exhaust else 1)
    for request in requests:
        assert request.extensions['timeout'] == dict(connect=15.0, read=15.0, write=15.0, pool=15.0)
    logs = [json.loads(record.message) for record in caplog.records if record.name == 'ai_retry']
    assert [entry['attempt'] for entry in logs] == ([1, 2, 3] if exhaust else [1])
    assert all(entry['operation'] == operation and entry['error_type'] == 'APITimeoutError' for entry in logs)
    assert 'private transport details' not in caplog.text


def test_parsing_timeout_and_validation_share_three_attempt_limit(no_sleep):
    client = Mock()
    timeout = APITimeoutError(request=httpx.Request('POST', 'https://example.com'))
    client.chat.completions.create.side_effect = [
        timeout, completion('invalid json'), timeout, completion(json.dumps(VALID))]
    with pytest.raises(ai_retry.AIServiceError):
        parser.parse_query_with_retry('prompt', client, 'model', {})
    assert client.chat.completions.create.call_count == 3
    assert no_sleep.call_count == 2
