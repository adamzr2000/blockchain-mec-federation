import os
import re

def rename_files(directory):
    files = [f for f in os.listdir(directory) if f.endswith('.csv')]
    files.sort(key=lambda x: int(re.findall(r'\d+', x)[0]))

    for index, filename in enumerate(files, start=1):
        new_filename = f"federation_events_consumer_test_{index}.csv"
        old_path = os.path.join(directory, filename)
        new_path = os.path.join(directory, new_filename)
        os.rename(old_path, new_path)
        print(f"Renamed {old_path} to {new_path}")

if __name__ == "__main__":
    directories = ["consumer-2", "consumer-3", "consumer-4", "consumer-5", "consumer-6", "consumer-7", "consumer-8", "consumer-9", "consumer-10", "consumer-11", "consumer-12", "consumer-13", "consumer-14", "consumer-15"]
    for directory in directories:
        rename_files(directory)
