import socket
import threading
import random

# Generate a random number between 1 and 100
number_to_guess = random.randint(1, 100)
clients = []
client_names = {}
clients_ready = 0
lock = threading.Lock()

# Store the last guesses to determine who is closest
last_guesses = {}


# client connection and name registration
def handle_client(conn, addr):
    global clients_ready

    print(f"Client connected: {addr}")
    conn.send("Please enter your name: ".encode('utf-8'))
    name = conn.recv(1024).decode('utf-8')
    client_names[conn] = name
    print(f"Received name: {name}")

    with lock:
        clients_ready += 1
        if clients_ready == 2:
            start_game()

    conn.send("Waiting for other players...".encode('utf-8'))


def start_game():
    print("All clients are ready. Starting the game!")
    broadcast("Game Started!")
    print(f"Random number generated: {number_to_guess}")

    # Initialize last guesses with a high value for each client
    for conn in clients:
        last_guesses[conn] = float('inf')

    while True:
        # Each round consists of both players guessing once
        for conn in clients:
            name = client_names[conn]
            conn.send(f"Your turn to guess: ".encode('utf-8'))
            print(f"Prompting {name} to guess.")

            other_conn = [c for c in clients if c != conn][0]
            other_conn.send(f"Waiting for {name} to guess...".encode('utf-8'))

            while True:
                try:
                    guess = conn.recv(1024).decode('utf-8')
                    guess_int = int(guess)
                    if 1 <= guess_int <= 100:
                        last_guesses[conn] = guess_int
                        break  # Valid guess
                        # Add error handling for invalid input from client
                    else:
                        conn.send("Invalid guess. Please enter a number between 1 and 100.".encode('utf-8'))
                except ValueError:
                    conn.send("Invalid input. Please enter a valid number.".encode('utf-8'))
                except Exception as e:
                    conn.send(f"An error occurred: {str(e)}".encode('utf-8'))
                    print(f"Error handling client guess: {e}")
                    return

            print(f"Received guess {guess} from {name}.")

            if guess_int == number_to_guess:
                #Just declare the winner,don't need to tell each single player.
                broadcast(f"{name} guessed the number {number_to_guess} correctly! {name} wins!\n")
                print(f"{name} wins!")
                for c in clients:
                    c.close()
                return
            elif guess_int < number_to_guess:
                conn.send("Your guess is too low.".encode('utf-8'))
                print("Too low.")
                broadcast(f"{name} guessed {guess_int}. The guess is too low.\n", conn)
            else:
                conn.send("Your guess is too high.".encode('utf-8'))
                print("Too high.")
                broadcast(f"{name} guessed {guess_int}. The guess is too high.\n", conn)

        # Determine who was closest
        closest_client = min(last_guesses, key=lambda c: abs(last_guesses[c] - number_to_guess))
        closest_name = client_names[closest_client]
        #I add this to remind player which one can guess first and why.
        print(f"{closest_name} was closest in this round.")
        broadcast(f"{closest_name} was closest in this round and will guess first next.\n")

        # Reorder clients to ensure closest player guesses first next round
        clients.sort(key=lambda c: abs(last_guesses[c] - number_to_guess))


def broadcast(message, exclude_conn=None):
    for conn in clients:
        if conn != exclude_conn:
            conn.send(message.encode('utf-8'))


def start_server(ip, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((ip, port))
    server.listen(5)
    print(f"Server started on {ip}:{port}")

    while len(clients) < 2:
        conn, addr = server.accept()
        clients.append(conn)
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()


if __name__ == "__main__":
    ip = "127.0.0.1"
    port = 42345
    start_server(ip, port)









