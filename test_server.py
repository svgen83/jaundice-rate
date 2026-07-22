import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, patch
from server import process_url, ArticleNotFound


@pytest.fixture
def morph():
    import pymorphy3
    return pymorphy3.MorphAnalyzer()


@pytest.fixture
def charged_words():
    return {'шокирующий', 'сенсационный'}


@pytest.mark.asyncio
async def test_process_url_ok(morph, charged_words):
    url = "https://inosmi.ru/test"
    html = "<html><body><div class='layout-article'>текст</div></body></html>"
    session = AsyncMock()

    with patch('server.fetch', new_callable=AsyncMock,
               return_value=html):
        with patch('server.sanitize', return_value="текст"):
            with patch('server.split_by_words',
                       new_callable=AsyncMock,
                       return_value=['текст']):
                with patch('server.calculate_jaundice_rate',
                           return_value=50.0):
                    result = await process_url(session, url,
                                               morph, charged_words)
                    assert result['status'] == 'OK'
                    assert result['score'] == 50.0
                    assert result['words_count'] == 1


@pytest.mark.asyncio
async def test_process_url_fetch_error(morph, charged_words):
    url = "https://inosmi.ru/notexist"
    session = AsyncMock()
    with patch('server.fetch', new_callable=AsyncMock,
               side_effect=aiohttp.ClientError("404")):
        result = await process_url(
            session, url,
            morph, charged_words)
        assert result['status'] == 'FETCH_ERROR'
        assert result['score'] is None
        assert '404' in result['error_detail']


@pytest.mark.asyncio
async def test_process_url_parsing_error(morph, charged_words):
    url = "https://inosmi.ru/test"
    html = "<html><body>no article</body></html>"
    session = AsyncMock()

    with patch('server.fetch',
               new_callable=AsyncMock,
               return_value=html):
        with patch('server.sanitize',
                   side_effect=ArticleNotFound("No layout")):
            result = await process_url(
                session, url,
                morph, charged_words)
            assert result['status'] == 'PARSING_ERROR'
            assert result['score'] is None
            assert 'No layout' in result['error_detail']


@pytest.mark.asyncio
async def test_process_url_timeout(morph,
                                   charged_words):
    url = "https://inosmi.ru/slow"
    session = AsyncMock()

    async def slow_fetch(*args, **kwargs):
        await asyncio.sleep(10)
        return "<html></html>"

    with patch('server.fetch',
               new_callable=AsyncMock,
               side_effect=slow_fetch):
        with patch('server.TIMEOUT_SECONDS', 0.1):
            result = await process_url(session, url,
                                       morph, charged_words)
            assert result['status'] == 'TIMEOUT'
            assert result['score'] is None
            assert 'Timeout' in result['error_detail']
