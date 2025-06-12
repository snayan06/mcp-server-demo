from mcp.server.fastmcp import FastMCP
from typing import Any, Dict
import httpx
import asyncio
import logging
import uvicorn

# ------------------- Logging Setup -------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- MCP Server -------------------
mcp = FastMCP("weather")  # MCP namespace

# ------------------- Constants -------------------
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# ------------------- HTTP Client Init -------------------
http_client: httpx.AsyncClient | None = None
async def get_http_client() -> httpx.AsyncClient:
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return http_client

# ------------------- Utility: Fetch JSON -------------------
async def fetch_json(url: str, params: Dict[str, Any] = {}) -> Dict[str, Any] | None:
    try:
        client = await get_http_client()
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None

# ------------------- Tool: Geocode City -------------------
@mcp.tool()
async def geocode_city(city_name: str) -> Dict[str, float]:
    """
    Resolve a city name to latitude and longitude.

    Args:
        city_name: Name of the city, e.g., "Pune, India".

    Returns:
        A dict with keys "latitude" and "longitude".
        Example: {"latitude": 18.5204, "longitude": 73.8567}
    """
    logger.info(f"Geocoding: {city_name}")
    data = await fetch_json(GEOCODING_URL, params={"name": city_name, "count": 1})
    if not data or not data.get("results"):
        raise ValueError(f"Could not geocode location: {city_name}")
    coords = data["results"][0]
    return {"latitude": coords["latitude"], "longitude": coords["longitude"]}

# ------------------- Tool: Fetch Current Weather -------------------
@mcp.tool()
async def fetch_current_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Get current weather data for given coordinates.

    Args:
        latitude: Latitude of the location, e.g., 18.5204
        longitude: Longitude of the location, e.g., 73.8567

    Returns:
        The 'current_weather' dict from Open-Meteo.
        Example:
        {
            "temperature": 29.3,
            "windspeed": 5.8,
            "winddirection": 270.0
        }
    """
    logger.info(f"Fetching weather for coords: {latitude}, {longitude}")
    params = {"latitude": latitude, "longitude": longitude, "current_weather": True}
    data = await fetch_json(WEATHER_URL, params=params)
    if not data or "current_weather" not in data:
        raise ValueError("Weather data unavailable for provided coordinates")
    return data["current_weather"]

# ------------------- Resource: Greeting -------------------
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Returns a personalized greeting message, e.g., "Hello, Alice!"""  
    return f"Hello, {name}!"

# ------------------- MCP Shutdown -------------------
async def cleanup():
    """Clean up HTTP client on shutdown."""
    global http_client
    if http_client:
        await http_client.aclose()

if __name__ == "__main__":
    # Initialize and run the server
    print("Starting MCP server...")
    mcp.run(transport='stdio')