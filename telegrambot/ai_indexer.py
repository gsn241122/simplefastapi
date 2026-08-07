import os
import time
import logging
import threading
import chromadb
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_python as tspy

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # skip file > 2MB, biasanya bukan source code wajar


class CodebaseManager:
    def __init__(self, workspace_dir=None, db_path="code_db", ignore_dirs=None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.db_path = os.path.join(self.workspace_dir, db_path)
        self.ignore_dirs = ignore_dirs or {
            '.git', '__pycache__', 'venv', '.venv', '.env', 'node_modules',
            'dist', 'code_db', 'migrations', '.pytest_cache'
        }

        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(name="symbol_index")

        # Inisialisasi Parser dan Language
        self.language = Language(tspy.language())
        self.parser = Parser(self.language)

        # Query untuk ekstraksi simbol
        self.query = Query(self.language, """
            (function_definition name: (identifier) @name) @def
            (class_definition name: (identifier) @name) @def
        """)

        # PERBAIKAN: pada tree-sitter versi terbaru, QueryCursor menerima
        # `query` di constructor, dan .captures(node) mengembalikan
        # dict {capture_name: [Node, ...]} — bukan list of (node, index).
        self.cursor = QueryCursor(self.query)

        # Lock supaya index thread-safe (watcher berjalan di thread lain)
        self._lock = threading.Lock()

        logger.info(f"CodebaseManager diinisialisasi pada: {self.workspace_dir}")

    def _normalize_path(self, file_path):
        """Selalu simpan path absolut supaya konsisten antara initial scan,
        watcher event, dan pemanggilan get_context/file_filter."""
        return os.path.abspath(file_path)

    def _index_file(self, file_path):
        file_path = self._normalize_path(file_path)

        if not os.path.exists(file_path):
            return

        try:
            if os.path.getsize(file_path) > MAX_FILE_SIZE_BYTES:
                logger.warning(f"Melewati {file_path}: ukuran file melebihi batas.")
                return

            # errors="replace" agar file dengan encoding tidak murni UTF-8
            # tidak membuat seluruh proses indexing gagal
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                code = f.read()

            tree = self.parser.parse(bytes(code, "utf-8"))
            captures = self.cursor.captures(tree.root_node)  # dict: {name: [nodes]}

            documents, metadatas, ids = [], [], []

            for node in captures.get("def", []):
                symbol_text = code[node.start_byte:node.end_byte]
                documents.append(symbol_text)
                metadatas.append({"file": file_path, "symbol": "definition"})
                ids.append(f"{file_path}:{node.start_byte}")

            with self._lock:
                # Hapus entri lama file ini dulu, baru masukkan yang baru
                self.collection.delete(where={"file": file_path})
                if ids:
                    self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

            if ids:
                logger.info(f"Berhasil mengindeks {len(ids)} simbol di {os.path.basename(file_path)}")

        except Exception as e:
            logger.error(f"Gagal memproses {file_path}: {e}")

    def _remove_file(self, file_path):
        """Hapus semua entri index milik file yang dihapus/dipindah."""
        file_path = self._normalize_path(file_path)
        try:
            with self._lock:
                self.collection.delete(where={"file": file_path})
            logger.info(f"Menghapus index untuk file: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"Gagal menghapus index {file_path}: {e}")

    def get_context(self, user_query, n_results=3, file_filter=None):
        where_clause = {"file": self._normalize_path(file_filter)} if file_filter else None
        results = self.collection.query(
            query_texts=[user_query],
            n_results=n_results,
            where=where_clause
        )

        context = "### Context dari Codebase:\n"
        docs = results.get('documents', [[]])[0]
        metas = results.get('metadatas', [[]])[0]

        for doc, meta in zip(docs, metas):
            context += f"\nFile: {meta['file']} | Symbol: {meta['symbol']}\n{doc}\n"
        return context

    def _is_ignored(self, path):
        parts = os.path.normpath(path).split(os.sep)
        return any(p in self.ignore_dirs for p in parts)

    def start_watcher(self):
        manager = self

        class Handler(FileSystemEventHandler):
            def on_modified(self, event):
                if not event.is_directory and event.src_path.endswith('.py') and not manager._is_ignored(event.src_path):
                    manager._index_file(event.src_path)

            def on_created(self, event):
                if not event.is_directory and event.src_path.endswith('.py') and not manager._is_ignored(event.src_path):
                    manager._index_file(event.src_path)

            def on_deleted(self, event):
                if not event.is_directory and event.src_path.endswith('.py') and not manager._is_ignored(event.src_path):
                    manager._remove_file(event.src_path)

            def on_moved(self, event):
                if event.src_path.endswith('.py') and not manager._is_ignored(event.src_path):
                    manager._remove_file(event.src_path)
                if getattr(event, "dest_path", "").endswith('.py') and not manager._is_ignored(event.dest_path):
                    manager._index_file(event.dest_path)

        # Initial scan
        for root, dirs, files in os.walk(self.workspace_dir):
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            for file in files:
                if file.endswith(".py"):
                    self._index_file(os.path.join(root, file))

        observer = Observer()
        observer.schedule(Handler(), self.workspace_dir, recursive=True)
        observer.start()
        logger.info("Watcher aktif memantau perubahan file...")

        # Dikembalikan supaya caller bisa observer.stop() / observer.join()
        return observer


if __name__ == "__main__":
    manager = CodebaseManager()
    observer = manager.start_watcher()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        logger.info("Watcher dihentikan.")