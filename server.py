import asyncio
import contextlib
import logging
import time

import aiohttp
import async_timeout
import pymorphy3
from aiohttp import web
from functools import partial

from adapters.inosmi_ru import ArticleNotFound, sanitize
from text_tools import (calculate_jaundice_rate,
                        load_charged_words,
                        split_by_words)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


MAX_URLS = 10
TIMEOUT_SECONDS = 5.0


@contextlib.contextmanager
def timer(name):
    start = time.monotonic()
    yield
    elapsed = time.monotonic() - start
    logger.info(f"{name} закончен за {elapsed:.2f} сек")


async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def process_url(session, url, morph, charged_words):
    try:
        async with async_timeout.timeout(TIMEOUT_SECONDS):
            html = await fetch(session, url)

        with timer(f"Анализ статьи {url}"):
            html_sanitized = sanitize(html)
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
            "error_detail": f"Timeout after {TIMEOUT_SECONDS}s"
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

    url_list = [
        url.strip() for url in urls_param.split(',') if url.strip()]
    if not url_list:
        return web.json_response(
            {'error': 'No valid URLs provided'},
            status=400
        )

    if len(url_list) > MAX_URLS:
        return web.json_response(
            {'error': f'''too many urls in request,
                          should be {MAX_URLS} or less'''},
            status=400
        )

    async with aiohttp.ClientSession() as session:
        coros = [
            process_url(session, url, morph, charged_words)
            for url in url_list
        ]
        done, pending = await asyncio.wait(
            coros,
            return_when=asyncio.ALL_COMPLETED
        )
        results = [task.result() for task in done]

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
