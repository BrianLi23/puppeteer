import openai
import os
import json
import uuid
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
from agent_prompt import IMAGE_GENERATION
import base64
import re

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY environment variable not set. Please add it to your .env file."
    )

# Initialize Google Genai client for image generation
genai_client = genai.Client(api_key=GEMINI_API_KEY)

def image_generator_tool(image_description: str) -> str:
    response = genai_client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=[image_description],
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            # Generate unique filename in temp directory within current directory
            temp_dir = os.path.join(os.getcwd(), "temp")
            os.makedirs(temp_dir, exist_ok=True)
            filename = f"generated_image_{uuid.uuid4().hex[:8]}.png"
            filepath = os.path.join(temp_dir, filename)
            image = Image.open(BytesIO(part.inline_data.data))
            image.save(filepath)
            return os.path.abspath(filepath)

    return "No image generated"


def llm_call(message):
    # Combine user message with system instructions
    full_prompt = f"{IMAGE_GENERATION}\n\n{message}"
    
    response = genai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    content = response.text

    image_url_pattern = r"IMAGE_URL\(([^)]+)\)"
    matches = re.findall(image_url_pattern, content)

    # Replace each IMAGE_URL(...) with the actual generated image path
    for description in matches:
        clean_description = description.strip("\"'")
        
        # Generate image from description and get file path
        image_path = image_generator_tool(clean_description)
        content = content.replace(f"IMAGE_URL({description})", image_path, 1)

    return content