import os
import glob

def modify_csv_files(base_dir):
    # Get a list of all provider directories
    provider_dirs = glob.glob(os.path.join(base_dir, 'provider-1'))

    # Define the replacement mapping
    replacements = {
        "deployment_start_service_0_service_0": "deployment_start_service_0",
        "deployment_finished_service_0_service_0": "deployment_finished_service_0",
        "confirm_deployment_sent_service_0_service_0": "confirm_deployment_sent_service_0",
        "deployment_start_service_0_service_2": "deployment_start_service_2",
        "deployment_finished_service_0_service_2": "deployment_finished_service_2",
        "confirm_deployment_sent_service_0_service_2": "confirm_deployment_sent_service_2"
    }

    # Loop through each provider directory
    for provider_dir in provider_dirs:
        # Get all CSV files in the current provider directory
        csv_files = glob.glob(os.path.join(provider_dir, '*.csv'))
        
        # Loop through each CSV file
        for csv_file in csv_files:
            # Read the contents of the file
            with open(csv_file, 'r') as file:
                content = file.read()
            
            # Replace the strings according to the mapping
            for old_value, new_value in replacements.items():
                content = content.replace(old_value, new_value)
            
            # Write the modified contents back to the file
            with open(csv_file, 'w') as file:
                file.write(content)

            print(f"Modified {csv_file}")

if __name__ == "__main__":
    base_dir = '.'  # Change this to your base directory if needed
    modify_csv_files(base_dir)

