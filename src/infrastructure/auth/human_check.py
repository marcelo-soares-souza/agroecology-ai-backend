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
        ("Qual é o primeiro mês do ano?", ["janeiro", "jan"]),
        ("Quantos dias tem uma semana?", ["7", "sete"]),
    ],
    "en": [
        ("What is 2 + 3?", ["5", "five"]),
        ("What is 7 - 2?", ["5", "five"]),
        ("What is 3 + 4?", ["7", "seven"]),
        ("What is 10 - 4?", ["6", "six"]),
        ("What is 4 + 5?", ["9", "nine"]),
        ("What is the first month of the year?", ["january", "jan"]),
        ("How many days are in a week?", ["7", "seven"]),
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
