from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends
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
DEFAULT_IMAGE_PATH = "temp/sample.jp2"
DEFAULT_DZI_PATH = f"{DZI_FOLDER}/sample"

# Verificar si las carpetas existen, de lo contrario, crearlas
for folder in [TEMP_FOLDER, DZI_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Generar DZI por defecto al inicio del servidor
if os.path.exists(DEFAULT_IMAGE_PATH):
    subprocess.run(["vips", "dzsave", DEFAULT_IMAGE_PATH, DEFAULT_DZI_PATH])

@app.post("/upload/")
async def upload_image(file: UploadFile = File(...), format: str = Form(...)):
    unique_id = uuid.uuid4().hex
    original_name = file.filename.rsplit('.', 1)[0]  # Guarda el nombre original sin extensión
    image_path = f"{TEMP_FOLDER}/{unique_id}.jp2"
    dzi_path = f"{DZI_FOLDER}/{unique_id}"

    # Guardar la nueva imagen
    with open(Path(image_path), "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Ajustar opciones basadas en el formato
    suffix_option = f".{format}"
    if format == "webp":
        suffix_option += "[Q=80]"

    # Generar el archivo DZI
    process = subprocess.run(["vips", "dzsave", image_path, dzi_path, "--suffix", suffix_option])

    if process.returncode == 0:
        return {"message": "Imagen cargada y DZI generado con éxito", "filename": f"{original_name}.{format}.dzi", "id": unique_id}
    else:
        raise HTTPException(status_code=500, detail="Error al generar DZI")

@app.get("/api/list_images")
async def list_images():
    images = []
    for dzi_file in glob.glob("dzi/*.dzi"):
        file_path = Path(dzi_file)
        stats = file_path.stat()
        images.append({
            "filename": file_path.stem,  # El nombre base sin la extensión
            "size": stats.st_size,
            "modified_time": stats.st_mtime
        })
    return images

@app.delete("/api/delete_image/{image_id}")
async def delete_image(image_id: str):
    # Busca y elimina el archivo de imagen original y su DZI correspondiente
    for file in glob.glob(f"{TEMP_FOLDER}/{image_id}.*") + glob.glob(f"{DZI_FOLDER}/{image_id}.*"):
        os.remove(file)
    return {"message": "Imagen eliminada con éxito"}

@app.get("/api/get_dzi_info")
async def get_dzi_info():
    dzi_files = glob.glob("dzi/*.dzi")
    
    if not dzi_files:
        dzi_url = f"http://127.0.0.1:8000/dzi/sample.dzi"
        return {"filename": dzi_url}

    latest_dzi = max(dzi_files, key=os.path.getctime)
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
