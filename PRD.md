# PRD: Parakeet Clone — AI Interview & Meeting Assistant

## Overview

Aplikasi desktop Windows 10 yang berfungsi sebagai AI interview & meeting assistant, mirip Parakeet AI. Aplikasi menangkap audio system secara real-time, melakukan speech-to-text, dan memberikan jawaban AI berdasarkan konteks percakapan meeting saat diminta. Dilengkapi fitur CV dan Job Description agar AI memahami profil user dan posisi yang dilamar, sehingga dapat memberikan jawaban yang relevan saat interview.

---

## Problem Statement

Tidak ada alternatif gratis untuk Parakeet AI yang menyediakan kombinasi:
- Real-time audio listening
- AI Q&A instan berdasarkan konteks meeting/interview
- Hidden overlay (tidak terlihat saat screen sharing)
- Konteks personal (CV) dan posisi yang dilamar (Job Description)

Solusi: Bangun sendiri menggunakan open-source tools + Google Gemini API (gratis via Google AI Studio).

---

## Target User

- Pengguna pribadi (single user)
- Mengikuti meeting/interview di Google Meet, Zoom, Microsoft Teams
- Membutuhkan AI assistant yang mendengarkan dan siap menjawab kapan saja
- Membutuhkan bantuan AI saat technical/behavioral interview
- Bahasa meeting: English

---

## Functional Requirements

### FR-1: System Audio Capture
- Menangkap audio dari default output device (speaker/headphone) via WASAPI loopback
- Format: 16kHz, mono, 16-bit PCM
- Audio dipotong setiap 3 detik untuk dikirim ke speech-to-text
- Berjalan di background thread

### FR-2: Speech-to-Text (Real-time)
- Menggunakan `faster-whisper` secara lokal (gratis)
- Model: `base.en` (optimized untuk English)
- Menerima chunk audio 3 detik, mengembalikan teks
- Fallback: OpenAI Whisper API jika diperlukan akurasi lebih tinggi

### FR-3: Text Buffer (Rolling 5 Menit)
- Menyimpan hasil transkrip dengan timestamp
- Rolling window 5 menit — teks lebih lama otomatis dihapus
- Dapat di-clear manual oleh user

### FR-4: CV Profile
- User dapat memasukkan/paste CV dalam format teks via UI
- CV disimpan di file lokal (`cv.txt`) agar persist antar session
- Tombol **"Load CV"** di UI untuk import dari file `.txt` atau `.pdf`
- Tombol **"Edit CV"** untuk edit langsung di text area
- CV otomatis di-load saat aplikasi start
- AI menggunakan CV sebagai konteks untuk memahami:
  - Siapa user (nama, pengalaman, skills, education)
  - Project dan achievement yang bisa di-highlight
  - Cara menjawab pertanyaan behavioral ("Tell me about yourself", "Your greatest strength", dll)

### FR-5: Job Description
- User dapat memasukkan/paste Job Description via UI
- JD disimpan di file lokal (`jd.txt`) agar persist antar session
- Tombol **"Load JD"** di UI untuk import dari file
- Tombol **"Edit JD"** untuk edit langsung di text area
- AI menggunakan JD sebagai konteks untuk memahami:
  - Posisi apa yang dilamar
  - Requirements dan qualifications yang dicari
  - Tech stack yang relevan
  - Cara framing jawaban agar sesuai dengan job requirement

### FR-6: Gemini AI Integration
- Model: Gemini 2.5 Flash via Google AI Studio (gratis)
- Trigger: Hotkey **Ctrl+Enter** (global) ATAU klik tombol **"Ask AI"** di UI
- Mengirim konteks gabungan: **CV + Job Description + Transcript buffer 5 menit**
- System prompt disesuaikan untuk interview assistant:
  ```
  You are an AI interview assistant. You have the following context:
  
  1. CANDIDATE PROFILE (CV): [cv content]
  2. JOB DESCRIPTION: [jd content]  
  3. MEETING TRANSCRIPT (last 5 minutes): [transcript]
  
  Based on the interview conversation, help the candidate by:
  - Suggesting concise, relevant answers based on their CV and the job requirements
  - Highlighting relevant experience and skills that match the JD
  - Providing talking points for behavioral questions (STAR method)
  - Giving technical hints when relevant
  
  Keep answers brief and actionable — the candidate needs to respond quickly.
  ```
- Berjalan di background thread, UI menampilkan "Thinking..." saat menunggu

### FR-7: Overlay UI
- Panel always-on-top, draggable, resizable (~400x500px default)
- Posisi default: pojok kanan bawah layar
- **Tab-based UI** dengan 3 tab:
  - **Tab "Assistant"** — area utama:
    - Area teks scrollable (history jawaban AI)
    - Tombol **"Ask AI"** — trigger kirim buffer ke Gemini
    - Tombol **"Clear"** — reset buffer + history jawaban
    - Indikator status: Recording / Paused
  - **Tab "CV"** — manage CV:
    - Text area untuk edit/paste CV
    - Tombol **"Load File"** — import dari `.txt`/`.pdf`
    - Tombol **"Save"** — simpan ke `cv.txt`
    - Indikator: "CV Loaded ✓" atau "No CV"
  - **Tab "Job Description"** — manage JD:
    - Text area untuk edit/paste Job Description
    - Tombol **"Load File"** — import dari file
    - Tombol **"Save"** — simpan ke `jd.txt`
    - Indikator: "JD Loaded ✓" atau "No JD"
- Tombol **"Minimize"** — collapse panel (berlaku di semua tab)
- **Hidden dari screen share** menggunakan `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`

### FR-8: Global Hotkey
- **Ctrl+Enter** — kirim buffer ke Gemini (bekerja meskipun app tidak dalam fokus)

---

## Non-Functional Requirements

### NFR-1: Performance
- Speech-to-text latency: < 2 detik per chunk
- GPT response time: tergantung API (~2-5 detik)
- UI harus tetap responsif saat audio capture dan GPT request berjalan

### NFR-2: Scale
- Single user, single machine
- 1 meeting pada satu waktu

### NFR-3: Security / Privacy
- API key disimpan di file config lokal (tidak di-hardcode)
- Audio tidak disimpan ke disk — hanya di memory
- Transkrip hanya di memory buffer, hilang saat app ditutup atau di-clear

### NFR-4: Reliability
- Jika GPT API gagal, tampilkan error message di UI (bukan crash)
- Jika audio device tidak tersedia, tampilkan warning

### NFR-5: Maintenance
- Penggunaan pribadi, maintenance oleh user sendiri
- Dependency seminimal mungkin

---

## Architecture

### Data Flow

```
System Audio ──> Audio Capture ──> Whisper (lokal) ──> Text Buffer (5 min)
(Loopback)      (pyaudiowpatch)   (faster-whisper)         │
                                                            │
                              CV (cv.txt) ──────────────────┤
                                                            │ Ctrl+Enter / Click
                              JD (jd.txt) ──────────────────┤
                                                            ▼
                                                    Gemini 2.5 Flash API
                                                     (Google AI Studio)
                                                            │
                                                            ▼
                                                      Overlay UI (PyQt5)
```

### Tech Stack

| Komponen | Teknologi |
|---|---|
| Bahasa | Python |
| UI Framework | PyQt5 |
| Audio Capture | pyaudiowpatch (WASAPI loopback) |
| Speech-to-Text | faster-whisper (lokal, model base.en) |
| AI | Google Gemini 2.5 Flash via Google AI Studio (gratis) |
| Hotkey | keyboard / pynput |
| Hidden Overlay | Win32 API SetWindowDisplayAffinity |

### Project Structure

```
parakeet-clone/
├── main.py              # Entry point
├── audio_capture.py     # System audio loopback recording
├── transcriber.py       # Faster-whisper speech-to-text
├── text_buffer.py       # Rolling 5-min text buffer
├── gemini_client.py     # Google Gemini AI integration
├── context_manager.py   # Manages CV + JD + transcript context
├── overlay_ui.py        # PyQt5 overlay panel (tabbed UI)
├── hotkey_listener.py   # Global hotkey (Ctrl+Enter)
├── config.py            # API key, settings
├── cv.txt               # User's CV (persistent, gitignored)
├── jd.txt               # Job Description (persistent, gitignored)
└── requirements.txt     # Dependencies
```

---

## Decision Log

| # | Keputusan | Alternatif | Alasan |
|---|---|---|---|
| 1 | Python + PyQt5 | Electron, C#/WPF | Library AI/audio paling matang, faster-whisper lokal gratis |
| 2 | System audio capture (loopback) | Integrasi per-platform API | Lebih simpel, bekerja di semua platform sekaligus |
| 3 | pyaudiowpatch untuk audio | sounddevice, pyaudio | Native WASAPI loopback support di Windows |
| 4 | faster-whisper lokal | OpenAI Whisper API | Gratis, cepat, cukup akurat untuk English |
| 5 | Model Whisper base.en | tiny.en, small.en | Keseimbangan akurasi dan kecepatan |
| 6 | Gemini 2.5 Flash (Google AI Studio) | GPT-5.4, GPT-4o-mini, Local LLM | User punya akun Gemini Pro, free tier sangat generous (15 RPM), kualitas bagus |
| 7 | Rolling buffer 5 menit | 15/30 menit, full meeting | Hemat token API, konteks cukup untuk interview |
| 8 | SetWindowDisplayAffinity untuk hidden overlay | Share window spesifik | Solusi native Windows, pasti tersembunyi |
| 9 | Dual trigger: Ctrl+Enter + tombol UI | Hotkey saja | Fleksibilitas — keyboard dan mouse |
| 10 | Panel always-on-top draggable | Popup, tooltip, sidebar | Bisa minimize, ada history, posisi fleksibel |
| 11 | CV + JD sebagai konteks AI | Tanpa konteks personal | AI bisa memberikan jawaban yang personal dan relevan dengan posisi |
| 12 | Tab-based UI | Multiple windows, accordion | Compact, tetap dalam 1 overlay panel |
| 13 | CV/JD persist di file lokal | Database, cloud storage | Simpel, portable, mudah edit manual |

---

## Estimasi Biaya Operasional

| Komponen | Biaya |
|---|---|
| Audio capture | Gratis |
| Speech-to-text (faster-whisper lokal) | Gratis |
| Gemini 2.5 Flash API (Google AI Studio free tier) | **Gratis** |
| **Estimasi per interview/meeting** | **$0.00** |

> **Note:** Google AI Studio free tier: 15 RPM untuk Gemini 2.5 Flash. Untuk interview 1 jam dengan ~30 pertanyaan ke AI, masih jauh di bawah limit.

---

## Assumptions

1. User sudah memiliki Google account dengan akses ke Google AI Studio
2. Gemini 2.5 Flash tersedia di Google AI Studio free tier
3. Windows 10 mendukung `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`
4. Audio output device mendukung WASAPI loopback
5. Aplikasi untuk penggunaan pribadi, bukan distribusi
6. User menyediakan CV dalam format teks (bisa copy-paste atau file .txt)
7. User menyediakan Job Description sebelum interview dimulai

---

## Non-Goals

- Bukan untuk didistribusikan sebagai produk
- Tidak perlu multi-bahasa (English only)
- Tidak perlu menyimpan transkrip ke file
- Tidak perlu integrasi langsung ke Zoom/Meet/Teams API
- Tidak perlu fitur recording/playback

---

## Implementation Phases

### Fase 1: Setup & Audio Capture
- Inisialisasi project, virtual environment, dependencies
- Setup `config.py` — Google AI Studio API key, settings
- Implementasi `audio_capture.py` — system audio loopback via pyaudiowpatch
- **Deliverable:** Aplikasi bisa merekam system audio dan print raw audio data ke console

### Fase 2: Speech-to-Text
- Implementasi `transcriber.py` — integrasi faster-whisper (model base.en)
- Implementasi `text_buffer.py` — rolling window 5 menit dengan timestamp
- **Deliverable:** Aplikasi bisa menampilkan live transcription ke console

### Fase 3: Gemini AI + Context Integration
- Implementasi `gemini_client.py` — Google Gemini 2.5 Flash API call
- Implementasi `context_manager.py` — gabungkan CV + JD + transcript sebagai konteks
- Kirim konteks gabungan ke Gemini, terima jawaban
- **Deliverable:** Bisa kirim transkrip + CV + JD ke Gemini dan terima jawaban di console

### Fase 4: UI Overlay
- Implementasi `overlay_ui.py` — PyQt5 panel dengan tab-based UI
- **Tab "Assistant"**: area teks scrollable, tombol Ask AI, Clear, indikator status
- **Tab "CV"**: text area, Load File, Save
- **Tab "Job Description"**: text area, Load File, Save
- Always-on-top, draggable, resizable
- Hidden dari screen share (`SetWindowDisplayAffinity`)
- **Deliverable:** UI overlay berfungsi dengan 3 tab dan tersembunyi saat screen share

### Fase 5: Hotkey & Integration
- Implementasi `hotkey_listener.py` — Ctrl+Enter global hotkey
- Implementasi `main.py` — hubungkan semua komponen:
  - Audio Capture → Transcriber → Text Buffer ─┐
  - CV (file) ─────────────────────────────────┤→ Gemini → UI
  - JD (file) ─────────────────────────────────┘
- **Deliverable:** Aplikasi end-to-end berfungsi penuh

### Fase 6: Testing & Polish
- Test end-to-end dengan interview/meeting sungguhan (Google Meet, Zoom, Teams)
- Test hidden overlay saat screen sharing
- Test CV + JD context — pastikan AI memberikan jawaban yang personal
- Fix bugs, fine-tune prompt engineering
- **Deliverable:** Aplikasi siap digunakan sehari-hari untuk interview
