from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import shutil
from pathlib import Path
import os
import subprocess

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_FOLDER = "temp"
DZI_FOLDER = "dzi"

# Verificar si las carpetas existen, de lo contrario, crearlas
for folder in [TEMP_FOLDER, DZI_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

@app.post("/uploade/")
async def upload_image(file: UploadFile = File(...)):
    # Generar una ruta única para cada imagen
    image_path = f"{TEMP_FOLDER}/{file.filename}"
    
    # Eliminar cualquier archivo anterior en la carpeta temporal
    for f in os.listdir(TEMP_FOLDER):
        os.remove(os.path.join(TEMP_FOLDER, f))

    # Guardar la nueva imagen
    with open(Path(image_path), "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Generar el archivo DZI usando la utilidad de línea de comandos vips
    dzi_path = f"{DZI_FOLDER}/{file.filename}.dzi"
    process = subprocess.run(["vips", "dzsave", image_path, dzi_path])

    if process.returncode == 0:
        return {"message": "Imagen cargada y DZI generado con éxito", "filename": dzi_path}
    else:
        return {"message": "Error al generar DZI", "filename": image_path}
