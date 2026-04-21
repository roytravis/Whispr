# Desain Spesifikasi Eksekusi & Skill Mapping (Parakeet Clone)

## 1. Understanding Summary
*   **What is being built:** Aplikasi desktop Windows 10 (Parakeet Clone) sebagai asisten AI untuk *interview* yang memanfaatkan rekam audio sistem secara *real-time*, *speech-to-text* lokal (`faster-whisper`), dan Google Gemini 2.5 Flash API yang dikemas melalui UI *overlay* (PyQt5).
*   **Why it exists:** Memberikan alternatif gratis untuk layanan Parakeet AI untuk membantu menjawab pertanyaan saat *interview* tanpa ketahuan (overlay disembunyikan saat *screen sharing*), dengan konteks mandiri dari profil (CV) dan kriteria pekerjaan (JD).
*   **Who it is for:** Pengguna individu tipe *single-machine* untuk antarmuka wawancara (Meet, Zoom, Teams).
*   **Key constraints:** Latensi sangat rendah (< 2 etik rekam STT), model lokal, free tier AI Studio API, *5-minutes rolling memory*, dan fungsi *shortcut keyboard* di luar layar.
*   **Explicit non-goals:** Tidak menargetkan distribusi publik, tidak mendukung multi-bahasa selain bahasa Inggris, tidak ada histori sesi di _storage_, tidak di-hook ke API Meet/Zoom.

## 2. Assumptions
*   Eksplorasi berfokus secara eksklusif pada tumpukan Python murni, manajemen OS Windows (Win32 API), STT, dan panggilan HTTP API dengan asumsi *resource* komputer pengguna mampu mengangkat Threading bersama STT `faster-whisper` lokal di dalam siklus UI.

## 3. Decision Log Akhir
| # | Keputusan | Alternatif | Alasan |
|---|---|---|---|
| 1 | Pendekatan Desain Sistem: **Lean & Direct Strategy** | *Asynchronous Event-Driven Pipeline* | Metode "Lean" mempertahankan kompleksitas kode seminimum mungkin dengan prinsip YAGNI (mengurangi *over-engineering* untuk kasus *single-user*). |
| 2 | Injeksi **Prompt Engineering Skill** | *Gemini Integration* Bawaan | Rekayasa intruksi (Prompt) jauh lebih vital di arsitektur asisten ini untuk merekatkan komponen JD dan CV tanpa merusak *sliding memory* dibanding integrasi LLM *state-of-the-art*. |

---

## 4. Skill Assignments per Implementation Phase

### Fase 1: Setup & Audio Capture
*(Skills Utama: `python-pro`, `windows-shell-reliability`)*
*   Memandu struktur hirarki file.
*   Pemanggilan dan *hook* khusus pada audio endpoint WASAPI di Windows agar tidak berebut sumber daya audio dengan OS.

### Fase 2: Speech-to-Text & Data Buffer
*(Skills Utama: `audio-transcriber`, `python-pro`)*
*   Optimasi parameter pada model `base.en` Whisper terkait pendeteksian jeda *silence* (VAD).
*   Penerapan model relasional *timestamp* dan struktur siklus `collections.deque` terisolasi-thread untuk manajemen bufer 5 menit.

### Fase 3: Gemini AI + Context Integration
*(Skills Utama: `gemini-api-dev`, `prompt-engineering-patterns`)*
*   Pembangunan permintaan *Context-Window* gabungan CV + JD yang ringkas (sistem tidak kelebihan token).
*   *Prompt engineering* agar Gemini merespons layaknya "kisi-kisi".

### Fase 4: UI Overlay
*(Skills Utama: `python-pro`, `windows-shell-reliability`)*
*   Membangun struktur UI PyQt5 (tabulasi dan signal routing) dalam kelas-kelas OOP.
*   Menjalankan fitur persembunyian *User Interface* (`SetWindowDisplayAffinity`) memakai komponen Win32 (C++) yang di-bungkus di dalam Pustaka Standar Python.

### Fase 5: Hotkey & Integration
*(Skills Utama: `python-pro`, `windows-shell-reliability`)*
*   Orkestrasi multiutas *(Advanced Threading)* antar UI, Mikrofon, Perekam *Shortcut*, dan Modul API agar program berjalan reaktif tanpa *input delay*.
*   Membangun jalur penghentian program *(Exit hook)* yang bersih karena pencegat kursor global sering dimatikan paksa *(force kill)* oleh Windows.

### Fase 6: Testing & Polish
*(Skills Utama: `python-testing-patterns`, `prompt-engineering-patterns`)*
*   Validasi keandalan integrasi *(error handlers)* jika token limit terlampaui.
*   Modifikasi iteratif perintah sistem (*system prompt*) setelah pengujian lapangan langsung di Meeting App.
