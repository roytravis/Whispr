import sys
import threading
import keyboard
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from audio_capture import SystemAudioRecorder
from text_buffer import TextBuffer
from context_manager import ContextManager
from qwen_client import QwenClient
from overlay_ui import OverlayWindow
from streaming_transcriber import StreamingTranscriber
import config


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    print("Initializing Parakeet Clone (Streaming Mode)...")

    # Initialize backend components
    recorder = SystemAudioRecorder()
    text_buffer = TextBuffer()
    context_manager = ContextManager()

    try:
        ai_client = QwenClient()
    except ValueError as e:
        print(f"\nInitialization Error: {e}")
        print("Please create a .env file with QWEN_API_KEY=your_key")
        sys.exit(1)

    if not recorder.default_speakers:
        print("Warning: No loopback audio device found. Transcription will not work.")

    # Create overlay window
    window = OverlayWindow()

    # ── Ask AI logic ──────────────────────────────────────

    def ask_ai():
        window.ai_thinking_signal.emit()
        threading.Thread(target=_ask_ai_worker, daemon=True).start()

    def _ask_ai_worker():
        transcript = text_buffer.get_full_transcript()
        text_buffer.clear()
        prompt = context_manager.get_prompt(transcript)
        response = ai_client.ask(prompt)
        window.ai_response_signal.emit(response.strip())

    def clear_all():
        text_buffer.clear()

    # ── Screenshot solve logic ────────────────────────────

    def screenshot_solve(image_bytes):
        threading.Thread(target=_screenshot_worker, args=(image_bytes,), daemon=True).start()

    def _screenshot_worker(image_bytes):
        prompt = context_manager.get_screenshot_prompt()
        response = ai_client.ask_with_image(prompt, image_bytes)
        window.ai_response_signal.emit(response.strip())

    window.on_ask_ai = ask_ai
    window.on_clear = clear_all
    window.on_screenshot_solve = screenshot_solve

    # ── Global hotkeys ────────────────────────────────────

    keyboard.add_hotkey('ctrl+enter', ask_ai)
    keyboard.add_hotkey('ctrl+shift+s', lambda: window.start_screenshot())

    # ── Streaming transcription ───────────────────────────

    streaming_transcriber = None

    def on_interim(text):
        text_buffer.set_interim(text)
        final_text, interim_text = text_buffer.get_display_text()
        window.interim_signal.emit(final_text, interim_text)

    def on_final(text):
        text_buffer.add_text(text)
        final_text, interim_text = text_buffer.get_display_text()
        window.interim_signal.emit(final_text, interim_text)

    def on_stream_error(error_msg):
        window.status_signal.emit(f"Error: {error_msg}")

    def on_stream_status(status):
        window.status_signal.emit(status)

    if recorder.default_speakers and config.ASSEMBLYAI_API_KEY:
        try:
            streaming_transcriber = StreamingTranscriber(
                on_interim=on_interim,
                on_final=on_final,
                on_error=on_stream_error,
                on_status=on_stream_status,
            )
            audio_stream = recorder.get_audio_stream()
            streaming_transcriber.start(audio_stream)
            window.status_signal.emit("Connecting...")
        except Exception as e:
            print(f"Streaming init failed: {e}, falling back to offline mode")
            window.status_signal.emit("Streaming Failed")
    elif recorder.default_speakers:
        # Fallback: offline mode with faster-whisper (original behavior)
        print("No ASSEMBLYAI_API_KEY — falling back to offline transcription")
        from transcriber import AudioTranscriber
        transcriber = AudioTranscriber(model_size="base.en")
        chunk_count = 0

        def process_audio_chunk(chunk, idx):
            transcript = transcriber.transcribe_chunk(chunk)
            if transcript:
                text_buffer.add_text(transcript)
                print(f"[{idx}] {transcript}")

        def audio_loop():
            nonlocal chunk_count
            for chunk in recorder.get_audio_chunks():
                chunk_count += 1
                t = threading.Thread(
                    target=process_audio_chunk,
                    args=(chunk, chunk_count),
                    daemon=True
                )
                t.start()

        audio_thread = threading.Thread(target=audio_loop, daemon=True)
        audio_thread.start()
        window.status_signal.emit("Recording (Offline)")

        # Periodic UI update for offline mode
        def update_transcript_ui():
            formatted = text_buffer.get_formatted_transcript()
            if formatted:
                window.transcript_signal.emit(formatted)

        transcript_timer = QTimer()
        transcript_timer.timeout.connect(update_transcript_ui)
        transcript_timer.start(2000)
    else:
        window.status_signal.emit("No Audio Device")

    # ── Show window & run ─────────────────────────────────

    window.show()
    exit_code = app.exec()

    # Cleanup
    if streaming_transcriber:
        streaming_transcriber.stop()
    recorder.stop()
    recorder.cleanup()
    keyboard.unhook_all()

    print("Application closed.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
