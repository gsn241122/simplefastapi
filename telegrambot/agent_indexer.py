import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
import chromadb

# Load environment variables
load_dotenv()

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AgentIndexer:
    def __init__(self):
        # Ambil konfigurasi dari .env
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.base_url = os.getenv("GEMINI_BASE_URL")
        self.model = os.getenv("GEMINI_MODEL")
        
        # Inisialisasi Client OpenAI (compatible dengan Gemini API)
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Inisialisasi ChromaDB
        self.db_path = os.path.join(os.getcwd(), "code_db")
        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.chroma_client.get_or_create_collection(name="symbol_index")
        
        logger.info(f"AgentIndexer siap menggunakan model: {self.model}")

    def analyze_code(self, symbol_name, code_content):
        """Menggunakan Gemini untuk menganalisis kode yang diindeks."""
        prompt = f"""
        Analisis fungsi atau kelas berikut dan berikan ringkasan singkat dalam bahasa Indonesia:
        Nama: {symbol_name}
        Kode:
        {code_content}
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Anda adalah asisten AI ahli pemrograman."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Gagal menganalisis kode dengan Gemini: {e}")
            return None

    def process_all_symbols(self):
        """Mengambil semua simbol dari ChromaDB dan menganalisisnya."""
        results = self.collection.get()
        documents = results.get('documents', [])
        metadatas = results.get('metadatas', [])
        
        for i, doc in enumerate(documents):
            symbol = metadatas[i].get('symbol', 'unknown')
            logger.info(f"Menganalisis simbol: {symbol}")
            analysis = self.analyze_code(symbol, doc)
            if analysis:
                print(f"\n--- Analisis {symbol} ---\n{analysis}\n")
    
    def ask_about_code(self, query_text):
        """Melakukan pencarian relevansi di ChromaDB dan bertanya ke Gemini."""
        # Hanya ambil 3 hasil teratas yang paling relevan
        results = self.collection.query(
            query_texts=[query_text],
            n_results=3
        )
        
        if not results['documents'] or not results['documents'][0]:
            return "Maaf, tidak ada konteks kode yang relevan ditemukan untuk pertanyaan tersebut."

        # Gabungkan hasil untuk dikirim ke Gemini
        context = "\n\n".join(results['documents'][0])
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Anda adalah asisten ahli coding. Jawab pertanyaan berdasarkan konteks kode yang diberikan."},
                    {"role": "user", "content": f"Konteks kode:\n{context}\n\nPertanyaan: {query_text}"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Gagal bertanya ke Gemini: {e}")
            return "Terjadi kesalahan saat menghubungi model AI."

if __name__ == "__main__":
    import sys
    indexer = AgentIndexer()
    # indexer.process_all_symbols()
        
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Jelaskan fungsi utama dari codebase ini."
    print(f"Hasil Analisis: \n{indexer.ask_about_code(query)}")
    # sample penggunaan: python agent_indexer.py "Bagaimana cara kerja fungsi weather di project ini?"