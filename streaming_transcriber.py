import threading
from typing import Type

from assemblyai.streaming.v3 import (
    BeginEvent,
    SpeechModel,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    TerminationEvent,
    TurnEvent,
)
import config


class StreamingTranscriber:
    """Real-time streaming transcriber using AssemblyAI's Universal Streaming API."""

    def __init__(self, on_interim=None, on_final=None, on_error=None, on_status=None):
        """
        Args:
            on_interim: Callback(text) for partial/interim transcripts
            on_final:   Callback(text) for finalized transcripts
            on_error:   Callback(error_str) for errors
            on_status:  Callback(status_str) for status updates
        """
        if not config.ASSEMBLYAI_API_KEY:
            raise ValueError("ASSEMBLYAI_API_KEY not set in .env")

        self._on_interim = on_interim
        self._on_final = on_final
        self._on_error = on_error
        self._on_status = on_status
        self._client = None
        self._thread = None

    def _handle_begin(self, client: Type[StreamingClient], event: BeginEvent):
        print(f"AssemblyAI session started: {event.id}")
        if self._on_status:
            self._on_status("Streaming")

    def _handle_turn(self, client: Type[StreamingClient], event: TurnEvent):
        text = event.transcript.strip() if event.transcript else ""
        if not text:
            return

        if event.end_of_turn:
            if self._on_final:
                self._on_final(text)
        else:
            if self._on_interim:
                self._on_interim(text)

    def _handle_terminated(self, client: Type[StreamingClient], event: TerminationEvent):
        print(f"AssemblyAI session ended: {event.audio_duration_seconds:.1f}s processed")
        if self._on_status:
            self._on_status("Disconnected")

    def _handle_error(self, client: Type[StreamingClient], error: StreamingError):
        error_msg = str(error)
        print(f"AssemblyAI error: {error_msg}")
        if self._on_error:
            self._on_error(error_msg)

    def start(self, audio_stream):
        """Start streaming transcription in a background thread.

        Args:
            audio_stream: Iterable that yields raw PCM16 audio bytes (16kHz mono)
        """
        self._client = StreamingClient(
            StreamingClientOptions(
                api_key=config.ASSEMBLYAI_API_KEY,
                api_host="streaming.assemblyai.com",
            )
        )

        self._client.on(StreamingEvents.Begin, self._handle_begin)
        self._client.on(StreamingEvents.Turn, self._handle_turn)
        self._client.on(StreamingEvents.Termination, self._handle_terminated)
        self._client.on(StreamingEvents.Error, self._handle_error)

        self._client.connect(
            StreamingParameters(
                sample_rate=config.SAMPLE_RATE,
                speech_model=SpeechModel.universal_streaming_multilingual,
                format_turns=True,
            )
        )

        def _stream_loop():
            try:
                self._client.stream(audio_stream)
            except Exception as e:
                print(f"Streaming error: {e}")
                if self._on_error:
                    self._on_error(str(e))
            finally:
                try:
                    self._client.disconnect(terminate=True)
                except Exception:
                    pass

        self._thread = threading.Thread(target=_stream_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the streaming session."""
        if self._client:
            try:
                self._client.disconnect(terminate=True)
            except Exception:
                pass
            self._client = None
