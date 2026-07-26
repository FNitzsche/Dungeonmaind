"""ChromaDB vector store integration for rulebook and transcription embeddings."""

import os
import shutil
import time
from uuid import UUID

import numpy as np
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from app.core.chat_store import chat_store
from app.core.config import settings
from app.functions.embedding.entity_extractor import entities_as_metadata


def embedding_search(
    query: str, source: bool = False, persist_directory: str | None = None
) -> list[Document]:
    """Perform similarity search over ChromaDB embeddings.

    Args:
        query: The query text.
        source (bool): If True, search only rulebook embeddings; otherwise search
            both rulebook and transcriptions.
        persist_directory (str | None): Optional custom ChromaDB path.

    Returns:
        list[Document]: List of Document objects from the vector store.
    """

    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    source_db = 'rulebook' if source else 'transcriptions'

    vectorstore = Chroma(persist_directory=persist_directory)

    # If rulebook search is active only use rulebook embeddings
    if source_db == 'rulebook':
        results = vectorstore.similarity_search(
            query, k=min(settings.embedding_top_k, 6), filter={'source': source_db}
        )
    # If LLM is asked use the transcriptions and the rulebook information
    else:
        results_rulebook = vectorstore.similarity_search(query, k=2, filter={'source': 'rulebook'})
        results_transcriptions = vectorstore.similarity_search(
            query, k=settings.embedding_top_k, filter={'source': 'transcriptions'}
        )

        results = results_rulebook + results_transcriptions

    for i, doc in enumerate(results):
        print(f'Result {i + 1}: {doc.page_content}')
        if source:
            print('Path:', doc.metadata.get('path'))

    # Always need to stop the vectorstor client if finished, otherwise windows will create a indefinite lock in the db file
    # vectorstore._client._system.stop()

    return results


def get_all_transcription_documents(persist_directory: str | None = None) -> list[Document]:
    """Retrieve all transcription documents from ChromaDB.

    Args:
        persist_directory (str | None): Optional custom ChromaDB path.

    Returns:
        List of Document objects with source='transcriptions'.
    """
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    vectorstore = Chroma(persist_directory=persist_directory)
    entries = vectorstore._collection.get(
        where={'source': 'transcriptions'}, include=['documents', 'metadatas']
    )

    documents = entries.get('documents') or []
    metadatas = entries.get('metadatas') or []
    return [
        Document(page_content=document, metadata=metadata or {})
        for document, metadata in zip(documents, metadatas)
    ]


def embedd_transcriptions(
    embedding_text: list[str], speakers: list[str], persist_directory: str | None = None
):
    """Embed transcription texts with speaker metadata into ChromaDB.

    Args:
        embedding_text (list[str]): List of text strings to embed.
        speakers: List of speaker names corresponding to each text.
        persist_directory (str | None): Optional custom ChromaDB path.

    Raises:
        ValueError: If embedding_text and speakers have different lengths.
    """

    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    if len(embedding_text) != len(speakers):
        raise ValueError(
            f'embedding_text ({len(embedding_text)}) and speakers ({len(speakers)}) must have the same length'
        )

    # Load embedding model locally
    embedding_model = SentenceTransformerEmbeddings(model_name=settings.embedding_model)

    documents = []
    for i, text in enumerate(embedding_text):
        entity_metadata = entities_as_metadata(text, use_llm=settings.entity_llm_fallback)
        documents.append(
            Document(
                page_content=text,
                metadata={
                    'source': 'transcriptions',
                    'player_id': speakers[i],
                    'session_id': 'none',  # Update here later
                    'path': 'none',
                    **entity_metadata,
                },
            )
        )

    write_to_ChromaDB(persist_directory, documents, embedding_model)


def embedd_rulebook(
    embedding_text: list[str], txt_paths: dict[int, str], persist_directory: str | None = None
):
    """Embed rulebook text files into ChromaDB.

    Args:
        embedding_text: List of text contents.
        txt_paths (dict[int, str]): Dict mapping index in embedding_text to absolute txt path.
        persist_directory (str | None): Optional custom ChromaDB path.
    """
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    embedding_model = SentenceTransformerEmbeddings(model_name=settings.embedding_model)

    documents = []
    for text, txt_abs_path in zip(embedding_text, txt_paths):
        md_abs_path = txt_abs_path.replace('.txt', '.md')
        folder_name = os.path.basename(os.path.dirname(md_abs_path))
        filename = os.path.basename(md_abs_path)

        rel_path_with_prefix = os.path.join('./data/markdowns', folder_name, filename)
        # print(rel_path_with_prefix.replace("\\", "/"))

        doc = Document(
            page_content=text,
            metadata={
                'source': 'rulebook',
                'player_id': 'none',
                'session_id': 'none',
                'path': rel_path_with_prefix.replace('\\', '/'),
            },
        )
        documents.append(doc)

    write_to_ChromaDB(persist_directory, documents, embedding_model)


def read_text_files(rulebook_folder: str | None = None) -> tuple[list[str], list[str]]:
    """Read all .txt files from the rulebook folder.

    Args:
        rulebook_folder (str | None): Path to the rulebook folder. Defaults to
            the configured rulebook path.

    Returns:
        tuple[list[str], list[str]]: Tuple of (texts list, txt_paths list).
    """
    if rulebook_folder is None:
        rulebook_folder = os.path.join(settings.backend_root_path, 'data', 'rulebook')

    texts = []
    txt_paths = []  # maps index in texts -> txt file path

    for subdir, dirs, files in os.walk(rulebook_folder):
        for file in files:
            if file.endswith('.txt'):
                txt_path = os.path.join(subdir, file)
                with open(txt_path, encoding='utf-8') as f:
                    content = f.read()
                texts.append(content)
                txt_paths.append(txt_path.replace('\\', '/'))  # index -> txt path

    return texts, txt_paths


def delete_transcription_embeddings(persist_directory: str | None = None):
    """Delete all transcription documents from ChromaDB.

    Args:
        persist_directory (str | None): Optional custom ChromaDB path.
    """
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    # Load embedding model
    embedding_model = SentenceTransformerEmbeddings(model_name=settings.embedding_model)

    if not os.path.exists(os.path.join(persist_directory, 'chroma.sqlite3')):
        print('No database found at:', persist_directory)
        return

    vectorstore = Chroma(persist_directory=persist_directory, embedding_function=embedding_model)

    collection = vectorstore._collection
    all_docs = collection.get(include=['metadatas'])

    ids_to_delete = [
        doc_id
        for doc_id, meta in zip(all_docs['ids'], all_docs['metadatas'])
        if meta.get('source') == 'transcriptions'
    ]

    if not ids_to_delete:
        print('No transcriptions in database found.')
        return

    collection.delete(ids=ids_to_delete)
    print(f"Deleted {len(ids_to_delete)} documents with source='transcriptions'")

    # vectorstore._client._system.stop()


def has_rulebook_embeddings(persist_directory: str | None = None) -> bool:
    """Check if rulebook embeddings exist in ChromaDB.

    Args:
        persist_directory (str | None): Optional custom ChromaDB path.

    Returns:
        True if at least one rulebook document exists.
    """
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    try:
        embedding_model = SentenceTransformerEmbeddings(model_name=settings.embedding_model)

        vectorstore = Chroma(
            persist_directory=persist_directory, embedding_function=embedding_model
        )

        collection = vectorstore._collection

        all_data = collection.get(include=['metadatas'])
        metadatas = all_data.get('metadatas', [])

        # Check if any document has source == "rulebook"
        return any(meta.get('source') == 'rulebook' for meta in metadatas)  # no rulebook found

    except PermissionError:
        return False


def reembed_chroma_entries(new_model: str, persist_directory: str | None = None):
    """Re-embed all documents in ChromaDB with a new embedding model.

    Args:
        new_model: Name of the new embedding model.
        persist_directory (str | None): Optional custom ChromaDB path.
    """
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    old_model = settings.embedding_model

    if old_model == new_model:
        return

    old_embedding_model = SentenceTransformerEmbeddings(model_name=old_model)
    new_embedding_model = SentenceTransformerEmbeddings(model_name=new_model)

    if not os.path.exists(os.path.join(persist_directory, 'chroma.sqlite3')):
        print('No database found at:', persist_directory)
        return

    vectorstore = Chroma(
        persist_directory=persist_directory, embedding_function=old_embedding_model
    )

    collection = vectorstore._collection
    all_data = collection.get(include=['metadatas', 'documents'])

    texts = all_data['documents']
    metadatas = all_data['metadatas']
    ids = all_data['ids']

    if not texts:
        print('No documents found in the database.')
        return

    print(f'Found {len(texts)} documents. Re-embedding with {new_model}...')

    new_embeddings = new_embedding_model.embed_documents(texts)

    collection.delete(ids=ids)

    collection.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=new_embeddings)

    print(f'Re-embedded {len(texts)} documents with {new_model}.')

    # vectorstore._client._system.stop()


def delete_chromadb(
    delete_tmp_only: bool = False, forced_stop: bool = False, persist_directory: str | None = None
):
    """Delete ChromaDB directories, optionally only temporary subfolders.

    Args:
        delete_tmp_only (bool): If True, only delete tmp* subfolders.
        forced_stop (bool): If True, stop the SQLite client before deletion.
        persist_directory (str | None): Optional custom ChromaDB path.
    """
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    if forced_stop:
        # Create vectorstore without embedding model to avoid network/model loading during shutdown.
        vectorstore = Chroma(persist_directory=persist_directory)
        # Stops the SQLite client, which should break any lock the client has on the folder on windows
        vectorstore._client._system.stop()
        print('Stopped client')
        # Wait a short moment to be sure the lock is gone
        time.sleep(1)

    if delete_tmp_only:
        if not os.path.isdir(persist_directory):
            print('Chroma DB directory does not exist.')
            return

        deleted_any = False

        for name in os.listdir(persist_directory):
            path = os.path.join(persist_directory, name)
            print(path)
            if os.path.isdir(path) and name.startswith('tmp'):
                shutil.rmtree(path)
                print(f'Deleted subfolder: {path}')
                deleted_any = True

        if not deleted_any:
            print('No tmp* subfolders found to delete.')
    else:
        if os.path.exists(persist_directory):
            shutil.rmtree(persist_directory)
            print(f"Chroma DB at '{persist_directory}' has been deleted.")
        else:
            print('Chroma DB directory does not exist.')


def print_all_chromadb_entries(persist_directory: str | None = None):
    """Print all entries in ChromaDB for debugging.

    Args:
        persist_directory (str | None): Optional custom ChromaDB path.
    """
    if persist_directory is None:
        persist_directory = settings.chroma_db_path

    embedding_model = SentenceTransformerEmbeddings(model_name='all-MiniLM-L6-v2')

    if not os.path.exists(os.path.join(persist_directory, 'chroma.sqlite3')):
        print('No Chroma DB found at', persist_directory)
        return

    vectorstore = Chroma(persist_directory=persist_directory, embedding_function=embedding_model)
    entries = vectorstore.get(ids=None)

    for i, doc in enumerate(entries['documents']):
        print(f'Entry {i + 1}')
        print(f'Document: {doc}')
        print(f'Metadata: {entries["metadatas"][i]}')
        print(f'ID: {entries["ids"][i]}')
        print('-' * 40)

    # vectorstore._client._system.stop()


def write_to_ChromaDB(
    persist_directory: str,
    documents: list[Document],
    embedding_model: SentenceTransformerEmbeddings,
):
    """Write documents to ChromaDB, creating the database if it doesn't exist.

    Args:
        persist_directory (str): ChromaDB directory path.
        documents (list[Document]): List of Document objects to add.
        embedding_model (SentenceTransformerEmbeddings): The embedding function to use.
    """
    if os.path.exists(os.path.join(persist_directory, 'chroma.sqlite3')):
        print('found db under ' + persist_directory)
        vectorstore = Chroma(
            persist_directory=persist_directory, embedding_function=embedding_model
        )
        vectorstore.add_documents(documents)
    else:
        print('No database exists, creating a new database...')
        vectorstore = Chroma.from_documents(
            documents=documents, embedding=embedding_model, persist_directory=persist_directory
        )
    print(f"Saved {len(documents)} documents to Chroma at '{persist_directory}'")
    # vectorstore._client._system.stop()


def embed_text(embedding_text: str) -> list[float]:
    """Embed a single text string using the configured model.

    Args:
        embedding_text: The text to embed.

    Returns:
        list[float]: List of embedding floats.
    """
    embedding_model = SentenceTransformerEmbeddings(model_name=settings.embedding_model)
    embeddings = embedding_model.embed_query(embedding_text)
    return embeddings


async def embedding_search_on_chat_history(
    query: str, query_embedding: list[float], player_id: UUID
) -> list[dict]:
    """Perform similarity search over in-memory chat history embeddings.

    Computes cosine similarity between the query embedding and all paired
    user/assistant entries, returning the top-k most relevant pairs.

    Args:
        query: The user's original query text.
        query_embedding: The embedding vector for the query.
        player_id: The player's UUID.

    Returns:
        List of chat history message dicts, highest similarity first,
        with the current query appended at the end.
    """
    top_k = settings.embedding_top_k
    query_embedding = np.array(query_embedding)

    history = await chat_store.history(player_id)
    if not history or len(query_embedding) == 0:
        query_as_history = [{'role': 'user', 'content': query}]
        return query_as_history

    # Get user request, assisstent response pairs for previous requests
    paired_entries = []
    for i in range(len(history) - 1):
        if history[i]['role'] == 'user' and history[i + 1]['role'] == 'assistant':
            paired_entries.append((history[i], history[i + 1]))

    # for user_entry, assistant_entry in paired_entries:
    #    print("User:", user_entry["content"])
    #    print("Assistant:", assistant_entry["content"])

    user_texts = [u['content'] for u, a in paired_entries]
    assistant_texts = [a['content'] for u, a in paired_entries]
    # Compute one embedding vector per text by averaging over token embeddings
    user_embeddings = [
        np.array(u['embedded_content'])
        for u, a in paired_entries
        if u['embedded_content'] is not None
    ]
    assistant_embeddings = [
        np.array(a['embedded_content'])
        for u, a in paired_entries
        if a['embedded_content'] is not None
    ]

    user_embeddings_np = np.stack(user_embeddings)
    assistant_embeddings_np = np.stack(assistant_embeddings)
    print('Query shape:', query_embedding.shape)

    # Do the similarity calculations with cosine sim on both requests and answers
    print('assistant_embeddings shape:', assistant_embeddings_np.shape)
    assistant_similarities = (
        assistant_embeddings_np
        @ query_embedding
        / (np.linalg.norm(assistant_embeddings_np, axis=1) * np.linalg.norm(query_embedding))
    )

    print('user_embeddings shape:', user_embeddings_np.shape)
    user_similarities = (
        user_embeddings_np
        @ query_embedding
        / (np.linalg.norm(user_embeddings_np, axis=1) * np.linalg.norm(query_embedding))
    )
    pair_similarities = (assistant_similarities + user_similarities) / 2

    top_indices = pair_similarities.argsort()[::-1][:top_k]

    top_results = []
    # Important here, to keep the request, response order
    for idx in top_indices:
        # Add user entry
        top_results.append({'role': 'user', 'content': user_texts[idx]})
        # Add assistant entry
        top_results.append({'role': 'assistant', 'content': assistant_texts[idx]})

    # Add query at the end
    top_results.append({'role': 'user', 'content': query})

    return top_results
