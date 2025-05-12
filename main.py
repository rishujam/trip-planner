from fastapi import FastAPI, Query
from typing import Optional
import os
import googlemaps
import json
import re
from openai import OpenAI
import uvicorn

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

from dotenv import load_dotenv
load_dotenv()


# Load environment variables
if os.environ.get("RENDER") != "true":
    load_dotenv()

def load_mcp_graph(path="mcp_graph.json"):
    with open(path, "r") as f:
        return json.load(f)
    
context = load_mcp_graph()

app = FastAPI()
google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
if not google_api_key:
    raise ValueError("Google Maps API Key is missing.")
gmaps = googlemaps.Client(key=google_api_key)
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    organization=os.getenv("OPENAI_ORG_ID")
)

def call_gpt_with_graph(origin: str, destination: str):

    system_prompt = f"""
You're a travel planner AI. Generate a day-wise itinerary for a motorcycle trip from "{origin}" to "{destination}" in JSON format only (no Markdown, no text, no explanation).

The format should be:

{{
  "itinerary": [
    {{
      "day": 1,
      "date": "YYYY-MM-DD",
      "start": "{origin}",
      "end": "Next Stop",
      "distance_km": 250,
      "ride_hours": 5,
      "stays": [
        {{
          "name": "Hotel Name",
          "contact": "Phone Number",
          "location": "City/Area"
        }}
      ]
    }}
  ]
}}

- Use today's date as Day 1 and increment each day.
- Always return a valid JSON object.
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please plan a trip from {origin} to {destination}."}
        ],
        response_format={ "type": "json_object" }
    )

    content = response.choices[0].message.content.strip()

    try:
        json_start = content.find('{')
        return json.loads(content[json_start:])
    except Exception:
        return {
            "raw": content,
            "error": "Could not parse GPT response as JSON."
        }

# TOOL: Directions API
class DirectionsTool:
    @staticmethod
    def get_route(origin: str, destination: str):
        directions_result = gmaps.directions(
            origin=origin,
            destination=destination,
            mode="driving",
            alternatives=False
        )
        return directions_result

# TOOL: Places API
class PlacesTool:
    @staticmethod
    def get_lodging_nearby(lat: float, lon: float, radius: int = 6000, page_token: Optional[str] = None):
        stays = []
        search_args = {
            "location": (lat, lon),
            "radius": radius,
            "type": "lodging"
        }
        if page_token:
            search_args["page_token"] = page_token

        places_result = gmaps.places_nearby(**search_args)

        for place in places_result.get("results", []):
            name = place.get("name")
            place_id = place.get("place_id")

            details = PlacesTool.get_place_details(place_id)
            result = details.get("result", {})

            phone = result.get("formatted_phone_number", "Phone not available")

            # Build photo URL
            photo_url = None
            photos = result.get("photos")
            if photos:
                photo_ref = photos[0].get("photo_reference")
                if photo_ref:
                    photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_ref}&key={google_api_key}"

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

    @staticmethod
    def get_place_details(place_id: str):
        return gmaps.place(
            place_id=place_id,
            fields=["formatted_phone_number", "photo"]
        )

# MEMORY: User Preferences (MCP-style static example)
USER_PREFERENCES = {
    "max_hours_highway": 6,
    "max_hours_mountains": 4,
    "min_stays_with_contact": 6,
    "exploration_required": True
}

@app.get("/stays")
def get_stays(
    lat: float = Query(..., description="Latitude of the location"),
    lon: float = Query(..., description="Longitude of the location"),
    radius: int = Query(6000, description="Search radius in meters"),
    page_token: Optional[str] = Query(None, description="Google Places API next_page_token")
):
    return PlacesTool.get_lodging_nearby(lat, lon, radius, page_token)

@app.get("/itinerary")
def plan_itinerary(
    origin: str = Query(..., description="Starting location"),
    destination: str = Query(..., description="Destination location"),
    daily_limit_km: int = Query(250, description="Max distance to ride per day")
):
    try: 
        directions = DirectionsTool.get_route(origin, destination)
        if not directions:
            return {"error": "No route found."}

        route = directions[0]['legs'][0]
        steps = route['steps']

        itinerary = []
        day = 1
        segment_distance = 0
        segment_start = steps[0]['start_location']

        for step in steps:
            segment_distance += step['distance']['value'] / 1000  # meters to km
            end_loc = step['end_location']

            if segment_distance >= daily_limit_km:
                lat, lon = end_loc['lat'], end_loc['lng']
                stays = PlacesTool.get_lodging_nearby(lat, lon, radius=6000)
                itinerary.append({
                    "day": day,
                    "segment_km": round(segment_distance),
                    "stop_location": {
                        "lat": lat,
                        "lon": lon
                    },
                    "stays": stays['stays'][0]
                })
                day += 1
                segment_distance = 0

        gpt_raw = call_gpt_with_graph(origin, destination)
        return {
            "fallback_itinerary": itinerary,
            "gpt_itinerary": gpt_raw
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}