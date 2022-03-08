import requests 
from redis import Redis
from slugify import slugify
from fastapi import FastAPI
from datetime import date
from fastapi.responses import JSONResponse

redis = Redis(host="redis.pythonweekend.skypicker.com", port=6379, db=0)
app = FastAPI()

def find_location(source, destination, departure_time):
    source_key = slugify(f"vas:location:{source}")
    destination_key = slugify(f"vas:location:{destination}")

    if redis.get(source_key):
        source_id = redis.get(source_key).decode("utf-8")

    if redis.get(destination_key):
        destination_id = redis.get(destination_key).decode("utf-8")

    if 'source_id' in locals() and 'destination_id' in locals():
        return source_id, destination_id, source, destination, str(departure_time)

    location_response = requests.get('https://brn-ybus-pubapi.sa.cz/restapi/consts/locations')
    locations = location_response.json()
    for location in locations:
        for cities in location["cities"]:
            if cities["name"] == source:
                source_id = cities["id"]
            if cities["name"] == destination:
                destination_id = cities["id"]

    redis.set(source_key, source_id)
    redis.set(destination_key, destination_id)

    return source_id, destination_id, source, destination, str(departure_time)


def cache_check(args):
    print(args)
    journey_key = slugify(f"vas:journey:{args[2]}_{args[3]}_{args[4]}")

    if redis.get(journey_key):
        return redis.get(journey_key).decode("utf-8"), args[2], args[3], args[4]

    result = serialize(scrape(args[0], args[1], args[2], args[3], args[4]))
    redis.set(journey_key, str(result))

    return result, args[2], args[3], args[4]


def scrape(source_id, destination_id, source, destination, departure_time):
    print(f"https://brn-ybus-pubapi.sa.cz/restapi/routes/search/simple?tariffs=REGULAR&toLocationType=CITY&toLocationId={destination_id}&fromLocationType=CITY&fromLocationId={source_id}&departureDate={departure_time}")
    try:
        response = requests.get(f"https://brn-ybus-pubapi.sa.cz/restapi/routes/search/simple?tariffs=REGULAR&toLocationType=CITY&toLocationId={destination_id}&fromLocationType=CITY&fromLocationId={source_id}&departureDate={departure_time}")
        routes = response.json()["routes"]
    except:
         return [], source, destination

    return routes, source, destination


def serialize(args):
    output = list()

    for route in args[0]:
        data = dict()
        data["departure_datetime"] = route["departureTime"]
        data["arrival_datetime"] = route["arrivalTime"]
        data["source"] = args[1]
        data["destination"] = args[2]
        data["fare"] = {'amount': route["priceFrom"], 'currency': "EUR"}
        data["type"] = route["vehicleTypes"][0]
        data["source_id"] = route["departureStationId"]
        data["destination_id"] = route["arrivalStationId"]
        data["free_seats"] = route["freeSeatsCount"]

        output.append(data)

    return output


@app.get('/search')
def search(origin: str, destination: str, departure: date):
  results = cache_check(find_location(origin, destination, departure))[0]
  return JSONResponse(results)
