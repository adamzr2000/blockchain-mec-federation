import os
import csv
import re
from pathlib import Path

def adjust_timestamps(events, registration_send, registration_confirm):
    adjustment_time = registration_confirm - registration_send
    adjusted_events = []

    for step, timestamp in events:
        if step == "send_registration_transaction":
            adjusted_events.append((step, registration_send))
        elif step == "confirm_registration_transaction":
            adjusted_events.append((step, registration_confirm))
        else:
            adjusted_events.append((step, float(timestamp) + adjustment_time))
    
    return adjusted_events

def read_csv(file_path):
    data = []
    with open(file_path, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            data.append((row[0], float(row[1])))
    return data

def write_csv(file_path, data):
    with open(file_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['step', 'timestamp'])
        writer.writerows(data)
    print(f'Written adjusted timestamps to {file_path}')

def process_files(events_dir, registration_dir, output_dir, num_tests):
    for test_num in range(1, num_tests + 1):
        events_file = events_dir / f'federation_events_merged_test_{test_num}.csv'
        registration_file = registration_dir / f'federation_registration_merged_test_{test_num}.csv'

        if not events_file.exists() or not registration_file.exists():
            print(f"Skipping test {test_num}: Missing files")
            continue

        events = read_csv(events_file)
        registration = read_csv(registration_file)

        send_registration_time = registration[0][1]
        confirm_registration_time = registration[1][1]

        # Add registration steps to events
        events.insert(0, ("confirm_registration_transaction", confirm_registration_time))
        events.insert(0, ("send_registration_transaction", send_registration_time))

        adjusted_events = adjust_timestamps(events, send_registration_time, confirm_registration_time)
        output_file = output_dir / f'federation_events_merged_test_{test_num}.csv'
        write_csv(output_file, adjusted_events)

def list_system_dirs(base_dir):
    return [d for d in os.listdir(base_dir) if re.match(r'\d+-mec-systems', d)]

def main():
    base_dir = './15-offer_v1'
    registration_base_dir = './registration-time'
    system_dirs = list_system_dirs(base_dir)

    print("Available system directories:")
    for i, d in enumerate(system_dirs, 1):
        print(f"{i}. {d}")

    choice = int(input("Enter the number corresponding to the directory you want to process: ")) - 1
    selected_system_dir = system_dirs[choice]

    events_dir = Path(base_dir) / selected_system_dir / 'merged'
    registration_dir = Path(registration_base_dir) / selected_system_dir / 'merged'
    output_dir = Path(base_dir) / selected_system_dir / 'merged-with-registration'
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine the number of tests based on one participant's files
    num_tests = len(list(events_dir.glob('federation_events_merged_test_*.csv')))

    process_files(events_dir, registration_dir, output_dir, num_tests)

if __name__ == '__main__':
    main()
