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
from martian_prompt import IMAGE_GENERATION
import base64
import re

load_dotenv()
MARTIAN_ENV = os.getenv("MARTIAN_ENV")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY environment variable not set. Please add it to your .env file."
    )

oai_client = openai.OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

# Initialize Google Genai client for image generation
genai_client = genai.Client(api_key=GEMINI_API_KEY)


def image_generator_tool(image_description: str) -> str:
    """
    Generates an image based on the provided description using Google Genai
    """
    response = genai_client.models.generate_content(
        model="gemini-2.5-flash-image-preview",
        contents=[image_description],
    )

    print("I am here!")
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            # Generate unique filename in temp directory within current directory
            temp_dir = os.path.join(os.getcwd(), "temp")
            os.makedirs(temp_dir, exist_ok=True)
            filename = f"generated_image_{uuid.uuid4().hex[:8]}.png"
            filepath = os.path.join(temp_dir, filename)
            image = Image.open(BytesIO(part.inline_data.data))
            image.save(filepath)
            print("I am returning the filename:", filepath)
            return os.path.abspath(filepath)

    return "No image generated"


def use_martian(message, instructions, context):
    messages = []

    messages.append({"role": "user", "content": message})

    messages.append({"role": "system", "content": IMAGE_GENERATION})

    response = oai_client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=messages,
        response_format={"type": "json_object"},
    )

    message = response.choices[0].message
    content = message.content

    image_url_pattern = r"IMAGE_URL\(([^)]+)\)"
    matches = re.findall(image_url_pattern, content)

    for description in matches:
        clean_description = description.strip("\"'")
        image_path = image_generator_tool(clean_description)
        content = content.replace(f"IMAGE_URL({description})", image_path, 1)

    return content