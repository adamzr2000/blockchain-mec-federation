import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns


lighter_green = '#D5E8D4' 
darker_green = '#82B366'

lighter_blue = '#DAE8FC' 
darker_blue = '#6C8EBF'

lighter_red = '#F8CECC' 
darker_red = '#B85450'

lighter_yellow = '#FFF2CC' 
darker_yellow = '#D6B656'

# Function to calculate mean accumulated time
def calculate_mean_accumulated_time(directory):
    accumulated_times = []
    for filename in os.listdir(directory):
        if filename.endswith(".csv"):
            df = pd.read_csv(os.path.join(directory, filename))
            accumulated_time = df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
            accumulated_times.append(accumulated_time)
    return np.mean(accumulated_times)

# Set the seaborn style for aesthetics
sns.set_style("whitegrid")

# --- Plot 1: Mean start and end times of each federation step ---
# Directory containing merged test results
mec_systems = 6
merged_dir = f'../{mec_systems}-mec-systems/merged'
times_data = []

# Process each merged file
for filename in os.listdir(merged_dir):
    filepath = os.path.join(merged_dir, filename)
    df = pd.read_csv(filepath)

    # Capture start and end times for each step
    steps_definitions = {
        'Service Announced': ('service_announced', 'announce_received'),
        'Bid Offered': ('bid_offer_sent', 'bid_offer_received'),
        'Winner Choosen': ('winner_choosen', 'winner_received'),
        'Service Deployment': ('deployment_start', 'deployment_finished'),
        'Confirm Service Deployment': ('confirm_deployment_sent', 'confirm_deployment_received'),
        'Establish VXLAN Connection': ('establish_vxlan_connection_with_provider_start', 'establish_vxlan_connection_with_provider_finished')
    }
    for step, (start, end) in steps_definitions.items():
        if start in df.step.values and end in df.step.values:
            start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
            end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
            times_data.append({'Step': step, 'Start Time': start_time, 'End Time': end_time})

times_df = pd.DataFrame(times_data)
times_df = times_df.groupby('Step').agg({'Start Time': 'mean', 'End Time': 'mean'}).reset_index()
ordered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployment', 'Confirm Service Deployment', 'Establish VXLAN Connection']
times_df['Order'] = times_df['Step'].apply(lambda x: ordered_steps.index(x))
times_df = times_df.sort_values('Order', ascending=True)

plt.figure(figsize=(10, 6))
for i, step in enumerate(ordered_steps):
    mean_start = times_df.loc[times_df['Step'] == step, 'Start Time'].values[0]
    mean_end = times_df.loc[times_df['Step'] == step, 'End Time'].values[0]
    mean_duration = mean_end - mean_start
    plt.barh(i, mean_duration, left=mean_start, color=lighter_blue, edgecolor=darker_blue)
    # plt.text(mean_start + mean_duration / 2, i, f"{mean_duration:.2f}s", va='center', ha='center', color='black',fontweight='bold')

plt.yticks(range(len(ordered_steps)), ordered_steps)
plt.xlabel('Time (s)')
plt.ylabel('Phases')
# plt.title('Mean start and end times of each federation step')
plt.tight_layout()
plt.gca().invert_yaxis()
# plt.savefig(f'federation_events_{mec_systems}_mec_systems.pdf')
plt.show()



# --- Plot 2: Mean accumulated time for consumer and provider ---
consumer_dir =  f'../{mec_systems}-mec-systems/consumer'
provider_dir =  f'../{mec_systems}-mec-systems/provider-1'
mean_accumulated_time_consumer = calculate_mean_accumulated_time(consumer_dir)
mean_accumulated_time_provider = calculate_mean_accumulated_time(provider_dir)

domains = ['Consumer', 'Provider']
mean_times = [mean_accumulated_time_consumer, mean_accumulated_time_provider]

plt.figure(figsize=(8, 4))
colors = [lighter_green, lighter_blue]
edge_colors = [darker_green, darker_blue]

barplot = plt.barh(domains, mean_times, color=colors, edgecolor=edge_colors)
# for bar, time in zip(barplot, mean_times):
#     plt.text(time, bar.get_y() + bar.get_height()/2, f"{time:.2f}s", va='center', ha='right', color='black', fontweight='bold')


plt.xlabel('Time (s)')
plt.ylabel('MEC System')
# plt.title('Mean accumulated time')
plt.tight_layout()
plt.gca().invert_yaxis()
plt.savefig(f'total_accumulated_time_{mec_systems}_mec_systems.pdf')
plt.show()

# --- Plot 3: Mean time for each step with standard deviation ---
# Calculate mean and standard deviation for each step
mean_times = []
std_times = []

for step, (start, end) in steps_definitions.items():
    step_times = []
    for filename in os.listdir(merged_dir):
        filepath = os.path.join(merged_dir, filename)
        df = pd.read_csv(filepath)
        if start in df.step.values and end in df.step.values:
            start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
            end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
            step_times.append(end_time - start_time)
    mean_times.append(np.mean(step_times))
    std_times.append(np.std(step_times))

plt.figure(figsize=(10, 6))
plt.bar(ordered_steps, mean_times, yerr=std_times, color=lighter_blue, edgecolor=darker_blue, capsize=5)
# for i, (mean_time, std_time) in enumerate(zip(mean_times, std_times)):
#     plt.text(i, mean_time + std_time, f"{mean_time:.2f}s\n±{std_time:.2f}s", ha='center', va='bottom', fontweight='bold')
plt.xticks(rotation=45, ha='right')  # Rotate x-axis labels for better readability
plt.xlabel('Steps')
plt.ylabel('Time (s)')
# plt.title('Mean time for each step with standard deviation')
plt.tight_layout()
plt.savefig(f'federation_steps_{mec_systems}_mec_systems.pdf')
plt.show()

# --- Plot 4: ---
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

# List of MEC systems to compare
participants_to_compare = ["2", "3", "4", "6"]
colors = [lighter_blue, lighter_green, lighter_red, lighter_yellow]
edge_colors = [darker_blue, darker_green, darker_red, darker_yellow]
mean_times = []
std_times = []

for mec_systems in participants_to_compare:
    merged_dir = f'../{mec_systems}-mec-systems/merged'
    total_federation_times = calculate_total_federation_time(merged_dir)
    mean_times.append(np.mean(total_federation_times))
    std_times.append(np.std(total_federation_times))

# Plot the mean total federation time with standard deviation
plt.figure(figsize=(10, 6))
plt.bar(participants_to_compare, mean_times, yerr=std_times, color=colors, edgecolor=edge_colors, capsize=5)
plt.xlabel('Number of MEC Systems')
plt.ylabel('Federation Time (s)')
plt.tight_layout()
plt.savefig('comparison.pdf')
plt.show()