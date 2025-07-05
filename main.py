from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
from openai import OpenAI
import googlemaps
from typing import Optional, List
from sqlalchemy.orm import Session

# Import database models and session
from database import get_db, Destination

app = FastAPI()

from dotenv import load_dotenv
import os
load_dotenv()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

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

# Pydantic models for Destination API
class DestinationCreate(BaseModel):
    name: str
    lat: float
    long: float
    image_urls: List[str] = []

class DestinationUpdate(BaseModel):
    name: Optional[str] = None
    lat: Optional[float] = None
    long: Optional[float] = None
    image_urls: Optional[List[str]] = None

class DestinationResponse(BaseModel):
    id: str
    name: str
    lat: float
    long: float
    image_urls: List[str]
    created_at: int

    class Config:
        from_attributes = True

# Destination CRUD endpoints
@app.post("/destinations", response_model=DestinationResponse)
async def create_destination(destination: DestinationCreate, db: Session = Depends(get_db)):
    """Create a new destination"""
    # Generate ID from coordinates
    destination_id = Destination.generate_id(destination.lat, destination.long)
    
    # Check if destination already exists
    existing_destination = db.query(Destination).filter(Destination.id == destination_id).first()
    if existing_destination:
        raise HTTPException(status_code=400, detail="Destination with these coordinates already exists")
    
    # Create new destination
    db_destination = Destination(
        id=destination_id,
        name=destination.name,
        lat=destination.lat,
        long=destination.long,
        image_urls=destination.image_urls
    )
    
    db.add(db_destination)
    db.commit()
    db.refresh(db_destination)
    
    return db_destination

@app.get("/destinations", response_model=List[DestinationResponse])
async def get_destinations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all destinations with pagination"""
    destinations = db.query(Destination).offset(skip).limit(limit).all()
    return destinations

@app.get("/destinations/{destination_id}", response_model=DestinationResponse)
async def get_destination(destination_id: str, db: Session = Depends(get_db)):
    """Get a specific destination by ID"""
    destination = db.query(Destination).filter(Destination.id == destination_id).first()
    if destination is None:
        raise HTTPException(status_code=404, detail="Destination not found")
    return destination

@app.put("/destinations/{destination_id}", response_model=DestinationResponse)
async def update_destination(destination_id: str, destination_update: DestinationUpdate, db: Session = Depends(get_db)):
    """Update a destination"""
    db_destination = db.query(Destination).filter(Destination.id == destination_id).first()
    if db_destination is None:
        raise HTTPException(status_code=404, detail="Destination not found")
    
    # Update fields if provided
    update_data = destination_update.dict(exclude_unset=True)
    
    # If lat or long is being updated, we need to generate a new ID
    if 'lat' in update_data or 'long' in update_data:
        new_lat = update_data.get('lat', db_destination.lat)
        new_long = update_data.get('long', db_destination.long)
        new_id = Destination.generate_id(new_lat, new_long)
        
        # Check if new ID already exists (different from current)
        if new_id != destination_id:
            existing = db.query(Destination).filter(Destination.id == new_id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Destination with new coordinates already exists")
            update_data['id'] = new_id
    
    for field, value in update_data.items():
        setattr(db_destination, field, value)
    
    db.commit()
    db.refresh(db_destination)
    return db_destination

@app.delete("/destinations/{destination_id}")
async def delete_destination(destination_id: str, db: Session = Depends(get_db)):
    """Delete a destination"""
    db_destination = db.query(Destination).filter(Destination.id == destination_id).first()
    if db_destination is None:
        raise HTTPException(status_code=404, detail="Destination not found")
    
    db.delete(db_destination)
    db.commit()
    
    return {"message": "Destination deleted successfully"}