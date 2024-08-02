import os
import csv
import re
from pathlib import Path
from statistics import mean, stdev

def calculate_statistics(directory):
    send_registration_times = []
    confirm_registration_times = []

    for file in directory.glob('federation_registration_participant*_test_*.csv'):
        with open(file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['step'] == 'send_registration_transaction':
                    send_registration_times.append(float(row['timestamp']))
                elif row['step'] == 'confirm_registration_transaction':
                    confirm_registration_times.append(float(row['timestamp']))
    
    mean_send_registration = mean(send_registration_times) if send_registration_times else 0
    mean_confirm_registration = mean(confirm_registration_times) if confirm_registration_times else 0
    
    stdev_send_registration = stdev(send_registration_times) if len(send_registration_times) > 1 else 0
    stdev_confirm_registration = stdev(confirm_registration_times) if len(confirm_registration_times) > 1 else 0

    return (mean_send_registration, mean_confirm_registration, 
            stdev_send_registration, stdev_confirm_registration)

def write_statistics_csv(mean_dir, mean_send_registration, mean_confirm_registration, 
                         stdev_send_registration, stdev_confirm_registration):
    output_file = mean_dir / 'federation_registration_mean.csv'
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['statistic', 'send_registration', 'confirm_registration'])
        writer.writerow(['mean', mean_send_registration, mean_confirm_registration])
        writer.writerow(['stdev', stdev_send_registration, stdev_confirm_registration])
    print(f'Statistics written to {output_file}')

def process_directory(directory):
    print(f'Processing directory: {directory}')
    stats = calculate_statistics(directory)
    
    # Create the mean directory if it doesn't exist
    mean_dir = directory / 'mean'
    mean_dir.mkdir(exist_ok=True)
    
    write_statistics_csv(mean_dir, *stats)

if __name__ == '__main__':
    base_dir = './registration-time'
    system_dirs = [d for d in os.listdir(base_dir) if re.match(r'\d+-mec-systems', d)]

    print("Available system directories:")
    for i, d in enumerate(system_dirs, 1):
        print(f"{i}. {d}")

    choice = int(input("Enter the number corresponding to the directory you want to process: ")) - 1
    selected_system_dir = os.path.join(base_dir, system_dirs[choice])
    
    process_directory(Path(selected_system_dir))
