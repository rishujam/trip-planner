from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from openai import OpenAI
import googlemaps
from typing import Optional

app = FastAPI()

from dotenv import load_dotenv
import os
load_dotenv()

# Load environment variables
if os.environ.get("RENDER") != "true":
    load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    organization=os.getenv("OPENAI_ORG_ID")
)

function_def = {
    "type": "function",
    "function": {
        "name": "generate_itinerary",
        "description": "Generates a multi-day road trip itinerary",
        "parameters": {
            "type": "object",
            "properties": {
                "itinerary": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "day": {"type": "integer"},
                            "start": {
                                "type": "object",
                                "properties": {
                                    "lat": {"type": "number"},
                                    "long": {"type": "number"},
                                },
                                "required": ["lat", "long"]
                            },
                            "end": {
                                "type": "object",
                                "properties": {
                                    "lat": {"type": "number"},
                                    "long": {"type": "number"},
                                },
                                "required": ["lat", "long"]
                            },
                            "distance_km": {"type": "integer"},
                            "places_to_see": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "stay": {"type": "string"}
                        },
                        "required": ["day", "start", "end", "distance_km", "places_to_see", "stay"]
                    }
                }
            },
            "required": ["itinerary"]
        }
    }
}


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
            tools=[function_def],
            tool_choice="auto"
        )
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


api_key = os.getenv("GOOGLE_MAPS_API_KEY")
if not api_key:
    raise ValueError("Google Maps API Key is missing.")
gmaps = googlemaps.Client(key=api_key)

@app.get("/stays")
def get_stays(
    lat: float = Query(..., description="Latitude of the location"),
    lon: float = Query(..., description="Longitude of the location"),
    radius: int = Query(6000, description="Search radius in meters"),
    page_token: Optional[str] = Query(None, description="Google Places API next_page_token")
):
    stays = []

    # Build search request
    search_args = {
        "location": (lat, lon),
        "radius": radius,
        "type": "lodging"
    }
    if page_token:
        search_args["page_token"] = page_token

    # Call Google Maps Places API
    places_result = gmaps.places_nearby(**search_args)

    for place in places_result.get("results", []):
        name = place.get("name")
        place_id = place.get("place_id")

        details = gmaps.place(
            place_id=place_id,
            fields=["formatted_phone_number", "photo"]
        )
        result = details.get("result", {})

        phone = result.get("formatted_phone_number", "Phone not available")

        # Build photo URL
        photo_url = None
        photos = result.get("photos")
        if photos:
            photo_ref = photos[0].get("photo_reference")
            if photo_ref:
                photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_ref}&key={api_key}"

        stays.append({
            "name": name,
            "phone": phone,
            "photo_url": photo_url or "No photo available",
            "place_id": place_id 
        })

    return {
        "stays": stays,
        "next_page_token": places_result.get("next_page_token")
    }