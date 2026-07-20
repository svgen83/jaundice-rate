import asyncio
import aiohttp
from aiohttp import web
from functools import partial
import pymorphy3
import async_timeout
import logging
import time
import contextlib

from adapters.inosmi_ru import sanitize, ArticleNotFound
from text_tools import split_by_words, calculate_jaundice_rate
from text_tools import load_charged_words


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@contextlib.contextmanager
def timer(name):
    start = time.monotonic()
    yield
    elapsed = time.monotonic() - start
    logger.info(f"{name} закончен за {elapsed:.2f} сек")


async def fetch(session, url):
    """Скачивает HTML-страницу по URL."""
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def process_url(session, url, morph, charged_words):
    timeout_seconds = 5.0
    try:
        async with async_timeout.timeout(timeout_seconds):
            html = await fetch(session, url)

        with timer(f"Анализ статьи {url}"):
            # Очистка HTML (может выбросить ArticleNotFound)
            html_sanitized = sanitize(html)
            # Асинхронная разбивка на слова
            article_words = await split_by_words(morph, html_sanitized)
            total_words = len(article_words)
            rating = calculate_jaundice_rate(article_words, charged_words)

        return {
            "url": url,
            "status": "OK",
            "score": rating,
            "words_count": total_words
        }

    except asyncio.TimeoutError:
        return {
            "url": url,
            "status": "TIMEOUT",
            "score": None,
            "words_count": None,
            "error_detail": f"Timeout after {timeout_seconds}s"
        }
    except aiohttp.ClientError as e:
        return {
            "url": url,
            "status": "FETCH_ERROR",
            "score": None,
            "words_count": None,
            "error_detail": str(e)
        }
    except ArticleNotFound as e:
        return {
            "url": url,
            "status": "PARSING_ERROR",
            "score": None,
            "words_count": None,
            "error_detail": str(e) if str(e) else "Article structure not found"
        }
    except Exception as e:
        return {
            "url": url,
            "status": "ERROR",
            "score": None,
            "words_count": None,
            "error_detail": str(e)
        }


async def handle_analyze(request, morph, charged_words):
    urls_param = request.query.get('urls')
    if urls_param is None:
        return web.json_response(
            {'error': 'Missing "urls" parameter'},
            status=400
        )
    
    url_list = [url.strip() for url in urls_param.split(',') if url.strip()]
    if not url_list:
        return web.json_response(
            {'error': 'No valid URLs provided'},
            status=400
        )
    
    async with aiohttp.ClientSession() as session:
        tasks = [process_url(session, url, morph, charged_words) for url in url_list]
        results = await asyncio.gather(*tasks)

    return web.json_response(results)


def main():
    morph = pymorphy3.MorphAnalyzer()
    charged_words = load_charged_words("charged_dict")
    logger.info(f"Загружено {len(charged_words)} заряженных слов.")

    app = web.Application()

    handler = partial(handle_analyze, morph=morph, charged_words=charged_words)
    app.router.add_get('/', handler)

    web.run_app(app, host='127.0.0.1', port=8080)

if __name__ == '__main__':
    main()
