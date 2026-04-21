# 🎙️ Whispr

> AI-powered stealth interview assistant — listens to your conversation, remembers context, and whispers smart answers in real-time. Invisible to screen share.

## Features

- **Real-time Audio Capture** — Captures system audio (loopback) to listen to your interview
- **Live Transcription** — Converts speech to text using AssemblyAI streaming or offline Whisper
- **AI-Powered Answers** — Generates context-aware responses based on your CV, Job Description, and conversation
- **Screenshot Solver** — Capture coding problems on screen and get instant solutions
- **Stealth Mode** — Hidden from screen sharing tools (Windows Display Affinity API)
- **Always-on-Top Overlay** — Frameless, draggable window that stays on top of everything

## Tech Stack

- **Python 3.12+** with PyQt6 for the overlay UI
- **AssemblyAI** for real-time speech-to-text
- **Qwen / Gemini** for AI response generation
- **SoundCard** for system audio capture
- **PyMuPDF** for PDF parsing (CV upload)

## Quick Start

### 1. Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### 2. Setup

```powershell
# Clone the repository
git clone https://github.com/roytravis/Whispr.git
cd Whispr

# Create virtual environment and install dependencies
uv venv
uv pip install -r requirements.txt
```

### 3. Configure

Create a `.env` file from the template:

```powershell
cp .env.template .env
```

Fill in your API keys:
```env
QWEN_API_KEY=your_qwen_api_key
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
```

### 4. Run

```powershell
uv run python main.py
```

Or use the provided script:
```powershell
.\run.ps1
```

## Usage

1. **Load your CV** — Go to the "CV" tab and paste/upload your resume
2. **Load the JD** — Go to the "Job Desc" tab and paste the job description
3. **Start your interview** — The app will automatically transcribe audio
4. **Press `Ctrl+Enter`** or click "Ask AI" to get suggested answers
5. **Press `Ctrl+Shift+S`** to screenshot and solve coding problems
6. **Click "Clear"** to reset everything and start a new interview session

## License

MIT
