"""
Build the ChromaDB vector index from scraped and PDF content.
Embeddings: Google Gemini text-embedding-004 (free, multilingual, 768 dims)
Run this after scraper.py and pdf_loader.py.
"""

import os
import json
import time
import chromadb
from google import genai
from dotenv import load_dotenv

load_dotenv(override=True)

gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "scraped")
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
COLLECTION_NAME = "webb_knowledge"
CHUNK_SIZE = 1200     # larger chunks = more context per retrieval
CHUNK_OVERLAP = 250   # larger overlap = fewer missed details at boundaries
EMBED_MODEL = "gemini-embedding-001"


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Paragraph-aware chunking:
    1. Split text at natural paragraph breaks (\n\n)
    2. Merge small paragraphs until approaching chunk_size
    3. Add overlap by prepending the tail of the previous chunk
    """
    # Split into paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current = ""
    prev_tail = ""

    for para in paragraphs:
        candidate = (current + "\n\n" + para).strip() if current else para

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            # Save current chunk (with overlap prefix from previous chunk)
            if current:
                chunk = (prev_tail + "\n\n" + current).strip() if prev_tail else current
                chunks.append(chunk)
                # Keep last `overlap` chars as tail for next chunk's prefix
                prev_tail = current[-overlap:] if len(current) > overlap else current

            # If single paragraph exceeds chunk_size, split it by characters
            if len(para) > chunk_size:
                start = 0
                while start < len(para):
                    piece = para[start:start + chunk_size]
                    prefix = prev_tail + "\n\n" if prev_tail else ""
                    chunks.append((prefix + piece).strip())
                    prev_tail = piece[-overlap:] if len(piece) > overlap else piece
                    start += chunk_size - overlap
                current = ""
                prev_tail = para[-overlap:] if len(para) > overlap else para
            else:
                current = para

    # Don't forget the last chunk
    if current:
        chunk = (prev_tail + "\n\n" + current).strip() if prev_tail else current
        chunks.append(chunk)

    return chunks


def get_embeddings(texts):
    """Get embeddings using Gemini, with retry on rate limit."""
    embeddings = []
    for text in texts:
        for attempt in range(5):
            try:
                result = gemini.models.embed_content(
                    model=EMBED_MODEL,
                    contents=text,
                )
                embeddings.append(result.embeddings[0].values)
                time.sleep(0.55)  # Paid tier, ~20% faster than before
                break
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    wait = 60 * (attempt + 1)
                    print(f"\n  Rate limited. Waiting {wait}s before retry {attempt+1}/5...")
                    time.sleep(wait)
                else:
                    raise
        else:
            raise RuntimeError(f"Failed after 5 retries")
    return embeddings


def build_index():
    json_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]
    if not json_files:
        print(f"No data files found in {DATA_DIR}")
        print("Run ingest/scraper.py and ingest/pdf_loader.py first.")
        return

    print(f"Found {len(json_files)} documents.")
    print(f"Using Gemini {EMBED_MODEL} for embeddings.\n")

    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Resume mode: reuse existing collection if present
    try:
        collection = chroma_client.get_collection(COLLECTION_NAME)
        # Check which files already have their first chunk indexed
        already_indexed = set()
        for filename in json_files:
            first_chunk_id = f"{filename}_0"
            result = collection.get(ids=[first_chunk_id])
            if result["ids"]:
                already_indexed.add(filename)
        print(f"Resuming: {len(already_indexed)}/{len(json_files)} documents already indexed.\n")
    except Exception:
        collection = chroma_client.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        already_indexed = set()

    total_chunks = 0
    for filename in sorted(json_files):
        if filename in already_indexed:
            print(f"  Skip: {filename}")
            continue
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, encoding="utf-8") as f:
            doc = json.load(f)

        chunks = chunk_text(doc["content"])
        print(f"Indexing: {doc['title'][:60]} ({len(chunks)} chunks)")

        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            embeddings = get_embeddings(batch)
            ids = [f"{filename}_{i + j}" for j in range(len(batch))]
            metadatas = [
                {"source": doc["url"], "title": doc["title"]} for _ in batch
            ]
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=batch,
                metadatas=metadatas,
            )
            total_chunks += len(batch)

    print(f"\nIndex built successfully.")
    print(f"Total chunks: {total_chunks}")
    print(f"Database saved to: {CHROMA_DIR}")


if __name__ == "__main__":
    build_index()
