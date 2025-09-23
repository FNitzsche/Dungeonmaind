from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
import os
import shutil

def embedd_text(embedding_text: list, persist_directory="./chroma_db"):
    # Load embedding model locally
    embedding_model = SentenceTransformerEmbeddings(
        model_name="all-MiniLM-L6-v2"
    )

    documents = [Document(page_content=text) for text in embedding_text]

    # Later metadata should be included, such as session id, user id, maybe even timestamps
    #documents = [
    #    Document(page_content=item["text"], metadata={"session_id": item["session_id"]})
    #    for item in embedding_text
    #]

    # Loads the chroma db vectorstore if already found under given path, otherwise creates it from scratch
    if os.path.exists(os.path.join(persist_directory, "index")):
        vectorstore = Chroma(
            persist_directory=persist_directory,
            embedding_function=embedding_model
        )
        vectorstore.add_documents(documents)
    else:
        vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=embedding_model,
            persist_directory=persist_directory
        )

    # From Chromadb => 4 on, this should be done automatically
    # vectorstore.persist()

    print(f"Saved {len(documents)} documents to Chroma at '{persist_directory}'")

def embedding_search(query: str, persist_directory="./chroma_db", top_k=5):
    embedding_model = SentenceTransformerEmbeddings(
        model_name="all-MiniLM-L6-v2"
    )

    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embedding_model
    )

    results = vectorstore.similarity_search(query, k=top_k)

    for i, doc in enumerate(results):
        print(f"Result {i + 1}: {doc.page_content}")

    return results


def delete_chromadb(persist_directory="./chroma_db"):
    if os.path.exists(persist_directory):
        shutil.rmtree(persist_directory)
        print(f"Chroma DB at '{persist_directory}' has been deleted.")
    else:
        print("Chroma DB directory does not exist.")