import os


class ContextManager:
    def __init__(self, cv_path="cv.txt", jd_path="jd.txt"):
        self.cv_path = cv_path
        self.jd_path = jd_path
        # Conversation memory: stores pairs of {transcript, response}
        self.conversation_history = []
        self.max_history_chars = 8000  # ~2000 tokens budget for history

    def read_file(self, path):
        """Reads and returns the content of the file if it exists."""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as e:
                print(f"Error reading {path}: {e}")
        return ""

    def add_to_history(self, transcript, ai_response):
        """Store a transcript + AI response pair into conversation history."""
        self.conversation_history.append({
            "transcript": transcript.strip(),
            "response": ai_response.strip()
        })

    def clear_history(self):
        """Clear all conversation history — called when user clicks Clear."""
        self.conversation_history = []

    def _build_history_text(self):
        """Build history string with smart trimming (newest kept, oldest trimmed)."""
        if not self.conversation_history:
            return ""

        # Build from newest to oldest, stop when budget exceeded
        parts = []
        total_chars = 0
        for i, entry in enumerate(reversed(self.conversation_history)):
            turn_num = len(self.conversation_history) - i
            chunk = f"--- Turn {turn_num} ---\n"
            chunk += f"Transcript: {entry['transcript']}\n"
            chunk += f"AI Answer: {entry['response']}\n"

            if total_chars + len(chunk) > self.max_history_chars:
                break  # Budget exceeded, stop adding older entries
            parts.insert(0, chunk)
            total_chars += len(chunk)

        return "\n".join(parts)

    def get_prompt(self, transcript):
        """
        Combines CV, Job Description, conversation history, and live transcript
        into structured prompt data for the AI Interview Assistant.
        """
        cv_text = self.read_file(self.cv_path) or "Not provided."
        jd_text = self.read_file(self.jd_path) or "Not provided."
        
        if not transcript:
            transcript = "[No conversation yet]"

        history_text = self._build_history_text()

        system_instruction = """You are an AI interview assistant helping a candidate answer questions in real-time.

Rules:
- Reply in plain text only. No markdown, no bold, no headers, no asterisks, no hashtags.
- Maximum 5 short bullet points using "- " prefix.
- Each bullet point must be 1-2 sentences max.
- Go straight to the answer. No introductions, no summaries, no closings.
- Match the language of the interviewer's question.
- Use the candidate's CV and JD to make answers specific and relevant.
- Review the conversation history to maintain consistency and avoid repeating previous answers.
- Build upon what was already discussed in previous turns."""

        # Build contents with optional history section
        history_section = ""
        if history_text:
            history_section = f"""
[CONVERSATION HISTORY]
{history_text}
"""

        contents = f"""[CV]
{cv_text}

[JOB DESCRIPTION]
{jd_text}
{history_section}
[CURRENT TRANSCRIPT]
{transcript}

Answer the latest question from the transcript. Consider the conversation history for context. Plain text, max 5 short bullets, no formatting symbols."""
        
        return {
            "system_instruction": system_instruction,
            "contents": contents
        }

    def get_screenshot_prompt(self):
        """
        Build a prompt for solving a coding problem from a screenshot.
        """
        cv_text = self.read_file(self.cv_path) or "Not provided."
        jd_text = self.read_file(self.jd_path) or "Not provided."

        system_instruction = """You are an expert coding interview assistant. You will receive a screenshot of a coding problem.

Rules:
- Analyze the problem in the screenshot carefully.
- Provide a complete, working solution in the most appropriate programming language.
- If the language is specified in the problem, use that language.
- Write clean, well-structured code that is easy to read and type quickly.
- Include brief inline comments for key logic steps.
- After the code, provide a SHORT explanation (2-3 bullets max) of the approach and time/space complexity.
- Use markdown formatting: wrap code in triple backticks with the language name (e.g. ```python).
- Use "- " prefix for explanation bullets."""

        contents = f"""[CANDIDATE CV]
{cv_text}

[TARGET JOB]
{jd_text}

Look at the screenshot of the coding problem. Solve it completely. Write production-quality code that the candidate can type in."""

        return {
            "system_instruction": system_instruction,
            "contents": contents
        }
