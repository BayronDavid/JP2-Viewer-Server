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
    with open(f"{TEMP_FOLDER}/sample_metadata.txt", "w") as meta:
        meta.write("sample.jp2\n")

@app.post("/upload/")
async def upload_image(file: UploadFile = File(...), format: str = Form(...)):
    unique_id = uuid.uuid4().hex
    original_name = file.filename  # Guarda el nombre original con la extensión
    image_path = f"{TEMP_FOLDER}/{unique_id}.jp2"
    dzi_path = f"{DZI_FOLDER}/{unique_id}"
    metadata_path = f"{TEMP_FOLDER}/{unique_id}_metadata.txt"

    # Guardar la nueva imagen y metadata
    with open(Path(image_path), "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    with open(Path(metadata_path), "w") as meta:
        meta.write(f"{original_name}\n")

    # Ajustar opciones basadas en el formato
    suffix_option = f".{format}"
    if format == "webp":
        suffix_option += "[Q=80]"

    # Generar el archivo DZI
    process = subprocess.run(["vips", "dzsave", image_path, dzi_path, "--suffix", suffix_option])

    if process.returncode == 0:
        return {"message": "Imagen cargada y DZI generado con éxito", "filename": original_name, "id": unique_id}
    else:
        raise HTTPException(status_code=500, detail="Error al generar DZI")

@app.get("/api/list_images")
async def list_images():
    images = []
    for metadata_file in glob.glob(f"{TEMP_FOLDER}/*_metadata.txt"):
        meta_path = Path(metadata_file)
        unique_id = meta_path.stem.split('_')[0]
        original_name = meta_path.read_text().strip()
        dzi_path = f"{DZI_FOLDER}/{unique_id}.dzi"
        if os.path.exists(dzi_path):
            stats = Path(dzi_path).stat()
            images.append({
                "filename": original_name,
                "id": unique_id,
                "size": stats.st_size,
                "modified_time": stats.st_mtime
            })
    return images

@app.delete("/api/delete_image/{image_id}")
async def delete_image(image_id: str):
    paths_to_delete = glob.glob(f"{TEMP_FOLDER}/{image_id}.*") + glob.glob(f"{DZI_FOLDER}/{image_id}.*") + glob.glob(f"{TEMP_FOLDER}/{image_id}_metadata.txt")
    for file in paths_to_delete:
        os.remove(file)
    return {"message": "Imagen eliminada con éxito"}



@app.get("/api/get_dzi_info")
async def get_dzi_info(image_id: str = None):
    if image_id:
        dzi_path = f"{DZI_FOLDER}/{image_id}.dzi"
        if os.path.exists(dzi_path):
            dzi_url = f"http://127.0.0.1:8000/dzi/{image_id}.dzi"
            return {"filename": dzi_url}
        else:
            raise HTTPException(status_code=404, detail="DZI no encontrado para el ID proporcionado")
    else:
        # Si no se proporciona un ID, devolver el DZI de muestra
        sample_dzi_path = f"http://127.0.0.1:8000/dzi/sample.dzi"
        return {"filename": sample_dzi_path}


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
