# Second Brain Semantic Search

A minimal local semantic search system for personal notes.

This project demonstrates the core pipeline behind a second brain / retrieval system:

```text
Notes → Chunk → Embed → Store
Query → Embed → Search → Return Top Results
```

## Setup

This project uses Conda for environment management.

Create the Conda environment:

```bash
conda create -n Personal-notes-RAG-system python=3.11

conda activate Personal-notes-RAG-system

pip install -r requirements.txt
```

## Running the Project

```bash
conda activate second-brain-search
```

# 1. Add notes

Add personal notes as .md or .txt files inside the notes/ folder.

For this first version, the project chunks notes by paragraph, so each paragraph becomes one searchable chunk.

# 2. Generate embeddings

Run the following command whenever new notes are added or existing notes are updated:

```bash
python src/embed_notes.py
```

This script will:

Read notes from the notes/ folder
Split them into paragraph chunks
Generate local embeddings using sentence-transformers
Save the chunks and embeddings into data/embeddings.json

The generated file will be stored here:

```text
data/embeddings.json
```

# 3. Search your notes

After generating embeddings, start the search program:

```bash
python src/search.py
```

The program will return the top matching chunks from your notes, including:

Similarity score
Source file name
Chunk number
Matching note text

To stop the program, type:

```text
exit
```
