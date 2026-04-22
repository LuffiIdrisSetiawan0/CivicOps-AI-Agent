import math
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.data_seed import ensure_policy_docs


@dataclass
class RetrievalHit:
    source: str
    title: str
    snippet: str
    score: float | None = None


class RAGService:
    SYNONYMS = {
        "asli": {"real", "synthetic"},
        "diperbarui": {"refreshed", "freshness"},
        "datanya": {"data", "available", "missing"},
        "indikator": {"indicator", "healthy"},
        "menangani": {"handle", "handled", "question"},
        "pertanyaan": {"question"},
        "seberapa": {"freshness", "often"},
        "sering": {"daily", "monthly"},
        "tersedia": {"available", "missing", "metric"},
        "warga": {"citizen", "pii", "records"},
    }

    def __init__(self, docs_path: str = "data/policies") -> None:
        self.docs_path = Path(docs_path)
        self.settings = get_settings()
        ensure_policy_docs()
        self._index = None
        self._chunk_cache: list[tuple[RetrievalHit, set[str]]] | None = None

    def search(self, query: str, top_k: int = 4, use_vector: bool = False) -> list[RetrievalHit]:
        if use_vector and self.settings.openai_api_key:
            try:
                return self._search_llamaindex(query, top_k=top_k)
            except Exception:
                return self._search_lexical(query, top_k=top_k)
        return self._search_lexical(query, top_k=top_k)

    def _search_llamaindex(self, query: str, top_k: int) -> list[RetrievalHit]:
        if self._index is None:
            import chromadb
            from llama_index.core import Settings as LlamaSettings
            from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
            from llama_index.embeddings.openai import OpenAIEmbedding
            from llama_index.vector_stores.chroma import ChromaVectorStore

            chroma_path = Path(self.settings.chroma_path)
            chroma_path.mkdir(parents=True, exist_ok=True)
            chroma_client = chromadb.PersistentClient(path=str(chroma_path))
            collection = chroma_client.get_or_create_collection("satudata_policies")
            vector_store = ChromaVectorStore(chroma_collection=collection)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            LlamaSettings.embed_model = OpenAIEmbedding(
                model=self.settings.embedding_model,
                api_key=self.settings.openai_api_key,
            )
            LlamaSettings.llm = None
            documents = SimpleDirectoryReader(str(self.docs_path), recursive=False).load_data()
            self._index = VectorStoreIndex.from_documents(
                documents,
                storage_context=storage_context,
                show_progress=False,
            )

        nodes = self._index.as_retriever(similarity_top_k=top_k).retrieve(query)
        hits: list[RetrievalHit] = []
        for node in nodes:
            metadata = node.node.metadata or {}
            source = str(metadata.get("file_name") or metadata.get("file_path") or "policy")
            title = self._title_for_source(source)
            text = node.node.get_text().replace("\n", " ").strip()
            hits.append(
                RetrievalHit(
                    source=source,
                    title=title,
                    snippet=text[:420],
                    score=float(node.score) if node.score is not None else None,
                )
            )
        return hits

    def _search_lexical(self, query: str, top_k: int) -> list[RetrievalHit]:
        query_terms = self._tokens(query)
        chunks = self._load_indexed_chunks()
        scored: list[tuple[float, RetrievalHit]] = []
        for hit, doc_terms in chunks:
            if not doc_terms:
                continue
            overlap = len(query_terms.intersection(doc_terms))
            if overlap == 0:
                continue
            score = overlap / math.sqrt(len(doc_terms))
            scored.append(
                (
                    score,
                    RetrievalHit(
                        source=hit.source,
                        title=hit.title,
                        snippet=hit.snippet,
                        score=round(score, 3),
                    ),
                )
            )
        scored.sort(key=lambda item: item[0], reverse=True)
        return [hit for _, hit in scored[:top_k]]

    def _load_indexed_chunks(self) -> list[tuple[RetrievalHit, set[str]]]:
        if self._chunk_cache is not None:
            return self._chunk_cache

        chunks: list[tuple[RetrievalHit, set[str]]] = []
        for path in sorted(self.docs_path.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            title = self._title_from_text(text, fallback=self._title_for_source(path.name))
            paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
            for paragraph in paragraphs:
                if paragraph.startswith("#"):
                    continue
                hit = RetrievalHit(
                    source=path.name,
                    title=title,
                    snippet=paragraph.replace("\n", " ")[:420],
                )
                chunks.append((hit, self._tokens(f"{hit.title} {hit.snippet}")))
        self._chunk_cache = chunks
        return chunks

    @staticmethod
    def _tokens(text: str) -> set[str]:
        stopwords = {
            "dan",
            "yang",
            "untuk",
            "dengan",
            "the",
            "and",
            "from",
            "what",
            "apa",
            "mana",
            "pada",
            "dari",
            "to",
            "of",
        }
        tokens = {
            token
            for token in re.findall(r"[a-zA-Z0-9_]+", text.lower())
            if len(token) > 2 and token not in stopwords
        }
        expanded = set(tokens)
        for token in tokens:
            expanded.update(RAGService.SYNONYMS.get(token, set()))
        return expanded

    @staticmethod
    def _title_from_text(text: str, fallback: str) -> str:
        for line in text.splitlines():
            if line.startswith("# "):
                return line.replace("#", "", 1).strip()
        return fallback

    @staticmethod
    def _title_for_source(source: str) -> str:
        return Path(source).stem.replace("_", " ").title()
