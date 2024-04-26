from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pathlib import Path
import shutil
import glob
import os
import subprocess
import uuid
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Access-Control-Allow-Origin"] 
)
app.mount("/dzi", StaticFiles(directory="dzi"), name="dzi")

TEMP_FOLDER = "temp"
DZI_FOLDER = "dzi"
DEFAULT_IMAGE_PATH = "temp/sample.jp2"
DEFAULT_DZI_PATH = f"{DZI_FOLDER}/sample"


THUMBNAIL_LEVELS = [8, 7, 4, 2] 

# Verificar si las carpetas existen, de lo contrario, crearlas
for folder in [TEMP_FOLDER, DZI_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Generar DZI por defecto al inicio del servidor
if os.path.exists(DEFAULT_IMAGE_PATH):
    # Proceso para generar el archivo DZI
    subprocess.run(["vips", "dzsave", DEFAULT_IMAGE_PATH, DEFAULT_DZI_PATH])
    
    # Crear archivo JSON de metadatos para la imagen por defecto
    metadata_path = f"{TEMP_FOLDER}/sample_metadata.json"
    metadata = {
        "original_name": "sample.jp2",
        "annotations": []  # Lista inicial vacía para anotaciones
    }
    with open(metadata_path, "w") as meta:
        json.dump(metadata, meta)


@app.post("/upload/")
async def upload_image(file: UploadFile = File(...), format: str = Form(...)):
    unique_id = uuid.uuid4().hex
    original_name = file.filename
    image_path = f"{TEMP_FOLDER}/{unique_id}.jp2"
    dzi_path = f"{DZI_FOLDER}/{unique_id}"
    metadata_path = f"{TEMP_FOLDER}/{unique_id}_metadata.json"

    # Guardar la nueva imagen
    with open(Path(image_path), "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Crear archivo JSON de metadatos
    metadata = {
        "original_name": original_name,
        "annotations": []  # Lista vacía para futuras anotaciones
    }
    with open(Path(metadata_path), "w") as meta:
        json.dump(metadata, meta)

    # Proceso para generar el archivo DZI
    suffix_option = f".{format}"
    if format == "webp":
        suffix_option += "[Q=100]"
    process = subprocess.run(["vips", "dzsave", image_path, dzi_path, "--suffix", suffix_option])

    if process.returncode == 0:
        return {"message": "Imagen cargada y DZI generado con éxito", "filename": original_name, "id": unique_id}
    else:
        raise HTTPException(status_code=500, detail="Error al generar DZI")

@app.get("/api/list_images")
async def list_images():
    images = []
    for metadata_file in glob.glob(f"{TEMP_FOLDER}/*_metadata.json"):
        meta_path = Path(metadata_file)
        unique_id = meta_path.stem.split('_')[0]
        with open(meta_path, "r") as file:
            data = json.load(file)
            original_name = data["original_name"]
        dzi_path = f"{DZI_FOLDER}/{unique_id}.dzi"
        if os.path.exists(dzi_path):
            stats = Path(dzi_path).stat()

            # Buscar miniatura en los niveles de zoom
            thumbnail_url = find_thumbnail(dzi_path, unique_id)
            if thumbnail_url:
                images.append({
                    "filename": original_name,
                    "id": unique_id,
                    "size": stats.st_size,
                    "modified_time": stats.st_mtime,
                    "thumbnail_url": thumbnail_url
                })
    return images

@app.delete("/api/delete_image/{image_id}")
async def delete_image(image_id: str):
    paths_to_delete = glob.glob(f"{TEMP_FOLDER}/{image_id}.*") + glob.glob(f"{DZI_FOLDER}/{image_id}.*") + glob.glob(f"{TEMP_FOLDER}/{image_id}_metadata.json")
    
    # Agrega la carpeta que deseas eliminar junto con su contenido
    folder_to_delete = f"{DZI_FOLDER}/{image_id}_files"
    
    # Agrega la carpeta a la lista de elementos a eliminar
    paths_to_delete.append(folder_to_delete)
    
    # Elimina todos los elementos en la lista
    for item in paths_to_delete:
        if os.path.isdir(item):
            # Si es un directorio, utiliza shutil.rmtree() para eliminarlo recursivamente
            shutil.rmtree(item)
        else:
            os.remove(item)
    
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

# Anotations
@app.post("/api/annotations/{image_id}")
async def add_annotation(image_id: str, annotation: dict):
    metadata_path = f"{TEMP_FOLDER}/{image_id}_metadata.json"
    if os.path.exists(metadata_path):
        with open(metadata_path, "r+") as file:
            data = json.load(file)
            data['annotations'].append(annotation)
            file.seek(0)
            json.dump(data, file)
            file.truncate()
        return {"message": "Anotación añadida con éxito"}
    else:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

@app.get("/api/annotations/{image_id}")
async def get_annotations(image_id: str):
    metadata_path = f"{TEMP_FOLDER}/{image_id}_metadata.json"
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as file:
            data = json.load(file)
        return data['annotations']
    else:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

@app.put("/api/annotations/{image_id}/{annotation_id}")
async def update_annotation(image_id: str, annotation_id: str, new_annotation: dict):
    metadata_path = f"{TEMP_FOLDER}/{image_id}_metadata.json"
    if os.path.exists(metadata_path):
        with open(metadata_path, "r+") as file:
            data = json.load(file)
            # Buscar y actualizar la anotación por su ID
            annotations = data['annotations']
            annotation_index = next((i for i, anno in enumerate(annotations) if anno['id'] == annotation_id), None)
            if annotation_index is not None:
                annotations[annotation_index].update(new_annotation)
                file.seek(0)
                json.dump(data, file)
                file.truncate()
                return {"message": "Anotación actualizada con éxito"}
            else:
                raise HTTPException(status_code=404, detail="Anotación no encontrada")
    else:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

@app.delete("/api/annotations/{image_id}/{annotation_id}")
async def delete_annotation(image_id: str, annotation_id: str): 
    metadata_path = f"{TEMP_FOLDER}/{image_id}_metadata.json"
    if os.path.exists(metadata_path):
        with open(metadata_path, "r+") as file:
            data = json.load(file)
            # Buscar y eliminar la anotación correcta por su ID
            annotations = data['annotations']
            new_annotations = [anno for anno in annotations if anno['id'] != annotation_id]
            if len(annotations) == len(new_annotations):
                raise HTTPException(status_code=404, detail="Anotación no encontrada")
            data['annotations'] = new_annotations
            file.seek(0)
            json.dump(data, file)
            file.truncate()
        return {"message": "Anotación eliminada con éxito"}
    else:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")





def find_thumbnail(dzi_path, unique_id):
    for level in THUMBNAIL_LEVELS:
        level_folder = f"{DZI_FOLDER}/{unique_id}_files/{level}"
        if os.path.exists(level_folder):
            files = os.listdir(level_folder)
            if files:  # Verificar si hay archivos en la carpeta
                first_file = files[0]  # Tomar el primer archivo
                return f"http://127.0.0.1:8000/{level_folder}/{first_file}"
    return None