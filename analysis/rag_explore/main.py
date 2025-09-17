
from langchain_community.document_loaders import HuggingFaceDatasetLoader, TextLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

import logging
logger = logging.getLogger(__name__)

def setup_logger():
    """
    setup the logger with a stream handler and formatter
    """

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        console_handler = logging.StreamHandler()
        log_format = "%(asctime)s | %(levelname)s: %(message)s"
        console_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(console_handler)

setup_logger()

class DatasetPreparation:
    def __init__(
        self, 
        dataset_name: str = None,       
        page_content_column: str = None,
        txt_path: str = None,          
        chunk_size: int = 1000,
        chunk_overlap: int = 150
    ):
        self.dataset_name = dataset_name
        self.page_content_column = page_content_column
        self.txt_path = txt_path
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def load_hf_dataset(self):
        """
        Load a dataset from the Hugging Face Hub using HuggingFaceDatasetLoader.
        """
        logger.info("📥 Load dataset from Hugging Face Hub")
        loader = HuggingFaceDatasetLoader(self.dataset_name, self.page_content_column)
        logger.info(f"✅ Dataset '{self.dataset_name}' loaded successfully")
        return loader.load()

    def load_txt_dataset(self):
        """
        Load documents from a local text file using TextLoader.
        """
        logger.info(f"📥 Load dataset from local text file: {self.txt_path}")
        loader = TextLoader(self.txt_path, encoding="utf-8")
        logger.info(f"✅ Text file '{self.txt_path}' loaded successfully")
        return loader.load()

    def split_texts(self, texts):
        """
        Split documents into smaller chunks using RecursiveCharacterTextSplitter.
        """
        logger.info("✂️  Splitting documents into smaller chunks")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
        return text_splitter.split_documents(texts)

    def prepare(self):
        """
        Prepare dataset (either Hugging Face dataset or local txt file).
        """
        if self.txt_path:
            logger.info("📃 Using local text file for dataset preparation")
            data = self.load_txt_dataset()
        else:
            logger.info("😀 Using Hugging Face dataset for dataset preparation")
            data = self.load_hf_dataset()
        
        docs = self.split_texts(data)
        logger.info(f"✅ Dataset preparation completed with {len(docs)} chunks")
        return docs

class VectorStore:
    def __init__(self, model_name: str):
        self.model_name = model_name
    
    def embed(self):
        """
        Initialize and return a HuggingFaceEmbeddings object.
        """
        logger.info(f"🧠 Initializing embeddings with model: {self.model_name}")
        model_kwargs = {'device':'cpu'}
        encode_kwargs = {'normalize_embeddings': False}
        return HuggingFaceEmbeddings(
            model_name=self.model_name,    
            model_kwargs=model_kwargs, 
            encode_kwargs=encode_kwargs 
        )
    
    def stored_to_vector(self, docs):
        """
        Convert a list of documents into a FAISS vector store.
        """
        logger.info("⚡ Converting documents to vector store using FAISS")
        embedding = self.embed()
        return FAISS.from_documents(docs, embedding)

    def save(
        self, 
        vector_db, 
        vector_name: str
    ):
        """
        Save the FAISS vector store to local disk.
        """
        logger.info(f"💾 Saving vector store locally as: vector_db/{vector_name}")
        rag_path = f"vector_db/{vector_name}"
        vector_db.save_local(rag_path)

    def load(self, 
        vector_name: str
    ):
        """
        Load a previously saved FAISS vector store from local disk.
        """
        logger.info(f"📂 Loading vector store from: vector_db/{vector_name}")
        rag_path = f"vector_db/{vector_name}"
        embedding = self.embed()
        return FAISS.load_local(rag_path, embedding, allow_dangerous_deserialization=True)

def main():

    embeddings = VectorStore(model_name='sentence-transformers/all-MiniLM-L6-v2')
    data_preparation=DatasetPreparation(
        dataset_name='databricks/databricks-dolly-15k', 
        page_content_column='context'   
    )
    data = data_preparation.prepare()
    vector_db=embeddings.stored_to_vector(data)
    embeddings.save(vector_db, vector_name="databricks_dolly_15k")

    question = "What is cheesemaking?"
    searchDocs = vector_db.similarity_search(question)
    print(searchDocs[0].page_content)

if __name__ == "__main__":
    main()
