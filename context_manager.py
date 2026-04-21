import os

class ContextManager:
    def __init__(self, cv_path="cv.txt", jd_path="jd.txt"):
        self.cv_path = cv_path
        self.jd_path = jd_path

    def read_file(self, path):
        """Reads and returns the content of the file if it exists."""
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as e:
                print(f"Error reading {path}: {e}")
        return ""

    def get_prompt(self, transcript):
        """
        Combines CV, Job Description, and live transcript into structured prompt data
        tailored for an AI Interview Assistant according to prompt engineering principles.
        """
        cv_text = self.read_file(self.cv_path) or "Not provided."
        jd_text = self.read_file(self.jd_path) or "Not provided."
        
        if not transcript:
            transcript = "[No conversation yet]"

        system_instruction = f"""You are an AI interview assistant helping a candidate answer questions in real-time.

Rules:
- Reply in plain text only. No markdown, no bold, no headers, no asterisks, no hashtags.
- Maximum 5 short bullet points using "- " prefix.
- Each bullet point must be 1-2 sentences max.
- Go straight to the answer. No introductions, no summaries, no closings.
- Match the language of the interviewer's question.
- Use the candidate's CV and JD to make answers specific and relevant."""

        contents = f"""[CV]
{cv_text}

[JOB DESCRIPTION]
{jd_text}

[TRANSCRIPT]
{transcript}

Answer the latest question from the transcript. Plain text, max 5 short bullets, no formatting symbols."""
        
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
