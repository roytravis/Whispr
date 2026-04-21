import base64
from openai import OpenAI
import config


class QwenClient:
    """Qwen client via Alibaba Model Studio OpenAI-compatible endpoint."""

    def __init__(self):
        if not config.QWEN_API_KEY:
            raise ValueError("QWEN_API_KEY is missing. Please set it in your .env file.")

        self.client = OpenAI(
            api_key=config.QWEN_API_KEY,
            base_url=config.QWEN_BASE_URL,
        )
        self.text_model = config.QWEN_TEXT_MODEL
        self.vision_model = config.QWEN_VISION_MODEL

    def ask(self, prompt_data):
        """Send a text prompt. Expects dict with 'system_instruction' and 'contents'."""
        try:
            response = self.client.chat.completions.create(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": prompt_data["system_instruction"]},
                    {"role": "user", "content": prompt_data["contents"]},
                ],
                temperature=1.0,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Qwen API Error: {e}")
            return "Error: Could not get a response from AI."

    def ask_with_image(self, prompt_data, image_bytes: bytes):
        """Send a multimodal prompt (image + text) to a Qwen VL model."""
        try:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            data_url = f"data:image/png;base64,{b64}"
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": prompt_data["system_instruction"]},
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text", "text": prompt_data["contents"]},
                        ],
                    },
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Qwen API Error (image): {e}")
            return "Error: Could not get a response from AI."
