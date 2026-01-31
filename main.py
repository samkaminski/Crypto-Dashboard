from fastapi import FastAPI

#create a FastAPI application instance
#Main app object that handles routing and requests
app = FastAPI()

#Register a GET route at / (root path)
@app.get("/")
def read_root():
    return {"message": "Hello World! FastAPI is working."}


@app.get("/health")
def health_check():
    return {"status": "ok"}
