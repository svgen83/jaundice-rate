import aiohttp
import anyio
import asyncio
import pymorphy3
import async_timeout
import logging
from enum import Enum

from adapters.inosmi_ru import sanitize, ArticleNotFound
from text_tools import (split_by_words,
                        calculate_jaundice_rate,
                        load_charged_words)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    OK = 'OK'
    FETCH_ERROR = 'FETCH_ERROR'
    PARSING_ERROR = 'PARSING_ERROR'
    TIMEOUT = 'TIMEOUT'


TEST_ARTICLES = [
    'https://inosmi.ru/20260629/ormuz-279091044.html',
    'https://inosmi.ru/not/exist.html',
    'https://lenta.ru/brief/2021/08/26/afg_terror/',
    'http://example.com/slow'
]

morph = pymorphy3.MorphAnalyzer()


async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def process_article(session, url, morph, charged_words, results):
    timeout_seconds = 5.0
    try:
        async with async_timeout.timeout(timeout_seconds):
            html = await fetch(session, url)

        html_sanitized = sanitize(html)
        article_words = await split_by_words(morph, html_sanitized)
        total_words = len(article_words)
        rating = calculate_jaundice_rate(article_words, charged_words)

        results.append({
            "url": url,
            "status": ProcessingStatus.OK,
            "total_words": total_words,
            "rating": rating,
        })
    except asyncio.TimeoutError:
        results.append({
            "url": url,
            "status": ProcessingStatus.TIMEOUT,
            "total_words": None,
            "rating": None,
            "error_detail": f"Timeout after {timeout_seconds}s",
        })
    except aiohttp.ClientError as e:
        results.append({
            "url": url,
            "status": ProcessingStatus.FETCH_ERROR,
            "total_words": None,
            "rating": None,
            "error_detail": str(e),
        })
    except ArticleNotFound as e:
        results.append({
            "url": url,
            "status": ProcessingStatus.PARSING_ERROR,
            "total_words": None,
            "rating": None,
            "error_detail": (str(e)
                             if str(e)
                             else "Article structure not found"),
        })
    except Exception as e:
        results.append({
            "url": url,
            "status": ProcessingStatus.FETCH_ERROR,
            "total_words": None,
            "rating": None,
            "error_detail": str(e),
        })


def _sort_key(item):
    rating = item.get('rating')
    if rating is None:
        return (1, 0)
    else:
        return (0, -rating)


def sort_by_rating(results):
    return sorted(results, key=_sort_key)


async def main():
    charged_words = load_charged_words("charged_dict")
    logger.info(f"Загружено {len(charged_words)} заряженных слов.")

    results = []
    async with aiohttp.ClientSession() as session:
        async with anyio.create_task_group() as tg:
            for url in TEST_ARTICLES:
                tg.start_soon(process_article, session,
                              url, morph,
                              charged_words, results)

    sorted_results = sort_by_rating(results)

    logger.info("Сравнение статей по рейтингу желтушности:")
    for idx, res in enumerate(sorted_results, start=1):
        status = res['status']
        if status == ProcessingStatus.OK:
            logger.info(
                f"{idx}. {res['url']} -> Статус: OK, "
                f"Слов: {res['total_words']}, Рейтинг: {res['rating']}%"
            )
        elif status == ProcessingStatus.FETCH_ERROR:
            logger.info(
                f"{idx}. {res['url']} -> Статус: FETCH_ERROR"
                f"""{' - ' + res['error_detail']
                if 'error_detail' in res else ''}"""
            )
        elif status == ProcessingStatus.PARSING_ERROR:
            logger.info(
                f"""
                {idx}. {res['url']} -> Статус: PARSING_ERROR"""
                f"""
                 {' - ' + res['error_detail']
                 if 'error_detail' in res else ''}"""
            )
        elif status == ProcessingStatus.TIMEOUT:
            logger.info(
                f"{idx}. {res['url']} -> Статус: TIMEOUT"
                f"""
                 {' - ' + res['error_detail']
                 if 'error_detail' in res else ''}"""
            )
        else:
            logger.info(
                f"{idx}. {res['url']} -> Статус: {status.value}")

if __name__ == "__main__":
    anyio.run(main)
