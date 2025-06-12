# server.py
from mcp.server.fastmcp import FastMCP
from typing import Any
import httpx
import asyncio
import logging

# Set up logging to see what's happening during startup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create an MCP server
mcp = FastMCP("Demo")


# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"


# Open-Meteo endpoints
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# Create a persistent HTTP client to avoid connection overhead
http_client = None


async def get_http_client():
    """Get or create HTTP client with connection pooling."""
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
    return http_client


async def fetch_json(url: str, params: dict[str, Any] = {}) -> dict[str, Any] | None:
    """Utility function to make async GET requests and return JSON."""
    try:
        client = await get_http_client()
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching {url}")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} for {url}")
        return None
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None


@mcp.tool()
async def get_weather(location: str) -> str:
    """
    Get current weather (temperature, windspeed, direction) for a location.

    Args:
        location: City and country, e.g., 'Pune, India'
    """
    logger.info(f"Getting weather for {location}")

    # Step 1: Geocode the location
    geo_data = await fetch_json(GEOCODING_URL, params={"name": location, "count": 1})
    if not geo_data or not geo_data.get("results"):
        return f"Could not resolve location: {location}"

    coords = geo_data["results"][0]
    lat, lon = coords["latitude"], coords["longitude"]
    logger.info(f"Found coordinates: {lat}, {lon}")

    # Step 2: Fetch weather using coordinates
    weather_data = await fetch_json(
        WEATHER_URL, params={"latitude": lat, "longitude": lon, "current_weather": True}
    )

    if not weather_data or "current_weather" not in weather_data:
        return "Weather data unavailable for now."

    weather = weather_data["current_weather"]
    return f"""Here's the current weather in {location}:
  • Temperature: {weather['temperature']}°C
  • Wind Speed: {weather['windspeed']} km/h
  • Wind Direction: {weather['winddirection']}°"""


async def cleanup():
    """Clean up resources on shutdown."""
    global http_client
    if http_client:
        await http_client.aclose()