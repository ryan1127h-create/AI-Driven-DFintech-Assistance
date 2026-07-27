import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    app_name: str = "MSc DFT AI Assistant"
    debug: bool = True

settings = Settings()
