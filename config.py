import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

# Qwen (Alibaba Model Studio, OpenAI-compatible) configuration
# Singapore region (international) endpoint:
QWEN_BASE_URL = os.getenv(
    "QWEN_BASE_URL",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)
QWEN_TEXT_MODEL = os.getenv("QWEN_TEXT_MODEL", "qwen-plus")
QWEN_VISION_MODEL = os.getenv("QWEN_VISION_MODEL", "qwen-vl-max")

# Audio Configuration
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION = 3 # in seconds
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION) # number of frames
FORMAT = 8 # pyaudio.paInt16 code

# App Settings
BUFFER_MAX_AGE_MINUTES = 5
