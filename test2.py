from google import genai
from google.genai import types

client = genai.Client(api_key="AIzaSyDDsRayQsXO8Qo6vpUC_lGu3rDUSeLPQfk")

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=["find a best jbl speakers for me"],
    config=types.GenerateContentConfig(
        max_output_tokens=500,
        temperature=0.1
    )
)
print(response.text)