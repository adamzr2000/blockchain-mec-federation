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

lighter_purple = '#E1D5E7' 
darker_purple = '#9673A6'

lighter_orange = '#FFE6CC' 
darker_orange = '#D79B00'

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

mec_systems = 30
merged_dir = f'../{mec_systems}-mec-systems/merged'

# --- Plot 1: Mean start and end times of each federation step ---
# Directory containing merged test results

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
        'Federated Service Running': ('establish_vxlan_connection_with_provider_start', 'establish_vxlan_connection_with_provider_finished')
    }
    for step, (start, end) in steps_definitions.items():
        if start in df.step.values and end in df.step.values:
            start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
            end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
            times_data.append({'Step': step, 'Start Time': start_time, 'End Time': end_time})

times_df = pd.DataFrame(times_data)
times_df = times_df.groupby('Step').agg({'Start Time': 'mean', 'End Time': 'mean'}).reset_index()
ordered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployment', 'Confirm Service Deployment', 'Federated Service Running']
times_df['Order'] = times_df['Step'].apply(lambda x: ordered_steps.index(x))
times_df = times_df.sort_values('Order', ascending=True)

# plt.figure(figsize=(10, 6))
# for i, step in enumerate(ordered_steps):
#     mean_start = times_df.loc[times_df['Step'] == step, 'Start Time'].values[0]
#     mean_end = times_df.loc[times_df['Step'] == step, 'End Time'].values[0]
#     mean_duration = mean_end - mean_start
#     plt.barh(i, mean_duration, left=mean_start, color=lighter_blue, edgecolor=darker_blue)
#     # plt.text(mean_start + mean_duration / 2, i, f"{mean_duration:.2f}s", va='center', ha='center', color='black',fontweight='bold')

# plt.yticks(range(len(ordered_steps)), ordered_steps)
# plt.xlabel('Time (s)')
# plt.ylabel('Phases')
# plt.title('Mean start and end times of each federation step')
# plt.tight_layout()
# plt.gca().invert_yaxis()
# plt.savefig(f'federation_events_{mec_systems}_mec_systems.pdf')
# plt.show()



# --- Plot 2: Mean accumulated time for consumer and provider ---
# consumer_dir =  f'../{mec_systems}-mec-systems/consumer'
# provider_dir =  f'../{mec_systems}-mec-systems/provider-1'
# mean_accumulated_time_consumer = calculate_mean_accumulated_time(consumer_dir)
# mean_accumulated_time_provider = calculate_mean_accumulated_time(provider_dir)

# domains = ['Consumer', 'Provider']
# mean_times = [mean_accumulated_time_consumer, mean_accumulated_time_provider]

# plt.figure(figsize=(8, 4))
# colors = [lighter_green, lighter_blue]
# edge_colors = [darker_green, darker_blue]

# barplot = plt.barh(domains, mean_times, color=colors, edgecolor=edge_colors)
# # for bar, time in zip(barplot, mean_times):
# #     plt.text(time, bar.get_y() + bar.get_height()/2, f"{time:.2f}s", va='center', ha='right', color='black', fontweight='bold')


# plt.xlabel('Time (s)')
# plt.ylabel('MEC System')
# plt.title('Mean accumulated time')
# plt.tight_layout()
# plt.gca().invert_yaxis()
# plt.savefig(f'total_accumulated_time_{mec_systems}_mec_systems.pdf')
# plt.show()

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

# plt.figure(figsize=(10, 6))
# plt.bar(ordered_steps, mean_times, yerr=std_times, color=lighter_blue, edgecolor=darker_blue, capsize=5)
# # for i, (mean_time, std_time) in enumerate(zip(mean_times, std_times)):
# #     plt.text(i, mean_time + std_time, f"{mean_time:.2f}s\n±{std_time:.2f}s", ha='center', va='bottom', fontweight='bold')
# plt.xticks(rotation=45, ha='right')  # Rotate x-axis labels for better readability
# plt.xlabel('Steps')
# plt.ylabel('Time (s)')
# plt.title('Mean time for each step with standard deviation')
# plt.tight_layout()
# plt.savefig(f'federation_steps_{mec_systems}_mec_systems.pdf')
# plt.show()

# --- Plot 4: --- #
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
participants_to_compare = ["2", "6", "10", "15", "20", "30"]
colors = [lighter_blue, lighter_green, lighter_red, lighter_yellow, lighter_purple, lighter_orange]
edge_colors = [darker_blue, darker_green, darker_red, darker_yellow, darker_purple, darker_orange]
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
plt.savefig('comparison_total_federation_time.pdf')
plt.show()

# --- Plot 5: --- 
steps_definitions = {
    'Service Announced': ('service_announced', 'announce_received'),
    'Bid Offered': ('bid_offer_sent', 'bid_offer_received'),
    'Winner Choosen': ('winner_choosen', 'winner_received'),
    'Service Deployment': ('deployment_start', 'deployment_finished'),
    'Confirm Service Deployment': ('confirm_deployment_sent', 'confirm_deployment_received'),
    'Federated Service Running': ('establish_vxlan_connection_with_provider_start', 'establish_vxlan_connection_with_provider_finished')
}

# Function to calculate the total federation time for each file
def calculate_step_times(directory, steps_definitions):
    step_times = {step: [] for step in steps_definitions.keys()}
    for filename in os.listdir(directory):
        if filename.endswith(".csv"):
            df = pd.read_csv(os.path.join(directory, filename))
            for step, (start, end) in steps_definitions.items():
                if start in df.step.values and end in df.step.values:
                    start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
                    end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
                    step_times[step].append(end_time - start_time)
    return step_times

# Set the seaborn style for aesthetics
sns.set_style("whitegrid")

# List of MEC systems to compare
participants_to_compare = ["2", "6", "10", "15", "20", "30"]
colors = [lighter_blue, lighter_green, lighter_red, lighter_yellow, lighter_purple, lighter_orange]
edge_colors = [darker_blue, darker_green, darker_red, darker_yellow, darker_purple, darker_orange]

# Initialize data storage
mean_times = {step: [] for step in steps_definitions.keys()}
std_times = {step: [] for step in steps_definitions.keys()}

# Calculate mean and standard deviation for each step across multiple MEC systems
for mec_systems, color, edge_color in zip(participants_to_compare, colors, edge_colors):
    merged_dir = f'../{mec_systems}-mec-systems/merged'
    step_times = calculate_step_times(merged_dir, steps_definitions)
    
    for step in steps_definitions.keys():
        mean_times[step].append(np.mean(step_times[step]))
        std_times[step].append(np.std(step_times[step]))

# Plot the mean time for each step with standard deviation for multiple MEC systems
plt.figure(figsize=(22, 12))

x = np.arange(len(steps_definitions))  # the label locations
width = 0.12  # the width of the bars

# Create bar plots for each MEC system
for i, (mec_systems, lighter_color, darker_color) in enumerate(zip(participants_to_compare, colors, edge_colors)):
    means = [mean_times[step][i] for step in steps_definitions.keys()]
    stds = [std_times[step][i] for step in steps_definitions.keys()]
    plt.bar(x + i * width, means, width, yerr=stds, label=f'{mec_systems}', color=lighter_color, edgecolor=darker_color, capsize=5)

# Add labels, title, and legend
plt.xlabel('Federation Steps')
plt.ylabel('Time (s)')
# plt.title('Mean Time for Each Step with Standard Deviation')
plt.xticks(x + width * (len(participants_to_compare) - 1) / 2, steps_definitions.keys(), rotation=45, ha='right')
plt.legend(title='Number of MEC Systems')
plt.tight_layout()
plt.savefig('comparison_federation_steps.pdf')

# Show the plot
plt.show()
# --- Plot 6: --- 
# Function to calculate start and end times for each step
# def calculate_times(directory, steps_definitions):
#     times_data = []
#     for filename in os.listdir(directory):
#         if filename.endswith(".csv"):
#             df = pd.read_csv(os.path.join(directory, filename))
#             for step, (start, end) in steps_definitions.items():
#                 if start in df.step.values and end in df.step.values:
#                     start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
#                     end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
#                     times_data.append({'Step': step, 'Start Time': start_time, 'End Time': end_time})
#     return times_data

# # Set the seaborn style for aesthetics
# sns.set_style("whitegrid")

# # List of MEC systems to compare
# participants_to_compare = ["2", "3", "4", "6"]
# colors = [lighter_blue, lighter_green, lighter_red, lighter_yellow]
# edge_colors = [darker_blue, darker_green, darker_red, darker_yellow]
# # Function to calculate start and end times for each step
# def calculate_times(directory, steps_definitions):
#     times_data = []
#     for filename in os.listdir(directory):
#         if filename.endswith(".csv"):
#             df = pd.read_csv(os.path.join(directory, filename))
#             for step, (start, end) in steps_definitions.items():
#                 if start in df.step.values and end in df.step.values:
#                     start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
#                     end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
#                     times_data.append({'Step': step, 'Start Time': start_time, 'End Time': end_time})
#     return times_data

# # Set the seaborn style for aesthetics
# sns.set_style("whitegrid")



# # Initialize data storage
# all_times_data = []

# # Calculate start and end times for each step across multiple MEC systems
# for mec_systems in participants_to_compare:
#     merged_dir = f'../{mec_systems}-mec-systems/merged'
#     times_data = calculate_times(merged_dir, steps_definitions)
#     times_df = pd.DataFrame(times_data)
#     times_df = times_df.groupby('Step').agg({'Start Time': 'mean', 'End Time': 'mean'}).reset_index()
#     times_df['MEC Systems'] = mec_systems
#     all_times_data.append(times_df)

# # Concatenate all data into a single DataFrame
# all_times_df = pd.concat(all_times_data)

# # Order the steps
# ordered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployment', 'Confirm Service Deployment', 'Federated Service Running']
# all_times_df['Order'] = all_times_df['Step'].apply(lambda x: ordered_steps.index(x))
# all_times_df = all_times_df.sort_values('Order', ascending=True)

# # Plot the mean start and end times for each step for multiple MEC systems
# plt.figure(figsize=(16, 10))

# bar_width = 0.2  # the width of the bars
# x = np.arange(len(ordered_steps))  # the label locations

# # Create bar plots for each MEC system
# for i, (mec_systems, color, edge_color) in enumerate(zip(participants_to_compare, colors, edge_colors)):
#     mec_df = all_times_df[all_times_df['MEC Systems'] == mec_systems]
#     start_times = mec_df['Start Time'].values
#     end_times = mec_df['End Time'].values
#     plt.bar(x + i * bar_width, start_times, bar_width, label=f'{mec_systems} MEC Systems Start', color=color, edgecolor=edge_color)
#     plt.bar(x + i * bar_width + bar_width / 2, end_times, bar_width, label=f'{mec_systems} MEC Systems End', color=color, edgecolor=edge_color, hatch='//')

# # Add labels, title, and legend
# plt.xticks(x + bar_width * (len(participants_to_compare) - 1) / 2, ordered_steps, rotation=45, ha='right')
# plt.xlabel('Steps')
# plt.ylabel('Time (s)')
# plt.title('Mean Start and End Times of Each Federation Step')
# plt.legend(title='Number of Providers', loc='upper left')
# plt.tight_layout()

# # Show the plot
# plt.show()