import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Image, Table, TableStyle, Spacer, KeepTogether
import requests
from io import StringIO
import os
import pytz
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import matplotlib.dates as mdates

# Function to get the current date in India timezone
def get_indian_date():
    india_tz = pytz.timezone('Asia/Kolkata')
    return datetime.now(india_tz)

# Get today's date in India timezone
now = get_indian_date()
today = now.date()

# Calculate the date range for the report
start_time = datetime.combine(today - timedelta(days=1), datetime.min.time()) + timedelta(hours=6)
end_time = datetime.combine(today, datetime.min.time()) + timedelta(hours=6)

# Fetch the CSV file directly from the URL
url = 'https://malladi.s3.amazonaws.com/AX303.csv'
response = requests.get(url)
csv_content = response.text

# Load data from the CSV content
df = pd.read_csv(StringIO(csv_content))

# Convert the time column to datetime
time_column = 'Date&Time'  # Replace with your actual time column name
df[time_column] = pd.to_datetime(df[time_column], format='%d/%m/%y,%H:%M:%S', errors='coerce')

# Filter data for the given date range
df_filtered = df[(df[time_column] >= start_time) & (df[time_column] < end_time)]

# Identify sensor columns (excluding the time column)
sensor_columns = [col for col in df_filtered.columns if col != time_column]

# Filter out columns with all zero entries
sensor_columns = [col for col in sensor_columns if df_filtered[col].sum() != 0]

if not sensor_columns:
    raise ValueError("No valid sensor columns found in the data.")

print(f"Detected sensor columns: {sensor_columns}")

# Define color combinations for sensors
colors = ['blue', 'orange', 'green', 'red', 'purple', 'brown']

# Request for header and footer PNG files if not already provided
header_path = 'header.jpeg'
footer_path = 'footer.jpeg'

if not os.path.exists(header_path):
    raise FileNotFoundError("Please upload the header PNG file.")
    
if not os.path.exists(footer_path):
    raise FileNotFoundError("Please upload the footer PNG file.")

# Create the PDF document
report_path = 'deviation_report.pdf'
doc = SimpleDocTemplate(report_path, pagesize=letter)
elements = []

# Define a function to add header and footer
def add_header_footer(canvas, doc):
    canvas.drawImage(header_path, 0, 750, width=letter[0], height=50)  # Adjust header position
    canvas.drawImage(footer_path, 0, 0, width=letter[0], height=50)  # Adjust footer position

# Plot combined sensor data
plt.figure(figsize=(12, 6))
for i, col in enumerate(sensor_columns):
    plt.plot(df_filtered[time_column], df_filtered[col], label=col, color=colors[i % len(colors)], linestyle='-')

plt.title(f'Combined Sensor Data - {start_time.strftime("%d-%m-%Y")} to {end_time.strftime("%d-%m-%Y")}')
plt.xlabel('Time')
plt.ylabel('Value')

# Define date format for hours only
date_format = mdates.DateFormatter('%H:%M')
plt.gca().xaxis.set_major_formatter(date_format)

# Set major locator to show every hour
plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=1))

plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()

combined_plot_path = 'combined_data.png'
plt.savefig(combined_plot_path, format='png')
plt.close()

elements.append(Image(combined_plot_path, width=6*inch, height=3.5*inch))

# Prepare statistics data for the table
statistics_data = [['Sensor', 'Min Value', 'Max Value', 'Average Value', 'Mean Value', 'Median Value', 'No. Deviations']]

# Plot deviations for each sensor and compute statistics
for i, col in enumerate(sensor_columns):
    plt.figure(figsize=(12, 6))
    average = df_filtered[col].mean()
    mean = df_filtered[col].mean()
    median = df_filtered[col].median()
    deviation_threshold = 15
    deviations = df_filtered[(df_filtered[col] > mean + deviation_threshold) |
                             (df_filtered[col] < mean - deviation_threshold)]
    
    plt.plot(df_filtered[time_column], df_filtered[col], label=f'{col} Data', color=colors[i % len(colors)], linestyle='-')
    plt.axhline(y=mean, color='blue', linestyle='--', label=f'{col} Avg {mean:.2f}')
    plt.scatter(deviations[time_column], deviations[col], color='red', label=f'{col} Deviations', zorder=5)

    plt.title(f'{col} Data with Deviations - {start_time.strftime("%d-%m-%Y")} to {end_time.strftime("%d-%m-%Y")}')
    plt.xlabel('Time')
    plt.ylabel('Value')

    # Define date format for hours only
    plt.gca().xaxis.set_major_formatter(date_format)

    # Set major locator to show every hour
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=1))

    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()

    sensor_plot_path = f'{col}_data_with_deviations.png'
    plt.savefig(sensor_plot_path, format='png')
    plt.close()

    elements.append(Image(sensor_plot_path, width=6*inch, height=3.5*inch))

    # Calculate statistics
    min_value = df_filtered[col].min()
    max_value = df_filtered[col].max()
    average_value = df_filtered[col].mean()
    mean_value = df_filtered[col].mean()
    median_value = df_filtered[col].median()
    num_deviations = len(deviations)
    
    statistics_data.append([col, f'{min_value:.2f}', f'{max_value:.2f}', f'{average_value:.2f}', f'{mean_value:.2f}', f'{median_value:.2f}', num_deviations])

# Add the statistics table to the PDF
stats_table = Table(statistics_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch, 1*inch])
stats_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), (0.8, 0.8, 0.8)),
    ('TEXTCOLOR', (0, 0), (-1, 0), (0, 0, 0)),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0))
]))
elements.append(KeepTogether([stats_table]))
elements.append(Spacer(1, 24))  # Spacer to reduce gaps

# Add additional content if needed
elements.append(Spacer(1, 24))  # Spacer to reduce gaps

# Add header and footer to each page
doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)

print("PDF report generated:", report_path)

# Provide option to download the report
print("Download the PDF report from:", report_path)

# Function to generate the email body
def generate_email_body(report_date):
    return (
        f"This is an autogenerated email. Please find attached the deviation report for the data generated from {report_date.strftime('%d-%m-%Y')} to {(report_date + timedelta(days=1)).strftime('%d-%m-%Y')}.\n\n"
        "If you have any questions or need further information, please do not hesitate to contact us.\n\n"
        "Best regards,\n"
        "Reflow Technologies Pvt. Ltd."
	"Confidentiality: This email is confidential and intended only for the recipient. If you’re not the intended recipient, please notify us and delete it. Accuracy: Information provided is for informational purposes only, and we do not guarantee accuracy. Liability: We are not liable for any loss or damage arising from this email. Unsubscribing: To unsubscribe, please contact us."
    )

# Update the send_email_with_attachment function
def send_email_with_attachment(report_path):
    user = 'hello@reflowtech.in'
    password = 'cpVA thjs 0gLW'  # Application-specific password

    # Create the email
    msg = MIMEMultipart()
    msg['From'] = user
    msg['To'] = ', '.join(['vendhan@malladi.co.in','m1_maintenance@malladi.co.in','rajeshkhanna@malladi.co.in','perumal.m@malladi.co.in'])
    msg['Subject'] = 'M1 Gas Pressure Deviation Report'

    body = generate_email_body(now)
    msg.attach(MIMEText(body, 'plain'))

    # Attach the PDF file
    with open(report_path, 'rb') as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={report_path}')
        msg.attach(part)

    # Send the email
    with smtplib.SMTP('smtp.zoho.in', 587) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)

    print(f"Email sent with report: {report_path}")

# Send the email with the generated PDF report
send_email_with_attachment(report_path)
for filename in os.listdir():
    if filename.endswith('.png'):
        os.remove(filename)

print("Cleanup complete.")

