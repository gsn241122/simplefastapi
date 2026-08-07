import sys
import os

# Menambahkan path ke direktori bot agar bisa mengimpor agent_indexer
sys.path.append("/home/dell/Desktop/workspace/simplefastapi/telegrambot")

from agent_indexer import AgentIndexer

def execute(query: str):
    """
    Menjalankan pencarian kode dengan dua mode:
    1. '/code_search --raw <query>' : Menampilkan hasil mentah dari database (Original Search)
    2. '/code_search <query>'        : Menganalisis kode menggunakan LLM (Ask About Code)
    """
    try:
        # Deteksi mode
        if query.startswith("--raw "):
            raw_query = query.replace("--raw ", "").strip()
            return _original_search(raw_query)
        else:
            return _ask_about_code(query)
            
    except Exception as e:
        return f"⚠️ Terjadi kesalahan: {str(e)}"

def _original_search(query: str):
    """Mode Original Search: Mengambil data mentah dari ChromaDB"""
    # Menggunakan tool yang tersedia di environment untuk akses Chroma
    # Karena kita sudah terhubung ke code_db_chroma, kita bisa memanggilnya langsung
    from mcp_agent.client import mcp_client
    
    results = mcp_client.call_tool("code_db_chroma", "query_documents", {"query_texts": [query], "n_results": 3})
    
    if not results or "documents" not in results:
        return "❌ Tidak ditemukan hasil mentah untuk query tersebut."
        
    output = f"🔍 **Original Search: '{query}'**\n\n"
    for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0]), 1):
        output += f"{i}. 📄 *File*: {meta.get('file', 'unknown')}\n"
        output += f"   ```python\n{doc[:200]}...\n```\n\n"
    return output

def _ask_about_code(query: str):
    """Mode Ask About Code: Menganalisis kode dengan LLM via AgentIndexer"""
    indexer = AgentIndexer()
    result = indexer.ask_about_code(query)
    return f"🤖 **Analisis AI:**\n\n{result}"
