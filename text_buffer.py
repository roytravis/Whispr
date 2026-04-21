import time
import threading
import config


class TextBuffer:
    def __init__(self):
        self.buffer = []  # List of {'timestamp': float, 'text': str}
        self.current_interim = ""  # Interim text that can change
        self._lock = threading.Lock()

    def add_text(self, text):
        """Adds a finalized transcript segment."""
        clean_text = text.strip()
        if not clean_text:
            return

        with self._lock:
            self.buffer.append({
                'timestamp': time.time(),
                'text': clean_text
            })
            # Clear interim since it became final
            self.current_interim = ""
            self._cleanup_old_entries()

    def set_interim(self, text):
        """Sets the current interim (partial) transcript. Replaces previous interim."""
        with self._lock:
            self.current_interim = text.strip()

    def clear_interim(self):
        """Clears the interim text."""
        with self._lock:
            self.current_interim = ""

    def _cleanup_old_entries(self):
        """Removes entries older than BUFFER_MAX_AGE_MINUTES."""
        current_time = time.time()
        max_age_seconds = config.BUFFER_MAX_AGE_MINUTES * 60
        self.buffer = [
            entry for entry in self.buffer
            if (current_time - entry['timestamp']) <= max_age_seconds
        ]

    def clear(self):
        """Clears the entire text buffer and interim."""
        with self._lock:
            self.buffer = []
            self.current_interim = ""

    def get_full_transcript(self):
        """Returns full finalized transcript as a single string (for AI queries)."""
        with self._lock:
            self._cleanup_old_entries()
            return " ".join([entry['text'] for entry in self.buffer])

    def get_formatted_transcript(self):
        """Returns formatted transcript with timestamps. Final text only."""
        with self._lock:
            self._cleanup_old_entries()
            formatted_lines = []
            for entry in self.buffer:
                time_str = time.strftime("%H:%M:%S", time.localtime(entry['timestamp']))
                formatted_lines.append(f"[{time_str}] {entry['text']}")
            return "\n".join(formatted_lines)

    def get_display_text(self):
        """Returns tuple (final_text, interim_text) for UI rendering."""
        with self._lock:
            self._cleanup_old_entries()
            final_lines = []
            for entry in self.buffer:
                time_str = time.strftime("%H:%M:%S", time.localtime(entry['timestamp']))
                final_lines.append(f"[{time_str}] {entry['text']}")
            return "\n".join(final_lines), self.current_interim
