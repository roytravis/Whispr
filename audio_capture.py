import pyaudiowpatch as pyaudio
import time
import numpy as np
from scipy import signal
import config

class SystemAudioRecorder:
    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        
        # Get default WASAPI info
        try:
            self.wasapi_info = self.pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            print("WASAPI is not available on this system.")
            self.wasapi_info = None
            
        self.default_speakers = None
        if self.wasapi_info:
            try:
                # Get default output device
                default_output = self.pa.get_device_info_by_index(self.wasapi_info["defaultOutputDevice"])
                
                # We need the corresponding loopback device
                if not default_output["isLoopbackDevice"]:
                    for loopback in self.pa.get_loopback_device_info_generator():
                        if default_output["name"] in loopback["name"]:
                            self.default_speakers = loopback
                            break
                else:
                    self.default_speakers = default_output
            except Exception as e:
                print(f"Error getting default speakers: {e}")

    def get_audio_chunks(self):
        """Generator that yields audio chunks of CHUNK_DURATION at config.SAMPLE_RATE"""
        if not self.default_speakers:
            print("No suitable loopback device found.")
            return

        self.is_recording = True

        native_rate = int(self.default_speakers["defaultSampleRate"])
        native_channels = int(self.default_speakers["maxInputChannels"])

        # Read in 100ms native chunks internally
        frames_per_buffer = int(native_rate * 0.1)

        try:
            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=native_channels,
                rate=native_rate,
                input=True,
                frames_per_buffer=frames_per_buffer,
                input_device_index=self.default_speakers["index"]
            )

            print(f"Started recording loopback from: {self.default_speakers['name']} (Native Rate: {native_rate}Hz, Channels: {native_channels})")

            target_chunk_samples = config.CHUNK_SIZE  # e.g., 16000 * 3 = 48000 samples
            current_audio_data = np.array([], dtype=np.int16)

            while self.is_recording:
                # Read audio data
                try:
                    data = self.stream.read(frames_per_buffer, exception_on_overflow=False)

                    # Convert to numpy array
                    audio_array = np.frombuffer(data, dtype=np.int16)

                    # Convert interleaved multichannel -> 2D -> average to mono -> 1D
                    if native_channels > 1:
                        audio_array = audio_array.reshape(-1, native_channels)
                        audio_array = np.mean(audio_array, axis=1).astype(np.int16)

                    # Resample to target config.SAMPLE_RATE (usually 16000)
                    if native_rate != config.SAMPLE_RATE:
                        audio_array = signal.resample_poly(audio_array, config.SAMPLE_RATE, native_rate).astype(np.int16)

                    current_audio_data = np.concatenate((current_audio_data, audio_array))

                    # Yield when we have enough samples for our chunk
                    if len(current_audio_data) >= target_chunk_samples:
                        chunk_to_yield = current_audio_data[:target_chunk_samples]
                        current_audio_data = current_audio_data[target_chunk_samples:]

                        yield chunk_to_yield.tobytes()

                except Exception as e:
                    print(f"Error reading/processing audio: {e}")
                    time.sleep(0.1)
        except Exception as e:
            print(f"Failed to open audio stream: {e}")
        finally:
            self._cleanup_stream()

    def get_audio_stream(self):
        """Generator that yields small audio chunks (~100ms) for real-time streaming.
        Unlike get_audio_chunks(), this does NOT accumulate — it yields immediately."""
        if not self.default_speakers:
            print("No suitable loopback device found.")
            return

        self.is_recording = True

        native_rate = int(self.default_speakers["defaultSampleRate"])
        native_channels = int(self.default_speakers["maxInputChannels"])

        frames_per_buffer = int(native_rate * 0.1)  # 100ms

        try:
            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=native_channels,
                rate=native_rate,
                input=True,
                frames_per_buffer=frames_per_buffer,
                input_device_index=self.default_speakers["index"]
            )

            print(f"Streaming loopback from: {self.default_speakers['name']} (Native Rate: {native_rate}Hz, Channels: {native_channels})")

            while self.is_recording:
                try:
                    data = self.stream.read(frames_per_buffer, exception_on_overflow=False)

                    audio_array = np.frombuffer(data, dtype=np.int16)

                    if native_channels > 1:
                        audio_array = audio_array.reshape(-1, native_channels)
                        audio_array = np.mean(audio_array, axis=1).astype(np.int16)

                    if native_rate != config.SAMPLE_RATE:
                        audio_array = signal.resample_poly(audio_array, config.SAMPLE_RATE, native_rate).astype(np.int16)

                    yield audio_array.tobytes()

                except Exception as e:
                    print(f"Error reading/processing audio: {e}")
                    time.sleep(0.1)
        except Exception as e:
            print(f"Failed to open audio stream: {e}")
        finally:
            self._cleanup_stream()

    def stop(self):
        self.is_recording = False
        
    def _cleanup_stream(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def cleanup(self):
        self._cleanup_stream()
        if self.pa:
            self.pa.terminate()
