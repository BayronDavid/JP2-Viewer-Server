from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import glob
import os
import subprocess
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/dzi", StaticFiles(directory="dzi"), name="dzi")

TEMP_FOLDER = "temp"
DZI_FOLDER = "dzi"

# Verificar si las carpetas existen, de lo contrario, crearlas
for folder in [TEMP_FOLDER, DZI_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    # Generar un identificador único para la imagen
    unique_id = uuid.uuid4().hex

    # Generar las rutas para el archivo original y el DZI
    image_path = f"{TEMP_FOLDER}/{unique_id}.jp2"
    dzi_path = f"{DZI_FOLDER}/{unique_id}"

    # Guardar la nueva imagen
    with open(Path(image_path), "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Generar el archivo DZI
    process = subprocess.run(["vips", "dzsave", image_path, dzi_path])

    if process.returncode == 0:
        return {"message": "Imagen cargada y DZI generado con éxito", "filename": f"{dzi_path}.dzi"}
    else:
        return {"message": "Error al generar DZI", "filename": image_path}


@app.get("/api/get_dzi_info")
async def get_dzi_info():
    # Busca todos los archivos .dzi en la carpeta "dzi"
    dzi_files = glob.glob("dzi/*.dzi")

    if not dzi_files:
        raise HTTPException(status_code=404, detail="No se encontraron archivos DZI")

    latest_dzi = max(dzi_files, key=os.path.getctime)

    # Construye la URL completa (ajusta esto según la configuración de tu servidor)
    dzi_url = f"http://127.0.0.1:8000/{latest_dzi}"

    return {"filename": dzi_url}


@app.get("/dzi/{filename}")
async def read_dzi(filename: str):
    file_path = f"{DZI_FOLDER}/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    
    return FileResponse(
        path=file_path,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )
