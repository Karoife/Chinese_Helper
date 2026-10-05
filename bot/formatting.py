"""Build the Telegram message text (HTML parse mode) for a sentence."""
from __future__ import annotations

from html import escape
from typing import List

from data.models import Sentence, Word


def _word_line(word: Word) -> str:
    meaning = word.spanish or "(traducción al español pendiente)"
    return f"• <b>{escape(word.simplified)}</b> ({escape(word.pinyin)}) — {escape(meaning)}"


def format_sentence_message(sentence: Sentence, words: List[Word], *, heading: str) -> str:
    lines = [
        f"<b>{heading}</b> (HSK {sentence.hsk_level})",
        "",
        f"{escape(sentence.chinese)}",
        f"<i>{escape(sentence.pinyin)}</i>",
        f"{escape(sentence.spanish)}",
    ]
    if words:
        lines.append("")
        lines.append("<b>Desglose de la frase:</b>")
        lines.extend(_word_line(w) for w in words)
    return "\n".join(lines)


def format_progress(stats: dict, level: int, mode: str) -> str:
    mode_label = "tu nivel y los anteriores" if mode == "level_and_below" else "solo tu nivel"
    return (
        "<b>Tu progreso</b>\n"
        f"Nivel actual: HSK {level} ({mode_label})\n"
        f"Frases estudiadas: {stats['total_sent']}\n"
        f"Dominadas (repasadas 4 veces): {stats['mastered']}\n"
        f"En repaso activo: {stats['active']}\n"
        f"Repasos pendientes para hoy: {stats['due_today']}"
    )
