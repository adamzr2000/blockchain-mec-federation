import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns

# Define the colors
lighter_blue = '#DAE8FC' 
darker_blue = '#6C8EBF'

# Function to calculate the total federation time for each file
def calculate_total_federation_time(directory):
    total_times = []
    for filename in os.listdir(directory):
        if filename.endswith(".csv"):
            df = pd.read_csv(os.path.join(directory, filename))
            total_time = df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
            total_times.append(total_time)
    return total_times

# Set the seaborn style for aesthetics
sns.set_style("whitegrid")

# Directory containing the test results
mec_systems = 30
offers = 10
merged_dir = f'../{offers}-offer/{mec_systems}-mec-systems/merged'

# Calculate the total federation time for the given directory
total_federation_times = calculate_total_federation_time(merged_dir)
mean_total_time = np.mean(total_federation_times)
std_total_time = np.std(total_federation_times)

# Plot the total federation time
plt.figure(figsize=(10, 6))
plt.bar(['Total Federation Time'], [mean_total_time], yerr=[std_total_time], color=lighter_blue, edgecolor=darker_blue, capsize=5)
plt.xlabel('Test')
plt.ylabel('Federation Time (s)')
plt.title(f'Total Federation Time for {mec_systems} participants - 10 Consumers and 20 Constant Providers')
plt.tight_layout()
plt.savefig('total_federation_time.pdf')
plt.show()
