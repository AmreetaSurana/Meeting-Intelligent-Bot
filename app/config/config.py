from dotenv import load_dotenv
import os


load_dotenv()

API_KEY = os.getenv("API_KEY")
API_MODEL = os.getenv("API_MODEL")