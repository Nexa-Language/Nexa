# Nexa Dynamic Skills

Here we define tools that can be dynamically parsed by Nexa during codegen.

## Tool: get_weather
This tool retrieves the current weather of a given city.
```json
{
    "description": "Get current weather of a city",
    "type": "object",
    "properties": {
        "city": { "type": "string", "description": "The name of the city, e.g., Beijing" }
    },
    "required": ["city"]
}
```

## Tool: calculate_hash
This tool returns a fake hash for a given string.
```json
{
    "description": "Calculate hash of string",
    "type": "object",
    "properties": {
        "text": { "type": "string", "description": "The string to hash" }
    },
    "required": ["text"]
}
```
