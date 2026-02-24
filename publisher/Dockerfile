# Use a Python base image
FROM python:3.12

# Set the working directory inside the container ('app' is a convention for the working directory's name)
WORKDIR /app

EXPOSE 5678
EXPOSE 8000

# Copy the requirements.txt file and install the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python file(s) to the working directory ('COPY main.py .' copy only the main file while 'COPY . .' copy all files)
COPY . .

# Command to run the web parameters interface
CMD ["python", "-u", "scripts/parameters_web.py"]
