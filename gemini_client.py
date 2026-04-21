from google import genai
from google.genai import types
import config

class GeminiClient:
    def __init__(self):
        """
        Initializes the Gemini client using the official google-genai SDK.
        It uses the API key configured in .env (loaded via config.py).
        """
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is missing. Please set it in your .env file.")

        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model_name = "gemini-3-flash-preview"

    def ask(self, prompt_data):
        """
        Sends the prompt using prompt-engineering patterns to Gemini
        and returns the response text. Expects a dict with 'system_instruction' and 'contents'.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt_data["contents"],
                config=types.GenerateContentConfig(
                    system_instruction=prompt_data["system_instruction"],
                    temperature=1.0
                )
            )
            return response.text
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return "Error: Could not get a response from AI."

    def ask_with_image(self, prompt_data, image_bytes: bytes):
        """
        Sends a prompt together with an image (screenshot) to Gemini.
        Uses multimodal content: image + text.
        """
        try:
            image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
            text_part = types.Part.from_text(text=prompt_data["contents"])
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[image_part, text_part],
                config=types.GenerateContentConfig(
                    system_instruction=prompt_data["system_instruction"],
                    temperature=0.2
                )
            )
            return response.text
        except Exception as e:
            print(f"Gemini API Error (image): {e}")
            return "Error: Could not get a response from AI."
