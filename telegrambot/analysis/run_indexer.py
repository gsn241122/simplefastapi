import time
import logging
from ai_indexer import CodebaseManager

# Setup Logging agar terlihat di terminal
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    # Inisialisasi Manager
    manager = CodebaseManager(workspace_dir="/home/dell/Desktop/workspace/simplefastapi/telegrambot/")
    
    # Mulai memantau perubahan file
    manager.start_watcher()
    
    print("🚀 Indexer sedang berjalan. Tekan Ctrl+C untuk berhenti.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Indexer dihentikan.")
