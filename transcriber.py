import os
# Suppress huggingface_hub symlink warning on windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import numpy as np
from faster_whisper import WhisperModel
import config

class AudioTranscriber:
    def __init__(self, model_size="base.en", device="cpu", compute_type="int8"):
        """
        Initializes the faster-whisper model.
        Using base.en for a good balance of accuracy and speed.
        """
        print(f"Loading faster-whisper model '{model_size}' on {device.upper()}...")
        # Load the model with specified compute type (int8 is faster and uses less memory on CPU)
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("Model loaded successfully.")

    def transcribe_chunk(self, audio_chunk_bytes):
        """
        Transcribes a raw audio chunk (16-bit PCM numpy array bytes).
        Returns the transcribed text as a string.
        """
        if not audio_chunk_bytes:
            return ""

        # Convert raw bytes back to 16-bit integer numpy array
        audio_array = np.frombuffer(audio_chunk_bytes, dtype=np.int16)
        
        # Whisper model expects mono audio at 16kHz as a float32 NumPy array normalized between -1.0 and 1.0
        audio_float32 = audio_array.astype(np.float32) / 32768.0
        audio_float32 = audio_float32.flatten() # Ensure 1D

        try:
            # Transcribe the audio
            # condition_on_previous_text=False is recommended for short chunk loops so the model doesn't hallucinate based on past chunks.
            segments, info = self.model.transcribe(
                audio_float32, 
                beam_size=5, 
                language="en", 
                condition_on_previous_text=False,
                vad_filter=True, # Prevent hallucinating background noise
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            text = " ".join([segment.text for segment in segments]).strip()
            return text
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""
