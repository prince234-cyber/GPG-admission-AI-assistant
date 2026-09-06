import hashlib
import json
import os
import shutil
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings

PDF_PATH = os.getenv("PDF_PATH", "knowledge/admission.pdf")
VECTOR_PATH = os.getenv("VECTOR_PATH", "vectorstore")
INDEX_META_PATH = os.path.join(VECTOR_PATH, "index_meta.json")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
MIN_RELEVANCE = float(os.getenv("RAG_MIN_RELEVANCE", "0.35"))
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "700"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "gpg_admission")

_embeddings = None
_db = None
_index_hash = None


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        print("[RAG] Loading embedding model:", EMBEDDING_MODEL)
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            encode_kwargs={"normalize_embeddings": True},
        )
        print("[RAG] Embedding model loaded.")
    return _embeddings


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_index_meta():
    if not os.path.exists(INDEX_META_PATH):
        return None
    try:
        with open(INDEX_META_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as exc:
        print("[RAG] Could not read index metadata:", exc)
        return None


def _write_index_meta(pdf_hash, page_count, chunk_count):
    Path(VECTOR_PATH).mkdir(parents=True, exist_ok=True)
    metadata = {
        "pdf_path": os.path.abspath(PDF_PATH),
        "pdf_sha256": pdf_hash,
        "embedding_model": EMBEDDING_MODEL,
        "collection": COLLECTION_NAME,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "distance_metric": "cosine",
        "normalized_embeddings": True,
        "page_count": page_count,
        "chunk_count": chunk_count,
    }
    with open(INDEX_META_PATH, "w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)


def _load_db():
    global _db
    _db = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=VECTOR_PATH,
        embedding_function=_get_embeddings(),
    )
    return _db


def _remove_old_index():
    global _db, _index_hash
    if os.path.exists(VECTOR_PATH):
        shutil.rmtree(VECTOR_PATH)
    _db = None
    _index_hash = None


def ingest_pdf(force=False):
    """Index only when the PDF/index configuration changed."""
    global _db, _index_hash

    if not os.path.exists(PDF_PATH):
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    pdf_hash = _sha256_file(PDF_PATH)
    meta = _read_index_meta()
    same_index = (
        not force
        and meta is not None
        and meta.get("pdf_sha256") == pdf_hash
        and meta.get("embedding_model") == EMBEDDING_MODEL
        and meta.get("collection") == COLLECTION_NAME
        and meta.get("distance_metric") == "cosine"
        and meta.get("normalized_embeddings") is True
        and os.path.isdir(VECTOR_PATH)
    )

    if same_index:
        _index_hash = pdf_hash
        if _db is None:
            _load_db()
        print("[RAG] PDF unchanged. Existing vector index reused.")
        return False

    print("[RAG] PDF changed or index missing. Rebuilding vector index...")
    print("[RAG] PDF SHA-256:", pdf_hash)
    _remove_old_index()

    loader = PyPDFLoader(PDF_PATH)
    documents = loader.load()
    if not documents:
        raise ValueError("PDF contains no readable pages.")

    for page_number, document in enumerate(documents, start=1):
        document.metadata["source_filename"] = os.path.basename(PDF_PATH)
        document.metadata["page_number"] = page_number
        document.metadata["document_hash"] = pdf_hash
        document.metadata["document_version"] = pdf_hash[:12]
        document.metadata["collection"] = COLLECTION_NAME

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(documents)
    if not chunks:
        raise ValueError("PDF text extraction produced no chunks.")

    for chunk_index, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = f"{pdf_hash[:16]}-{chunk_index}"

    print(f"[RAG] Loaded {len(documents)} pages; created {len(chunks)} chunks.")

    _db = Chroma.from_documents(
        documents=chunks,
        embedding=_get_embeddings(),
        collection_name=COLLECTION_NAME,
        collection_metadata={"hnsw:space": "cosine"},
        persist_directory=VECTOR_PATH,
    )
    _write_index_meta(pdf_hash, len(documents), len(chunks))
    _index_hash = pdf_hash
    print("[RAG] Knowledge base rebuilt successfully.")
    return True


def update_vector_database(force=False):
    return ingest_pdf(force=force)


def ensure_vector_database():
    ingest_pdf(force=False)


def create_knowledge_base():
    return ingest_pdf(force=True)


def retrieve_pdf_context(question, top_k=RAG_TOP_K):
    """Return cosine-similarity-scored chunks from the current PDF index.

    We intentionally do NOT use Chroma's
    similarity_search_with_relevance_scores() here because its default
    relevance mapping can produce negative values for some distance metrics.
    The collection is explicitly configured for cosine distance, so we use
    the raw cosine distance and convert it to similarity: similarity=1-distance.
    """
    ensure_vector_database()
    if _db is None:
        _load_db()

    try:
        scored = _db.similarity_search_with_score(question, k=top_k)
    except Exception as exc:
        print("[RAG] Retrieval error:", exc)
        return []

    results = []
    for document, distance in scored:
        text = document.page_content.strip()
        if not text:
            continue

        # With the collection configured as cosine, Chroma returns cosine
        # distance. Convert it to a bounded similarity score.
        similarity = max(0.0, min(1.0, 1.0 - float(distance)))

        results.append({
            "text": text,
            "score": similarity,
            "distance": float(distance),
            "source_filename": document.metadata.get(
                "source_filename", os.path.basename(PDF_PATH)
            ),
            "page_number": document.metadata.get("page_number"),
            "document_hash": document.metadata.get("document_hash"),
            "document_version": document.metadata.get("document_version"),
            "chunk_id": document.metadata.get("chunk_id"),
        })

    # Chroma returns nearest first, but explicitly sort for deterministic behavior.
    results.sort(key=lambda item: item["score"], reverse=True)

    best = f"{results[0]['score']:.3f}" if results else "none"
    print(f"[RAG] Retrieved {len(results)} chunks; best similarity={best}")
    return results


def evaluate_pdf_relevance(results, min_relevance=MIN_RELEVANCE):
    """Decide whether the PDF contains enough semantically relevant material."""
    relevant = [item for item in results if item["score"] >= min_relevance]

    found = bool(relevant)
    print(
        f"[RAG] Similarity threshold={min_relevance:.3f}; "
        f"relevant={'YES' if found else 'NO'} "
        f"({len(relevant)}/{len(results)})"
    )
    return found, relevant


def search_information(question):
    """Backward-compatible text-only search helper."""
    results = retrieve_pdf_context(question)
    found, relevant = evaluate_pdf_relevance(results)
    if not found:
        return ""

    blocks = []
    for item in relevant:
        blocks.append(
            f"SOURCE: {item['source_filename']} | PAGE: {item['page_number'] or '?'}\n"
            f"RELEVANCE: {item['score']:.3f}\n{item['text']}"
        )
    context = "\n\n--- PDF CHUNK ---\n\n".join(blocks)
    print("[RAG] Relevant PDF context length:", len(context))
    return context
