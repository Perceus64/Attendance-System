import time
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
from PIL import Image, ImageTk
import datetime
import tkinter as tk
import cv2
import os
import csv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# Initialize the RFID reader
reader = SimpleMFRC522()

# Set up GPIO
GPIO.setwarnings(False)
led_pin = 12
GPIO.setmode(GPIO.BOARD)
GPIO.setup(led_pin, GPIO.OUT)

# Function to load user data from the CSV file
def load_user_data():
    user_data = {}
    # Path of users.csv
    with open('/home/Desktop/users.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_id = int(row['user_id'])
            user_data[user_id] = {
                'name': row['name'],
                'email': row['email'],
                'folder': row['folder'],
                'attendance': {
                    'timestamp': row['timestamp'],
                    'image_file': row['image_file']
                }
            }
    return user_data

# Load user data from the CSV file
user_data = load_user_data()

# Create a directory for each user if it doesn't exist already
for user_id, user_info in user_data.items():
    folder_name = user_info['folder']
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)

# Create a Tkinter window
window = tk.Tk()
window.title('RFID Attendance System')

# Set the initial size and position of the window
window.geometry('800x600')
window.update_idletasks()
window_width = window.winfo_width()
window_height = window.winfo_height()
screen_width = window.winfo_screenwidth()
screen_height = window.winfo_screenheight()

# Create a frame to hold the welcome label and the canvas
frame = tk.Frame(window)
frame.pack(pady=20)

# Add a label to display the welcome message
welcome_label = tk.Label(frame, font=('Arial', 14), text="Hold your RFID tag near the reader:")
welcome_label.pack()

# Create a canvas to hold the image
canvas = tk.Canvas(window, width=window_width, height=window_height - 100)
canvas.pack()

# Update the Tkinter window
window.update()

# Function to update the UI with the latest attendance data and image
def update_ui(name, img_path):
    welcome_label.config(text=f"Welcome, {name}!")

    # Load the image
    img = Image.open(img_path)

    # Calculate the scale factor to fit the image within the canvas
    scale = min((window_width - 20) / img.width, (window_height - 100) / img.height)
    new_width = int(img.width * scale)
    new_height = int(img.height * scale)

    # Resize the image
    img = img.resize((new_width, new_height), Image.ANTIALIAS)

    # Convert the image to a Tkinter PhotoImage and update the canvas
    img = ImageTk.PhotoImage(img)
    canvas.create_image(window_width // 2, (window_height - 100) // 2, image=img)
    canvas.image = img

# Function to clear the UI and reset to the initial state
def clear_ui():
    welcome_label.config(text="Hold your RFID tag near the reader:")
    canvas.delete("all")

# Function to display an error message in the console
def show_error(message):
    print(f"Error: {message}")

# Function to update the status message in the console
def update_status(message):
    print(message)

# Function to send attendance details and photo to the user via email
def send_email(user_email, user_name, timestamp, image_file):
    # Email configuration
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    smtp_username = 'INSERT YOUR SMTP USERNAME HERE'
    smtp_password = 'INSERT YOUR SMTP PASSWORD HERE'
    sender_email = 'INSERT YOUR SMTP SENDER EMAIL HERE'
    subject = 'Attendance Confirmation'
    body = f'Dear {user_name},\n\nYou have successfully checked in at {timestamp}.' \
           f'\n\nPlease find your photo attached below.' \
           f'\n\nBest regards,' \
           f'\nAttendance System'

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = user_email
    message['Subject'] = subject

    # Attach the body of the email
    message.attach(MIMEText(body, 'plain'))

    # Attach the photo
    with open(image_file, 'rb') as file:
        image_data = file.read()
        image = MIMEImage(image_data)
        image.add_header('Content-Disposition', 'attachment', filename=os.path.basename(image_file))
        message.attach(image)

    # Create a secure SSL context and send the email
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(message)
            print(f"Email sent to {user_email}")
    except Exception as e:
        print(f"Failed to send email to {user_email}: {str(e)}")

# Function to capture an image and save it to the user's folder
def capture_image(user_info):
    cap = cv2.VideoCapture(0)
    # Reduce the image resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    ret, frame = cap.read()
    cap.release()

    img_name = f"{user_info['name']}_{datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S')}.jpg"
    img_path = os.path.join(user_info['folder'], img_name)
    # Save the image in JPEG format with compression quality 80
    cv2.imwrite(img_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 80])

    return img_path

# Function to update attendance data and write to a CSV file
def update_attendance_data():
    with open('attendance.csv', 'w') as f:
        for user_id, user_info in user_data.items():
            attendance = user_info['attendance']
            f.write(f"{user_info['name']},{attendance['timestamp']},{attendance['image_file']}\n")

# Function to handle RFID tag read event
def handle_rfid_tag_read(id, text):
    if id in user_data:
        user_info = user_data[id]
        name = user_info['name']
        user_email = user_info['email']

        # Capture an image and save it to the user's folder
        img_path = capture_image(user_info)

        # Update attendance data
        attendance = user_info['attendance']
        attendance['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        attendance['image_file'] = img_path

        print(f"{name} checked in at {attendance['timestamp']}")

        # Update the UI with the latest attendance data and image
        update_ui(name, img_path)

        # Toggle the LED
        GPIO.output(led_pin, GPIO.HIGH)
        time.sleep(0.1)
        GPIO.output(led_pin, GPIO.LOW)

        # Write attendance data to a CSV file
        update_attendance_data()

        # Send attendance details and photo to the user via email
        if user_email:
            send_email(user_email, name, attendance['timestamp'], attendance['image_file'])

        # Update the Tkinter window
        window.update()

        # Update the status message
        update_status(f"Checked in: {name}")

        # Wait for a few seconds before clearing the UI and status message
        time.sleep(3)

        # Clear the UI and reset to the initial state
        clear_ui()
        update_status("System ready.")

# RFID tag read event loop
try:
    while True:
        # Read RFID tag
        id, text = reader.read()

        # Handle RFID tag read event
        handle_rfid_tag_read(id, text)

except KeyboardInterrupt:
    print("Program stopped by user")

finally:
    GPIO.cleanup()
