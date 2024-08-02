import os
import csv
import re
from pathlib import Path
from statistics import mean

def calculate_merged_statistics(directory, num_tests):
    for test_num in range(1, num_tests + 1):
        send_registration_times = []
        confirm_registration_times = []
        
        # Collect timestamps from all participants for the current test number
        for file in directory.glob(f'federation_registration_participant*_test_{test_num}.csv'):
            with open(file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['step'] == 'send_registration_transaction':
                        send_registration_times.append(float(row['timestamp']))
                    elif row['step'] == 'confirm_registration_transaction':
                        confirm_registration_times.append(float(row['timestamp']))

        if send_registration_times and confirm_registration_times:
            mean_send_registration = mean(send_registration_times)
            mean_confirm_registration = mean(confirm_registration_times)

            yield test_num, mean_send_registration, mean_confirm_registration

def write_merged_csv(merged_dir, test_num, mean_send_registration, mean_confirm_registration):
    output_file = merged_dir / f'federation_registration_merged_test_{test_num}.csv'
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['step', 'timestamp'])
        writer.writerow(['send_registration_transaction', mean_send_registration])
        writer.writerow(['confirm_registration_transaction', mean_confirm_registration])
    print(f'Merged test {test_num} statistics written to {output_file}')

def process_directory(directory):
    print(f'Processing directory: {directory}')

    # Determine the number of tests based on one participant's files
    participant_files = list(directory.glob('federation_registration_participant1_test_*.csv'))
    num_tests = len(participant_files)

    # Create the merged directory
    merged_dir = directory / 'merged'
    merged_dir.mkdir(exist_ok=True)

    # Calculate and write merged statistics
    for test_num, mean_send_registration, mean_confirm_registration in calculate_merged_statistics(directory, num_tests):
        write_merged_csv(merged_dir, test_num, mean_send_registration, mean_confirm_registration)

if __name__ == '__main__':
    base_dir = './registration-time'
    system_dirs = [d for d in os.listdir(base_dir) if re.match(r'\d+-mec-systems', d)]

    print("Available system directories:")
    for i, d in enumerate(system_dirs, 1):
        print(f"{i}. {d}")

    choice = int(input("Enter the number corresponding to the directory you want to process: ")) - 1
    selected_system_dir = os.path.join(base_dir, system_dirs[choice])

    process_directory(Path(selected_system_dir))
