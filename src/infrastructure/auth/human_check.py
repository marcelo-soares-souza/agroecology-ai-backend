from __future__ import annotations

import time
import unicodedata

import jwt

from src.shared.config import JWT_SECRET

_CHALLENGE_TTL = 900  # 15 min

_QUESTIONS = {
    "pt-BR": [
        ("Quanto é 2 + 3?", ["5", "cinco"]),
        ("Quanto é 7 - 2?", ["5", "cinco"]),
        ("Quanto é 3 + 4?", ["7", "sete"]),
        ("Quanto é 10 - 4?", ["6", "seis"]),
        ("Quanto é 4 + 5?", ["9", "nove"]),
        ("Quanto é 8 + 1?", ["9", "nove"]),
        ("Quanto é 6 - 3?", ["3", "tres", "três"]),
        ("Quanto é 5 + 5?", ["10", "dez"]),
        ("Quanto é 2 + 2?", ["4", "quatro"]),
        ("Quanto é 9 - 5?", ["4", "quatro"]),
        ("Qual é o primeiro mês do ano?", ["janeiro", "jan", "1", "um"]),
        ("Qual é o último mês do ano?", ["dezembro", "dez", "12", "doze"]),
        ("Quantos dias tem uma semana?", ["7", "sete"]),
        ("Quantos meses tem um ano?", ["12", "doze"]),
        ("Qual a cor do céu em um dia claro?", ["azul"]),
        ("Qual a cor da grama?", ["verde"]),
        ("Qual a cor do leite?", ["branco", "branca"]),
        ("Em que ano estamos?", ["2026"]),
        ("Quantas horas tem um dia?", ["24", "vinte e quatro"]),
        ("Quantos minutos tem uma hora?", ["60", "sessenta"]),
    ],
    "en": [
        ("What is 2 + 3?", ["5", "five"]),
        ("What is 7 - 2?", ["5", "five"]),
        ("What is 3 + 4?", ["7", "seven"]),
        ("What is 10 - 4?", ["6", "six"]),
        ("What is 4 + 5?", ["9", "nine"]),
        ("What is 8 + 1?", ["9", "nine"]),
        ("What is 6 - 3?", ["3", "three"]),
        ("What is 5 + 5?", ["10", "ten"]),
        ("What is 2 + 2?", ["4", "four"]),
        ("What is 9 - 5?", ["4", "four"]),
        ("What is the first month of the year?", ["january", "jan", "1", "one"]),
        ("What is the last month of the year?", ["december", "dec", "12", "twelve"]),
        ("How many days are in a week?", ["7", "seven"]),
        ("How many months are in a year?", ["12", "twelve"]),
        ("What color is the sky on a clear day?", ["blue"]),
        ("What color is grass?", ["green"]),
        ("What color is milk?", ["white"]),
        ("What year is it?", ["2026"]),
        ("How many hours are in a day?", ["24", "twenty four", "twenty-four"]),
        ("How many minutes are in an hour?", ["60", "sixty"]),
    ],
}


def create_challenge(locale: str = "pt-BR") -> dict:
    locale_questions = _QUESTIONS.get(locale, _QUESTIONS["pt-BR"])
    import random

    question_text, valid_answers = random.choice(locale_questions)
    question_id = locale_questions.index((question_text, valid_answers))

    now = int(time.time())
    token = jwt.encode(
        {
            "locale": locale,
            "question_id": question_id,
            "exp": now + _CHALLENGE_TTL,
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"challenge_id": token, "question": question_text}


def verify_challenge(challenge_id: str, answer: str) -> bool:
    try:
        payload = jwt.decode(challenge_id, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False

    locale = payload.get("locale", "pt-BR")
    question_id = payload["question_id"]
    locale_questions = _QUESTIONS.get(locale, _QUESTIONS["pt-BR"])
    _, valid_answers = locale_questions[question_id]

    normalized_answer = (
        unicodedata.normalize("NFD", answer.strip().lower())
        .encode("ascii", "ignore")
        .decode()
    )
    for valid in valid_answers:
        normalized_valid = (
            unicodedata.normalize("NFD", valid.lower())
            .encode("ascii", "ignore")
            .decode()
        )
        if normalized_answer == normalized_valid:
            return True
    return False
