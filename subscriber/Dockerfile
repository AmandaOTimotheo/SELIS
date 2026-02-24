# Use a Python base image
FROM python:3.12

# Set the working directory inside the container ('app' is a convention for the working directory's name)
WORKDIR /app

# Install tkinter and other system dependencies (to make the iterative plot available ' UserWarning: FigureCanvasAgg is non-interactive, and thus cannot be shown')
RUN apt-get update && apt-get install -y python3-tk

# Copy the requirements.txt file and install the dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python file(s) to the working directory ('COPY main.py .' copy only the main file while 'COPY . .' copy all files)
COPY . .

# Command to run the Python script
CMD ["python", "-u", "subscriber.py"]