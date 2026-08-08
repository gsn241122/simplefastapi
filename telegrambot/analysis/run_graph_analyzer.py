import argparse
import json
import sys

import chromadb
from graph_analyzer import GraphAnalyzer


def get_all_code_from_chroma(db_path: str, collection_name: str) -> list[dict]:
    """
    Ambil semua dokumen kode + metadata dari koleksi Chroma.
    Melempar RuntimeError dengan pesan yang jelas jika client/koleksi gagal dibuka.
    """
    try:
        client = chromadb.PersistentClient(path=db_path)
    except Exception as e:
        raise RuntimeError(f"Gagal membuka Chroma DB di '{db_path}': {e}") from e

    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        raise RuntimeError(
            f"Koleksi '{collection_name}' tidak ditemukan di '{db_path}': {e}"
        ) from e

    results = collection.get(include=["documents", "metadatas"])

    data = []
    documents = results.get("documents") or []
    metadatas = results.get("metadatas") or []

    for doc, meta in zip(documents, metadatas):
        if not doc:
            continue  # skip dokumen kosong/None
        if not meta or "file" not in meta:
            print(f"  [skip] metadata tidak lengkap (tidak ada 'file'): {meta}", file=sys.stderr)
            continue
        data.append({"content": doc, "metadata": meta})

    return data


def build_graph(analyzer: GraphAnalyzer, docs: list[dict]) -> None:
    """Proses setiap dokumen; satu dokumen gagal tidak menghentikan yang lain."""
    total = len(docs)
    ok, failed = 0, 0

    for i, doc in enumerate(docs, start=1):
        file_path = doc["metadata"]["file"]
        try:
            analyzer.analyze_code_structure(doc["content"], file_path)
            ok += 1
        except Exception as e:
            failed += 1
            print(f"  [gagal] {file_path}: {e}", file=sys.stderr)

        if i % 50 == 0 or i == total:
            print(f"  Progres: {i}/{total} ({ok} ok, {failed} gagal)")


def main():
    parser = argparse.ArgumentParser(description="Analisis graf pemanggilan fungsi dari kode di Chroma DB.")
    parser.add_argument("--db-path", default="../code_db", help="Path ke Chroma PersistentClient (default: code_db)")
    parser.add_argument("--collection", default="symbol_index", help="Nama koleksi Chroma (default: symbol_index)")
    parser.add_argument("--target", default=None, help="Nama fungsi untuk analisis dampak (impact analysis)")
    parser.add_argument("--chain-from", default=None, help="Node awal untuk mencari call chain")
    parser.add_argument("--chain-to", default=None, help="Node akhir untuk mencari call chain")
    parser.add_argument("--export", default=None, help="Path file JSON untuk menyimpan graf hasil analisis")
    args = parser.parse_args()

    print(f"Mengambil data dari Chroma ({args.db_path} / {args.collection})...")
    try:
        all_docs = get_all_code_from_chroma(args.db_path, args.collection)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not all_docs:
        print("Tidak ada dokumen kode yang valid ditemukan. Berhenti.")
        sys.exit(0)

    print(f"Memproses {len(all_docs)} potongan kode...")
    analyzer = GraphAnalyzer()
    build_graph(analyzer, all_docs)

    print(f"\nGraf selesai dibangun: {analyzer.graph.number_of_nodes()} node, "
          f"{analyzer.graph.number_of_edges()} edge.")

    if args.target:
        print(f"\nAnalisis dampak untuk: {args.target}")
        impact = analyzer.get_impact_analysis(args.target)
        if not impact["affected_by"] and not impact["affects"] and args.target not in analyzer.graph:
            print(f"  Peringatan: '{args.target}' tidak ditemukan di graf.")
        print(json.dumps(impact, indent=2, ensure_ascii=False))

    if args.chain_from and args.chain_to:
        print(f"\nMencari call chain: {args.chain_from} -> {args.chain_to}")
        chain = analyzer.get_call_chain(args.chain_from, args.chain_to)
        if chain is None:
            print("  Tidak ditemukan jalur pemanggilan di antara keduanya.")
        else:
            print("  " + " -> ".join(chain))

    if args.export:
        with open(args.export, "w", encoding="utf-8") as f:
            json.dump(analyzer.export_graph(), f, indent=2, ensure_ascii=False)
        print(f"\nGraf diekspor ke {args.export}")


if __name__ == "__main__":
    main()