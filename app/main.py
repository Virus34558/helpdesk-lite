from fastapi import FastAPI

app = FastAPI(title="HelpDesk Lite", description="Gestor de incidencias IT")

@app.get("/")
def inicio():
    return {"mensaje": "HelpDesk Lite funcionando"}