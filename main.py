from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

from dotenv import load_dotenv
import os
load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    organization=os.getenv("OPENAI_ORG_ID")
)

class ItineraryRequest(BaseModel):
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float

@app.post("/generate-itinerary")
async def generate_itinerary(req: ItineraryRequest):
    prompt = f"""
You are a travel planner specialized in planning road trips for people who travel with their own vehicles, such as motorcycles or cars. Your users only travel to hilly or mountainous regions and prefer scenic, adventure-filled routes.

Plan a road trip itinerary from Delhi to Gurez Valley. The plan should consider distance and terrain and break the journey into multiple days if required. 

For each day, specify:
- The distance to be covered
- The key stop or town for the night
- Suggested sightseeing places on the way
- An ideal place to stay (example: town, homestay, campsite)

The final response should be a **JSON** object with the following structure:

json
{{
  "itinerary": [
    {{
      "day": 1,
      "start": {{ "lat": 0.0, "long": 0.0 }},
      "end": {{ "lat": 0.0, "long": 0.0 }},
      "distance_km": 150,
      "places_to_see": ["Spot 1", "Spot 2"],
      "stay": "Suggested town or area to stay"
    }},
    {{
      "day": 2,
      "start": {{ "lat": 0.0, "long": 0.0 }},
      "end": {{ "lat": 0.0, "long": 0.0 }},
      ...
    }}
  ]
}}

Please provide the JSON response **without any markdown formatting or code blocks**. Just raw JSON.
"""


    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a travel itinerary generator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))