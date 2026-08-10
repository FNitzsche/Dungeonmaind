from app.core.config import settings
from app.core.chat_store import chat_store
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
import os
import shutil
import numpy as np
from typing import List, Tuple
from uuid import UUID
import time


def embedding_search(query: str, source=False, persist_directory=None):

    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    if source:
        source_db = "rulebook"
    else:
        source_db = "transcriptions"

    embedding_model = SentenceTransformerEmbeddings(
        model_name=settings.embedding_model
    )

    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embedding_model,
    )

    # If rulebook search is active only use rulebook embeddings
    if source_db == "rulebook":
        results = vectorstore.similarity_search(
            query,
            k=min(settings.embedding_top_k, 6),
            filter={"source": source_db}
        )
    # If LLM is asked use the transcriptions and the rulebook information
    else:
        results_rulebook = vectorstore.similarity_search(
            query,
            k=2,
            filter={"source": "rulebook"}
        )
        results_transcriptions = vectorstore.similarity_search(
            query,
            k=settings.embedding_top_k,
            filter={"source": "transcriptions"}
        )

        results = results_rulebook + results_transcriptions

    for i, doc in enumerate(results):
        print(f"Result {i + 1}: {doc.page_content}")
        if source:
            print("Path:", doc.metadata.get("path"))

    # Always need to stop the vectorstor client if finished, otherwise windows will create a indefinite lock in the db file
    #vectorstore._client._system.stop()

    return results

def get_all_transcription_documents(
    persist_directory=None,
) -> list[Document]:
    """
    Return all transcription documents currently stored in ChromaDB.

    Unlike similarity search, this retrieves every transcription segment
    so the complete session can be arranged chronologically.
    """

    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    if not os.path.exists(
        os.path.join(persist_directory, "chroma.sqlite3")
    ):
        return []

    embedding_model = SentenceTransformerEmbeddings(
        model_name=settings.embedding_model
    )

    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embedding_model,
    )

    collection = vectorstore._collection

    stored_data = collection.get(
        where={"source": "transcriptions"},
        include=["documents", "metadatas"],
    )

    documents = stored_data.get("documents") or []
    metadatas = stored_data.get("metadatas") or []

    result: list[Document] = []

    for text, metadata in zip(documents, metadatas):
        if not text:
            continue

        result.append(
            Document(
                page_content=text,
                metadata=metadata or {},
            )
        )

    return sorted(
        result,
        key=lambda document: float(
            document.metadata.get("start_time", 0.0)
        ),
    )

# def embedd_transcriptions(embedding_text: list, speakers: list[str], persist_directory=None):

#     if persist_directory is None:
#         persist_directory = settings.chroma_db_path

#     if len(embedding_text) != len(speakers):
#         raise ValueError(
#             f"embedding_text ({len(embedding_text)}) and speakers ({len(speakers)}) must have the same length"
#         )

#     # Load embedding model locally
#     embedding_model = SentenceTransformerEmbeddings(
#         model_name=settings.embedding_model
#     )

#     documents = [
#         Document(
#             page_content=text,
#             metadata={"source": "transcriptions",
#                       "player_id": speakers[i],
#                       "session_id": "none",  # Update here later
#                       "path": "none"}
#         )
#         for i, text in enumerate(embedding_text)
#     ]

#     write_to_ChromaDB(persist_directory, documents, embedding_model)


def embedd_transcriptions(
    embedding_text: list[str],
    speakers: list[str],
    start_times: list[float],
    end_times: list[float],
    persist_directory=None
):
    """
    Store transcription segments in ChromaDB together with their
    speaker and audio timestamps.

    The text is converted into an embedding. The original text and
    metadata remain available when the document is retrieved later.
    """

    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    lengths = {
        len(embedding_text),
        len(speakers),
        len(start_times),
        len(end_times),
    }

    if len(lengths) != 1:
        raise ValueError(
            "embedding_text, speakers, start_times and end_times "
            "must have the same length"
        )

    embedding_model = SentenceTransformerEmbeddings(
        model_name=settings.embedding_model
    )

    documents = [
        Document(
            page_content=text,
            metadata={
                "source": "transcriptions",
                "player_id": speakers[i],
                "session_id": "none",
                "path": "none",
                "start_time": float(start_times[i]),
                "end_time": float(end_times[i]),
            },
        )
        for i, text in enumerate(embedding_text)
    ]

    write_to_ChromaDB(
        persist_directory,
        documents,
        embedding_model
    )


def embedd_rulebook(embedding_text: list, txt_paths: dict, persist_directory=None):
    """
    embedding_text: list of text content
    txt_paths: dict mapping index in embedding_text -> absolute txt path
    """
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    embedding_model = SentenceTransformerEmbeddings(model_name=settings.embedding_model)

    documents = []
    for text, txt_abs_path in zip(embedding_text, txt_paths):
        md_abs_path = txt_abs_path.replace(".txt", ".md")
        folder_name = os.path.basename(os.path.dirname(md_abs_path))
        filename = os.path.basename(md_abs_path)

        rel_path_with_prefix = os.path.join("./data/markdowns", folder_name, filename)
        #print(rel_path_with_prefix.replace("\\", "/"))

        doc = Document(
            page_content=text,
            metadata={
                "source": "rulebook",
                "player_id": "none",
                "session_id": "none",
                "path": rel_path_with_prefix.replace("\\", "/")
            }
        )
        documents.append(doc)

    write_to_ChromaDB(persist_directory, documents, embedding_model)


def read_text_files(rulebook_folder=None):
    if rulebook_folder is None:
        rulebook_folder = os.path.join(settings.backend_root_path, "data", "rulebook")

    texts = []
    txt_paths = []  # maps index in texts -> txt file path

    for subdir, dirs, files in os.walk(rulebook_folder):
        for file in files:
            if file.endswith(".txt"):
                txt_path = os.path.join(subdir, file)
                with open(txt_path, "r", encoding="utf-8") as f:
                    content = f.read()
                texts.append(content)
                txt_paths.append(txt_path.replace("\\", "/"))  # index -> txt path

    return texts, txt_paths


def delete_transcription_embeddings(persist_directory=None):
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    # Load embedding model
    embedding_model = SentenceTransformerEmbeddings(
        model_name=settings.embedding_model
    )

    if not os.path.exists(os.path.join(persist_directory, "chroma.sqlite3")):
        print("No database found at:", persist_directory)
        return

    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embedding_model,
    )

    collection = vectorstore._collection
    all_docs = collection.get(include=["metadatas"])

    ids_to_delete = [
        doc_id for doc_id, meta in zip(all_docs["ids"], all_docs["metadatas"])
        if meta.get("source") == "transcriptions"
    ]

    if not ids_to_delete:
        print("No transcriptions in database found.")
        return

    collection.delete(ids=ids_to_delete)
    print(f"Deleted {len(ids_to_delete)} documents with source='transcriptions'")

    #vectorstore._client._system.stop()


def has_rulebook_embeddings(persist_directory=None) -> bool:
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    try:
        embedding_model = SentenceTransformerEmbeddings(
            model_name=settings.embedding_model
        )

        vectorstore = Chroma(
            persist_directory=persist_directory,
            embedding_function=embedding_model,
        )

        collection = vectorstore._collection

        all_data = collection.get(include=["metadatas"])
        metadatas = all_data.get("metadatas", [])

        # Check if any document has source == "rulebook"
        for meta in metadatas:
            if meta.get("source") == "rulebook":
                return True

        return False  # no rulebook found

    except PermissionError:
        return False



def reembed_chroma_entries(new_model: str, persist_directory=None):
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    old_model = settings.embedding_model

    if old_model == new_model:
        return

    old_embedding_model = SentenceTransformerEmbeddings(model_name=old_model)
    new_embedding_model = SentenceTransformerEmbeddings(model_name=new_model)

    if not os.path.exists(os.path.join(persist_directory, "chroma.sqlite3")):
        print("No database found at:", persist_directory)
        return

    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=old_embedding_model
    )

    collection = vectorstore._collection
    all_data = collection.get(include=["metadatas", "documents"])

    texts = all_data["documents"]
    metadatas = all_data["metadatas"]
    ids = all_data["ids"]

    if not texts:
        print("No documents found in the database.")
        return

    print(f"Found {len(texts)} documents. Re-embedding with {new_model}...")

    new_embeddings = new_embedding_model.embed_documents(texts)

    collection.delete(ids=ids)

    collection.add(
        ids=ids, documents=texts, metadatas=metadatas, embeddings=new_embeddings
    )

    print(f"Re-embedded {len(texts)} documents with {new_model}.")

    #vectorstore._client._system.stop()


def delete_chromadb(delete_tmp_only=False, forced_stop=False, persist_directory=None):
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    if forced_stop:
        # Create vectorstore to get connection to the SQL client
        embedding_model = SentenceTransformerEmbeddings(
            model_name=settings.embedding_model
        )

        vectorstore = Chroma(
            persist_directory=persist_directory,
            embedding_function=embedding_model,
        )
        # Stops the SQLite client, which should break any lock the client has on the folder on windows
        vectorstore._client._system.stop()
        print("Stopped client")
        # Wait a short moment to be sure the lock is gone
        time.sleep(1)

    if delete_tmp_only:
        if not os.path.isdir(persist_directory):
            print("Chroma DB directory does not exist.")
            return

        deleted_any = False

        for name in os.listdir(persist_directory):
            path = os.path.join(persist_directory, name)
            print(path)
            if os.path.isdir(path) and name.startswith("tmp"):
                shutil.rmtree(path)
                print(f"Deleted subfolder: {path}")
                deleted_any = True

        if not deleted_any:
            print("No tmp* subfolders found to delete.")
    else:
        if os.path.exists(persist_directory):
            shutil.rmtree(persist_directory)
            print(f"Chroma DB at '{persist_directory}' has been deleted.")
        else:
            print("Chroma DB directory does not exist.")


def print_all_chromadb_entries(persist_directory=None):
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    embedding_model = SentenceTransformerEmbeddings(
        model_name="all-MiniLM-L6-v2"
    )

    if not os.path.exists(os.path.join(persist_directory, "chroma.sqlite3")):
        print("No Chroma DB found at", persist_directory)
        return

    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embedding_model
    )
    entries = vectorstore.get(ids=None)

    for i, doc in enumerate(entries['documents']):
        print(f"Entry {i + 1}")
        print(f"Document: {doc}")
        print(f"Metadata: {entries['metadatas'][i]}")
        print(f"ID: {entries['ids'][i]}")
        print("-" * 40)

    #vectorstore._client._system.stop()


def write_to_ChromaDB(persist_directory, documents, embedding_model):
    if os.path.exists(os.path.join(persist_directory, "chroma.sqlite3")):
        print("found db under " + persist_directory)
        vectorstore = Chroma(
            persist_directory=persist_directory,
            embedding_function=embedding_model,
        )
        vectorstore.add_documents(documents)
    else:
        print("No database exists, creating a new database...")
        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=embedding_model,
            persist_directory=persist_directory,
        )
    print(f"Saved {len(documents)} documents to Chroma at '{persist_directory}'")
    #vectorstore._client._system.stop()


def embed_text(embedding_text: str):
    embedding_model = SentenceTransformerEmbeddings(model_name=settings.embedding_model)
    embeddings = embedding_model.embed_query(embedding_text)
    return embeddings


async def embedding_search_on_chat_history(query: str, query_embedding: list[float], player_id: UUID) -> list[dict]:
    """
    Perform similarity search over in-memory embeddings.

    Returns a list of tuples: (chat_text, similarity_score)
    """
    top_k = settings.embedding_top_k
    query_embedding = np.array(query_embedding)

    history = await chat_store.history(player_id)
    if not history or len(query_embedding) == 0:
        query_as_history = [{
            "role": "user",
            "content": query
        }]
        return query_as_history


    # Get user request, assisstent response pairs for previous requests
    paired_entries = []
    for i in range(len(history) - 1):
        if history[i]["role"] == "user" and history[i + 1]["role"] == "assistant":
            paired_entries.append((history[i], history[i + 1]))

    #for user_entry, assistant_entry in paired_entries:
    #    print("User:", user_entry["content"])
    #    print("Assistant:", assistant_entry["content"])

    user_texts = [u["content"] for u, a in paired_entries]
    assistant_texts = [a["content"] for u, a in paired_entries]
    # Compute one embedding vector per text by averaging over token embeddings
    user_embeddings = [
        np.array(u["embedded_content"])
        for u, a in paired_entries if u["embedded_content"] is not None
    ]
    assistant_embeddings = [
        np.array(a["embedded_content"])
        for u, a in paired_entries if a["embedded_content"] is not None
    ]

    if not user_embeddings:
        print(
            f"No chat-history embeddings found for player: {player_id}"
        )
        return []

    user_embeddings_np = np.stack(user_embeddings)
    assistant_embeddings_np = np.stack(assistant_embeddings)
    print("Query shape:", query_embedding.shape)

    # Do the similarity calculations with cosine sim on both requests and answers
    print("assistant_embeddings shape:", assistant_embeddings_np.shape)
    assistant_similarities = assistant_embeddings_np @ query_embedding / (
            np.linalg.norm(assistant_embeddings_np, axis=1) * np.linalg.norm(query_embedding)
    )

    print("user_embeddings shape:", user_embeddings_np.shape)
    user_similarities = user_embeddings_np @ query_embedding / (
            np.linalg.norm(user_embeddings_np, axis=1) * np.linalg.norm(query_embedding)
    )
    pair_similarities = (assistant_similarities + user_similarities) / 2

    top_indices = pair_similarities.argsort()[::-1][:top_k]

    top_results = []
    # Important here, to keep the request, response order
    for idx in top_indices:
        # Add user entry
        top_results.append({
            "role": "user",
            "content": user_texts[idx]
        })
        # Add assistant entry
        top_results.append({
            "role": "assistant",
            "content": assistant_texts[idx]
        })

    # Add query at the end
    top_results.append({
            "role": "user",
            "content": query
        })

    return top_results
