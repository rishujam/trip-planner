import requests
from fastapi import FastAPI, Query
from typing import Optional
import os
import googlemaps

from dotenv import load_dotenv
load_dotenv()

if os.environ.get("RENDER") != "true":
    from dotenv import load_dotenv
    load_dotenv()

app = FastAPI()

api_key = os.getenv("GOOGLE_MAPS_API_KEY")
print("ENV KEYS:", list(os.environ.keys()))
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
            "photo_url": photo_url or "No photo available"
        })

    return {
        "stays": stays,
        "next_page_token": places_result.get("next_page_token")
    }

@app.get("/resolve-link")
def resolve_google_maps_link(shared_url: str):
    try:
        response = requests.get(shared_url, allow_redirects=True, timeout=5)
        final_url = response.url 
        return {"final_url": final_url}
    except Exception as e:
        return {"error": str(e)}