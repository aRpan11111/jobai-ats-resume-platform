import asyncio
import os
from dotenv import load_dotenv
from app import ai

async def main():
    load_dotenv()
    print("GROQ_API_KEY:", os.environ.get("GROQ_API_KEY")[:5] if os.environ.get("GROQ_API_KEY") else "None")
    try:
        res = await ai.parse_resume_to_json("This is a sample resume. Software Engineer at Google.")
        print("Success:", res)
    except Exception as e:
        print("Error:", repr(e))

if __name__ == "__main__":
    asyncio.run(main())
