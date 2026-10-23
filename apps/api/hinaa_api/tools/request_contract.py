"""Clause-level request interpretation. Content is never execution authority."""
from __future__ import annotations

import re
from typing import Literal
from pydantic import BaseModel, Field


class RequestClause(BaseModel):
    text: str
    mode: Literal['discuss', 'execute', 'negate', 'cancel', 'quoted']
    deliverables: list[Literal['pdf', 'docx', 'pptx', 'image', 'folder']] = Field(default_factory=list)


class RequestContract(BaseModel):
    version: Literal['1'] = '1'
    clauses: list[RequestClause] = Field(default_factory=list)


def interpret_request(text: str) -> RequestContract:
    # Remove fenced, blockquoted and quoted history before splitting clauses.
    # Contractions and quoted object names in direct requests remain intact.
    clean = re.sub(r'```[\s\S]*?```|(?m:^\s*>[^\n]*)', '', text).strip()
    quotes: list[str] = []
    def protect(match):
        quotes.append(match.group(0))
        return f'__QUOTE_{len(quotes)-1}__'
    clean = re.sub(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`', protect, clean)
    clauses = []
    for part in re.split(r';|\n|,?\s+then\s+|\band\s+(?=(?:create|generate|make|explain|draw|do not)\b)', clean, flags=re.I):
        part = part.strip(' .')
        if not part:
            continue
        command = re.sub(r'^(?:hey\s+)?hinaa?[,\s]+|^hey\s+', '', part, flags=re.I).strip()
        command = re.sub(r'^(?:(?:please|kindly|now)\s+|(?:can|could|would|will)\s+you\s+)+', '', command, flags=re.I).strip()
        if re.match(r'^__QUOTE_|^["“`]|^(?:you said|i said|earlier|previously|yesterday|for example)\b', part, re.I):
            mode = 'quoted'
        elif re.match(r'^(?:stop|cancel|abort|halt|quit)\b', command, re.I):
            mode = 'cancel'
        elif re.match(r"^(?:do not|don't|never)\b", command, re.I):
            mode = 'negate'
        elif re.match(r'^(?:create|generate|make|write|prepare|build|draw|paint|render|export|design|mkdir|fetch|show|send|get|find|search)\b', command, re.I):
            mode = 'execute'
        else:
            mode = 'discuss'
        for index, quote in enumerate(quotes):
            part = part.replace(f'__QUOTE_{index}__', quote)
        deliverables = []
        if mode == 'execute':
            for name, pattern in [('pdf', r'\bpdfs?\b'), ('docx', r'\b(?:docx|word documents?)\b'),
                                  ('pptx', r'\b(?:pptx|slides?|decks?)\b'), ('image', r'\b(?:images?|illustrations?|pictures?)\b'),
                                  ('folder', r'\b(?:folders?|directory|directories)\b')]:
                if re.search(pattern, part, re.I):
                    deliverables.append(name)
            if not any(x in deliverables for x in ['pdf', 'docx', 'pptx']) and re.search(r'\b(?:report|document)\b', part, re.I):
                deliverables.insert(0, 'pdf')
        clauses.append(RequestClause(text=part, mode=mode, deliverables=deliverables))
    return RequestContract(clauses=clauses)
