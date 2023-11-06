# Usar una imagen base de Python
FROM python:3.9

# Instalar libvips y OpenJPG
RUN apt-get update && apt-get install -y libvips-dev libopenjp2-7

# Establecer el directorio de trabajo en /app
WORKDIR /app

# Copiar el archivo de requerimientos e instalar las dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código fuente
COPY . .

# Exponer el puerto donde se ejecutará FastAPI
EXPOSE 8000

# Comando para ejecutar la aplicación usando Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
