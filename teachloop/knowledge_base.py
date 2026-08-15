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
    """Small persistent BM25 store for local Chinese teaching materials."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.chunks: list[dict[str, Any]] = []
        if self.path.exists():
            self.chunks = json.loads(self.path.read_text(encoding="utf-8"))
        for item in self.chunks:
            item.setdefault("tokens", _tokens(item.get("text", "")))
        self.last_search_stats: dict[str, Any] = {}

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
                    "tokens": _tokens(chunk),
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
        query_tokens = _tokens(query)
        if not query_tokens or not self.chunks:
            self.last_search_stats = {"query": query, "candidates": len(self.chunks), "hits": 0}
            return []
        document_frequency = {
            token: sum(token in set(item.get("tokens", [])) for item in self.chunks)
            for token in set(query_tokens)
        }
        average_length = sum(len(item.get("tokens", [])) for item in self.chunks) / len(self.chunks)
        scored = []
        for item in self.chunks:
            tokens = item.get("tokens", [])
            counts = {token: tokens.count(token) for token in set(query_tokens)}
            score = 0.0
            for token in query_tokens:
                frequency = counts.get(token, 0)
                if not frequency:
                    continue
                df = document_frequency[token]
                idf = math.log(1 + (len(self.chunks) - df + 0.5) / (df + 0.5))
                denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * len(tokens) / max(average_length, 1))
                score += idf * frequency * 2.5 / denominator
            public_item = {key: value for key, value in item.items() if key != "tokens"}
            scored.append({**public_item, "score": round(float(score), 4)})
        scored.sort(key=lambda item: item["score"], reverse=True)
        results = [item for item in scored[:top_k] if item["score"] > 0]
        self.last_search_stats = {"query": query, "candidates": len(self.chunks), "hits": len(results), "top_score": results[0]["score"] if results else 0}
        return results

    def delete_source(self, source: str) -> int:
        before = len(self.chunks)
        self.chunks = [item for item in self.chunks if item.get("source") != source]
        removed = before - len(self.chunks)
        if removed:
            self._save()
        return removed

    def rename_source(self, source: str, new_name: str) -> int:
        changed = 0
        for item in self.chunks:
            if item.get("source") == source:
                item["source"] = new_name
                changed += 1
        if changed:
            self._save()
        return changed

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
