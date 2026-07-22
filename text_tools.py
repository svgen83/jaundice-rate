import pymorphy3
import string
import asyncio
import logging
from pathlib import Path


logger = logging.getLogger(__name__)


def _clean_word(word):
    word = word.replace('«', '').replace('»', '').replace('…', '')
    word = word.strip(string.punctuation)
    return word


async def split_by_words(morph, text, chunk_size=100):
    words = []
    for word_number, word in enumerate(text.split()):
        cleaned_word = _clean_word(word)
        normalized_word = morph.parse(cleaned_word)[0].normal_form
        if len(normalized_word) > 2 or normalized_word == 'не':
            words.append(normalized_word)
        if (word_number + 1) % chunk_size == 0:
            await asyncio.sleep(0)
    return words


def calculate_jaundice_rate(article_words, charged_words):
    if not article_words:
        return 0.0
    charged_set = set(charged_words)
    found = [word for word in article_words if word in charged_set]
    score = len(found) / len(article_words) * 100
    return round(score, 2)


def load_charged_words(folder_path):
    charged = set()
    folder = Path(folder_path)
    if not folder.exists():
        logger.warning(
            f"Папка {folder_path} не найдена. Словарь пуст.")
        return charged
    for file_path in folder.glob("*.txt"):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                words = line.strip().split()
                for word in words:
                    if word:
                        charged.add(word.lower())
    return charged


def test_split_by_words():
    morph = pymorphy3.MorphAnalyzer()
    result = asyncio.run(split_by_words(
        morph, 'Во-первых, он хочет, чтобы'))
    assert result == ['во-первых', 'хотеть', 'чтобы']
    result = asyncio.run(split_by_words(
        morph, '«Удивительно, но это стало началом!»'))
    assert result == ['удивительно', 'это', 'стать', 'начало']


def test_calculate_jaundice_rate():
    assert -0.01 < calculate_jaundice_rate([], []) < 0.01
    assert 33.0 < calculate_jaundice_rate(
        ['все', 'аутсайдер', 'побег'],
        ['аутсайдер', 'банкротство']) < 34.0
