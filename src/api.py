import fastapi


if __name__ == "__main__":
    import uvicorn

    load_dotenv()
    
    PORT = 8000

    if not os.getenv('ENV'):
        print("Missing environment variable.")
        exit(1)
    
    if not os.getenv('API_KEY'):
        print("Missing API key.")
        exit(1)

    if os.getenv('ENV') == "DEBUG":
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try: 
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]

            print("\n\nServer available @ http://" + ip_address + ":" + str(PORT) + "\n\n")
        except OSError as e:
            print(e)

    if os.getenv('ENV') == "PROD":
        print("Please consider the following command to start the server:")
        print("\t EXPERIMENTAL: uvicorn your_app_module:app --workers 3")
        
    global health 
    health = Health(status=Status.OK, ENV=os.getenv('ENV'))
    uvicorn.run(app, host="0.0.0.0", port=PORT)