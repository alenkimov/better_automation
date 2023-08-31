import random
import string


def generate_nickname(length, numbers=False, signs=False, capital=False):
    # Базовые строки для имитации настоящих слов
    starting_strings = ['th', 'wh', 'sh', 'ch', 'pr', 'st', 'pl']
    vowels = 'aeiou'
    consonants = 'bcdfghjklmnpqrstvwxyz'

    # Символы для добавления
    digits = string.digits
    special_signs = '.-_'

    # Стартовая строка
    nickname = random.choice(starting_strings)

    # Генерация "реального" слова
    for i in range((length - len(nickname)) // 2):
        nickname += random.choice(vowels) + random.choice(consonants)

    # Обрезаем, если длина больше заданной
    nickname = nickname[:length]

    # Добавление чисел
    if numbers:
        position = random.randint(0, len(nickname) - 1)
        nickname = nickname[:position] + random.choice(digits) + nickname[position + 1:]

    # Добавление специальных символов
    if signs:
        position = random.randint(0, len(nickname) - 1)
        nickname = nickname[:position] + random.choice(special_signs) + nickname[position + 1:]

    # Добавление заглавных букв
    if capital:
        position = random.randint(0, len(nickname) - 1)
        nickname = nickname[:position] + nickname[position].upper() + nickname[position + 1:]

    return nickname[:length]
