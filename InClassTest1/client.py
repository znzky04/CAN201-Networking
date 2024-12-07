import socket
import argparse

def start_client(server_ip, port):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((server_ip, port))

    while True:
        message = client.recv(1024).decode('utf-8')
        print(message)

        # Enter name
        if "Please enter your name" in message:
            name = input()
            client.send(name.encode('utf-8'))

        # When it's your turn to guess, send the guess
        if "Your turn to guess" in message:
            while True:
                guess = input("Enter your guess (1-100): ")
                try:
                    guess_int = int(guess)
                    if 1 <= guess_int <= 100:
                        client.send(guess.encode('utf-8'))
                        break  # Valid guess, exit loop
                    else:
                        print("Please enter a number between 1 and 100.")
                except ValueError:
                    print("Invalid input. Please enter a valid number.")

        # Exit the game when a winner is announced
        if "wins" in message or "Game over" in message:
            break

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='TCP Client for Number Guessing Game')
    parser.add_argument('--ip', type=str, required=True, help='Server IP address')
    parser.add_argument('--port', type=int, required=True, help='Server port')

    args = parser.parse_args()

    start_client(args.ip, args.port)


