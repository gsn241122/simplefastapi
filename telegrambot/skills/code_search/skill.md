# Skill: Code Search

## Deskripsi
`code_search` memungkinkan Anda mencari di dalam codebase dengan dua mode berbeda.

## Cara Penggunaan

### 1. Mode Analisis (Ask About Code) - Default
Memberikan jawaban yang telah dianalisis oleh AI berdasarkan konteks kode yang ditemukan.
`/code_search <pertanyaan_anda>`

**Contoh:**
`/code_search bagaimana fungsi _acquire_lock bekerja?`

### 2. Mode Mentah (Original Search)
Menampilkan cuplikan kode mentah langsung dari database tanpa filter analisis AI.
`/code_search --raw <kata_kunci>`

**Contoh:**
`/code_search --raw _acquire_lock`

## Manfaat
- **Fleksibilitas:** Pilih antara jawaban cepat (analisis) atau data mentah (verifikasi).
- **Akurasi:** Menggunakan `AgentIndexer` untuk hasil yang lebih cerdas.
- **Navigasi:** Memudahkan eksplorasi proyek tanpa harus membuka file secara manual.
