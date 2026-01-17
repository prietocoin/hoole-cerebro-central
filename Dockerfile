# Usamos la imagen oficial de Playwright que coincida con la librería instalada
FROM mcr.microsoft.com/playwright/python:v1.57.0-jammy

# Directorio de trabajo
WORKDIR /app

# Copiamos dependencias
COPY requirements.txt .

# Instalamos dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código
COPY . .

# Exponemos el puerto de FastAPI
EXPOSE 8000

# Comando para arrancar la aplicación
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
