import uvicorn
import os

# Define the host and port for the application
# Use environment variables if available, otherwise default to localhost:8000
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

if __name__ == "__main__":
    print(f"Starting Memo Flow server at http://{HOST}:{PORT}")

    # uvicorn.run() is the programmatic way to start the server.
    # "app.main:app": Uvicorn will look for the 'app' instance in the 'app/main.py' file.
    # host: Binds the server to this address. '127.0.0.1' is localhost.
    # port: The port number to listen on.
    # reload=True: The server will automatically restart when code changes are detected.
    #              This is very useful for development. Set to False in production.
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)