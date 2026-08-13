from __future__ import annotations

import hashlib
import json
import math
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader


VECTOR_SIZE = 512


def _tokens(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    chinese = re.findall(r"[\u4e00-\u9fff]", normalized)
    bigrams = ["".join(chinese[index : index + 2]) for index in range(len(chinese) - 1)]
    latin = re.findall(r"[a-z0-9_]+", text.lower())
    return chinese + bigrams + latin


def embed_text(text: str) -> list[float]:
    vector = [0.0] * VECTOR_SIZE
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        number = int.from_bytes(digest, "big")
        index = number % VECTOR_SIZE
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _cosine(first: list[float], second: list[float]) -> float:
    return sum(a * b for a, b in zip(first, second))


def chunk_text(text: str, max_chars: int = 500, overlap: int = 80) -> list[str]:
    clean = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not clean:
        return []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", clean) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = current[-overlap:] + "\n\n" + paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks


class LocalVectorKnowledgeBase:
    """Small persistent vector store suitable for the competition MVP."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.chunks: list[dict[str, Any]] = []
        if self.path.exists():
            self.chunks = json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def count(self) -> int:
        return len(self.chunks)

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.chunks, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_text(self, text: str, source: str, page: int | None = None) -> int:
        existing = {item["id"] for item in self.chunks}
        added = 0
        for index, chunk in enumerate(chunk_text(text), start=1):
            identity = hashlib.sha256(f"{source}|{page}|{chunk}".encode("utf-8")).hexdigest()
            if identity in existing:
                continue
            self.chunks.append(
                {
                    "id": identity,
                    "source": source,
                    "page": page,
                    "section": index,
                    "text": chunk,
                }
            )
            existing.add(identity)
            added += 1
        if added:
            self._save()
        return added

    def add_pdf(self, data: bytes, source: str) -> int:
        reader = PdfReader(BytesIO(data))
        added = 0
        for page_number, page in enumerate(reader.pages, start=1):
            added += self.add_text(page.extract_text() or "", source=source, page=page_number)
        return added

    def search(self, query: str, top_k: int = 4) -> list[dict[str, Any]]:
        query_vector = embed_text(query)
        scored = []
        for item in self.chunks:
            score = _cosine(query_vector, embed_text(item["text"]))
            scored.append({**item, "score": round(float(score), 4)})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return [item for item in scored[:top_k] if item["score"] > 0]

    def sources(self) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for item in self.chunks:
            source = item["source"]
            grouped.setdefault(source, {"source": source, "chunks": 0, "pages": set()})
            grouped[source]["chunks"] += 1
            if item.get("page"):
                grouped[source]["pages"].add(item["page"])
        return [
            {**value, "pages": sorted(value["pages"])}
            for value in grouped.values()
        ]
