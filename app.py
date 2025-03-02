from flask import Flask, request, jsonify, render_template, Response
import threading
import logging
from queue import Queue
import json
import sys

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Global list to store elevator instances and request queue
elevators = []

num_elevators = 0
num_floors = 0

# we can also use min heap to store the requests
request_queue = Queue()
response_queue = Queue()


class Elevator:
    def __init__(self, name, location, direction="idle", status="idle"):
        self.name = name
        self.location = location  # Floor location of the elevator
        self.direction = direction  # 'up', 'down', or 'idle'
        self.status = status  # 'moving' or 'idle'
        self.prev_location = None  # Previous floor location of the elevator
        self.requests = []  # List of floor requests
        self.responses = []  # List of responses

    def add_request(self, call_location, call_direction, call_destination=None):
        if call_destination is not None:
            self.requests.append((call_location, call_direction, call_destination))
        else:
            # Add destination request without a call direction
            self.requests.append((call_location, "", None))
        self.requests.sort()  # Keep requests sorted

    def move(self, num_floors):
        while self.requests:
            if self.direction == "idle":
                # Start moving towards the first request
                next_request = self.requests[0]
                if next_request[0] > self.location:
                    self.direction = "up"
                else:
                    self.direction = "down"
                self.status = "moving"
                print(f"Elevator {self.name} starts moving {self.direction}")

            if self.direction == "up":
                # Move up to the next request
                next_requests = [r for r in self.requests if r[0] >= self.location]
                if next_requests:
                    next_request = min(next_requests, key=lambda r: r[0])
                    self.prev_location = self.location
                    while self.location < next_request[0]:
                        self.location += 1
                        # time.sleep(1)  # Simulate time taken to move one floor
                    self.requests.remove(next_request)
                    print(
                        f"Elevator {self.name} reached floor {self.location} next request {self.requests}"
                    )

                    # Handle destination floor
                    if next_request[2] is not None:
                        print(
                            f"Elevator {self.name} picked up request to floor {next_request[2]}"
                        )
                        self.add_request(
                            next_request[2],
                            "up" if next_request[2] > self.location else "down",
                        )
                    self.add_response()

                # If no more requests in the current direction, change direction
                if not [r for r in self.requests if r[0] >= self.location]:
                    self.direction = "down" if self.requests else "idle"

            elif self.direction == "down":
                # Move down to the next request
                next_requests = [r for r in self.requests if r[0] <= self.location]
                if next_requests:
                    next_request = max(next_requests, key=lambda r: r[0])
                    self.prev_location = self.location
                    while self.location > next_request[0]:
                        self.location -= 1
                        # time.sleep(1)  # Simulate time taken to move one floor
                    self.requests.remove(next_request)
                    print(
                        f"Elevator {self.name} reached floor {self.location} next request {self.requests}"
                    )

                    # Handle destination floor
                    if next_request[2] is not None:
                        print(
                            f"Elevator {self.name} picked up request to floor {next_request[2]}"
                        )
                        self.add_request(
                            next_request[2],
                            "up" if next_request[2] > self.location else "down",
                        )
                    self.add_response()

                # If no more requests in the current direction, change direction
                if not [r for r in self.requests if r[0] <= self.location]:
                    self.direction = "up" if self.requests else "idle"

            if self.location == 0:
                self.direction = "up"
            elif self.location == num_floors - 1:
                self.direction = "down"

        self.status = "idle"
        self.direction = "idle"
        if len(self.responses) > 0:
            self.responses.pop()
            self.add_response()
            last_response = self.responses.copy()
            response_queue.put(last_response)
            self.responses.clear()  # Clear responses after adding to the response queue

    def add_response(self):
        response = {
            "elevator_name": self.name,
            "call_location": self.prev_location,
            "current_location": self.location,
            "current_status": self.status,
            "current_direction": self.direction,
        }

        self.responses.append(response)


def select_elevator(call_location, call_direction, elevators, num_floors):
    FS = 1
    selected_car = elevators[0]

    for car in elevators:
        d = abs(car.location - call_location)

        if car.status == "idle":
            new_FS = num_floors + 1 - d

        elif car.direction == "down":
            if call_location > car.location:
                new_FS = 1
            elif call_location < car.location and call_direction == "down":
                new_FS = num_floors + 2 - d
            else:  # call_location < car.location and call_direction != 'down'
                new_FS = num_floors + 1 - d

        elif car.direction == "up":
            if call_location < car.location:
                new_FS = 1
            elif call_location > car.location and call_direction == "up":
                new_FS = num_floors + 2 - d
            else:  # call_location > car.location and call_direction != 'up'
                new_FS = num_floors + 1 - d

        if new_FS > FS:
            FS = new_FS
            selected_car = car

    return selected_car


elevators_thread = []


def start_elevators():
    for instance in elevators:
        thread = threading.Thread(target=instance.move, args=(num_floors,))
        thread.start()
        elevators_thread.append(thread)

    for thread in elevators_thread:
        thread.join()


@app.route("/initialize_elevators", methods=["POST"])
def initialize_elevators():
    global num_elevators
    global num_floors
    data = request.get_json()
    num_elevators = data["num_elevators"]
    num_floors = data["num_floors"]

    # Initialize elevators if not already initialized
    if elevators.__len__() == 0:
        for i in range(num_elevators):
            elevators.append(Elevator(chr(i + 65), 0))

    return jsonify(
        {
            "status": f"{num_floors} floors and {num_elevators} elevators initialized",
            "num_elevators": num_elevators,
            "elevators": [e.__dict__ for e in elevators],
        }
    )


@app.route("/request_elevator", methods=["POST"])
def request_elevator():
    try:
        datas = request.get_json()

        for data in datas:

            call_location = data["call_location"]
            call_direction = data["call_direction"]
            call_destination = data["call_destination"]
            print(
                f"New request: call_location: {call_location}, call_direction: {call_direction}, call_destination: {call_destination}"
            )
            elevator = select_elevator(
                call_location, call_direction, elevators, num_floors
            )
            elevator.add_request(call_location, call_direction, call_destination)
            print(f"elevator {elevator.name}: {elevator.requests}")

        start_elevators()
        return jsonify({"status": "Request processed successfully"})

    except Exception as e:
        logging.error(f"Error processing elevator request: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/stream")
def stream():
    def generate():
        sys.stdout.flush()
        global response_queue
        while True:
            response = response_queue.get()
            # print(f"Response: {response}")
            response_queue.task_done()
            yield f"data: {json.dumps(response)}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
