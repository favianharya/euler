```

░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓████████▓▒░▒▓███████▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓██████▓▒░ ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓██████▓▒░ ░▒▓███████▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░ ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓████████▓▒░░▒▓██████▓▒░░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░

```

# 🧠 RAG Pipeline with LangChain, HuggingFace, and FAISS

This project demonstrates how to build a **Retrieval-Augmented Generation (RAG) pipeline** using:

- [LangChain](https://www.langchain.com/)
- [HuggingFace Transformers](https://huggingface.co/)
- [FAISS](https://github.com/facebookresearch/faiss) for vector storage
- A simple **logging system** for monitoring

It supports loading datasets from both:

- **Hugging Face Hub datasets**
- **Local `.txt` files**

---

## 🚀 Features

- Load dataset from Hugging Face (`HuggingFaceDatasetLoader`)
- Load local text files (`TextLoader`)
- Split documents into smaller chunks for embeddings
- Generate embeddings with `HuggingFaceEmbeddings`
- Store and retrieve vectors using FAISS
- Save and reload FAISS indexes for faster future queries
- Basic logger to track pipeline events

---

## 📦 Installation and Run App

Make sure you have Python 3.9+ and create a virtual environment:

```bash
uv sync
source .venv/bin/activate

uv run main.py
```
