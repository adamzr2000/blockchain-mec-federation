import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns


lighter_green = '#D5E8D4' 
darker_green = '#82B366'

lighter_blue = '#DAE8FC' 
darker_blue = '#6C8EBF'

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
merged_dir = '../1-offer/2-mec-systems/merged'
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
bar_height = 0.95  # Reduced height for the bars
for i, step in enumerate(ordered_steps):
    mean_start = times_df.loc[times_df['Step'] == step, 'Start Time'].values[0]
    mean_end = times_df.loc[times_df['Step'] == step, 'End Time'].values[0]
    mean_duration = mean_end - mean_start
    
    if step in ['Service Deployment', 'Establish VXLAN Connection']:
        color = lighter_green
        edgecolor = darker_green
        label = 'Deployment procedure' if 'Deployment procedure' not in plt.gca().get_legend_handles_labels()[1] else ""
    else:
        color = lighter_blue
        edgecolor = darker_blue
        label = 'Federation procedure using blockchain' if 'Federation procedure using blockchain' not in plt.gca().get_legend_handles_labels()[1] else ""
        
    plt.barh(i, mean_duration, left=mean_start, color=color, edgecolor=edgecolor, label=label, height=bar_height)

plt.yticks(range(len(ordered_steps)), ordered_steps)
plt.xlabel('Time (s)')
plt.ylabel('Procedures')
plt.legend(loc='upper right', fontsize=12)
plt.tight_layout()
plt.gca().invert_yaxis()
plt.savefig('federation_events.pdf')
plt.show()

# --- Plot 2: Mean accumulated time for consumer and provider ---
consumer_dir = '../1-offer/2-mec-systems/consumer'
provider_dir = '../1-offer/2-mec-systems/provider-1'
mean_accumulated_time_consumer = calculate_mean_accumulated_time(consumer_dir)
mean_accumulated_time_provider = calculate_mean_accumulated_time(provider_dir)

domains = ['Consumer', 'Provider']
mean_times = [mean_accumulated_time_consumer, mean_accumulated_time_provider]

plt.figure(figsize=(8, 4))
colors = [lighter_green, lighter_blue]
edge_colors = [darker_green, darker_blue]

barplot = plt.barh(domains, mean_times, color=colors, edgecolor=edge_colors)
for bar, time in zip(barplot, mean_times):
    plt.text(time, bar.get_y() + bar.get_height()/2, f"{time:.2f}s", va='center', ha='right', color='black', fontweight='bold')


plt.xlabel('Time (s)')
plt.ylabel('Domain')
# plt.title('Mean accumulated time')
plt.tight_layout()
plt.gca().invert_yaxis()
plt.savefig('total_accumulated_time.pdf')
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
for i, (mean_time, std_time) in enumerate(zip(mean_times, std_times)):
    plt.text(i, mean_time + std_time, f"{mean_time:.2f}s\n±{std_time:.2f}s", ha='center', va='bottom', fontweight='bold')

plt.xlabel('Steps')
plt.ylabel('Time (s)')
# plt.title('Mean time for each step with standard deviation')
plt.tight_layout()
plt.savefig('federation_steps.pdf')
plt.show()

# --- Plot 4: Events for consumer and provider with corresponding timestamps ---
# Mapping step numbers to step names
step_mapping = {
    1: 'service_announced',
    2: 'announce_received',
    3: 'bid_offer_sent',
    4: 'bid_offer_received',
    5: 'winner_choosen',
    6: 'winner_received',
    7: 'deployment_start',
    8: 'deployment_finished',
    9: 'confirm_deployment_sent',
    10: 'confirm_deployment_received',
    11: 'establish_vxlan_connection_with_provider_start',
    12: 'establish_vxlan_connection_with_provider_finished'
}

# Defining consumer and provider steps using step names
consumer_steps = [step_mapping[1], step_mapping[4], step_mapping[5], step_mapping[10], step_mapping[11], step_mapping[12]]
provider_steps = [step_mapping[2], step_mapping[3], step_mapping[6], step_mapping[7], step_mapping[8], step_mapping[9]]

# Capture timestamps for each step for each domain
consumer_times = {step: [] for step in consumer_steps}
provider_times = {step: [] for step in provider_steps}

for filename in os.listdir(merged_dir):
    filepath = os.path.join(merged_dir, filename)
    df = pd.read_csv(filepath)

    for step in consumer_steps:
        if step in df['step'].values:
            timestamp = df.loc[df['step'] == step, 'timestamp'].values[0]
            consumer_times[step].append(timestamp)

    for step in provider_steps:
        if step in df['step'].values:
            timestamp = df.loc[df['step'] == step, 'timestamp'].values[0]
            provider_times[step].append(timestamp)

# Calculate mean timestamps for each step, handle missing data
mean_consumer_times = {step: np.mean(times) if times else np.nan for step, times in consumer_times.items()}
mean_provider_times = {step: np.mean(times) if times else np.nan for step, times in provider_times.items()}
min_consumer_times = {step: np.min(times) if times else np.nan for step, times in consumer_times.items()}
max_consumer_times = {step: np.max(times) if times else np.nan for step, times in consumer_times.items()}
min_provider_times = {step: np.min(times) if times else np.nan for step, times in provider_times.items()}
max_provider_times = {step: np.max(times) if times else np.nan for step, times in provider_times.items()}

# Prepare data for plotting
plot_data = []
for step, time in mean_consumer_times.items():
    if not np.isnan(time):
        plot_data.append({'Domain': 'Consumer', 'Step': step, 'Time': time, 'StepNumber': list(step_mapping.keys())[list(step_mapping.values()).index(step)]})
for step, time in mean_provider_times.items():
    if not np.isnan(time):
        plot_data.append({'Domain': 'Provider', 'Step': step, 'Time': time, 'StepNumber': list(step_mapping.keys())[list(step_mapping.values()).index(step)]})

plot_df = pd.DataFrame(plot_data)

# Plotting
plt.figure(figsize=(12, 6))

# Add horizontal bars for min and max, and vertical line for mean time
for idx, row in plot_df.iterrows():
    y_center = 0.5 if row['Domain'] == 'Consumer' else -0.5
    y_range = 0.1  # Adjust this value to control the length of the line
    color = lighter_blue if row['Domain'] == 'Consumer' else lighter_green
    mean_time = row['Time']
    min_time = min_consumer_times[row['Step']] if row['Domain'] == 'Consumer' else min_provider_times[row['Step']]
    max_time = max_consumer_times[row['Step']] if row['Domain'] == 'Consumer' else max_provider_times[row['Step']]
    
    # Add horizontal bars for min and max
    plt.barh(y_center, max_time - min_time, left=min_time, height=0.2, color=color, alpha=0.6)
    
    # Add vertical line for mean time
    plt.axvline(x=mean_time, ymin=(y_center - y_range + 1) / 2, ymax=(y_center + y_range + 1) / 2, color='black', linestyle='-', alpha=0.8)
    plt.text(mean_time, y_center, str(row['StepNumber']), verticalalignment='center', horizontalalignment='center', color='black', fontweight='bold')

plt.yticks([0.5, -0.5], ['Consumer', 'Provider'])
plt.ylim(-1, 1)
plt.xlabel('Timestamp')
plt.ylabel('Domain')
# plt.title('Events for Consumer and Provider with Corresponding Timestamps')
plt.tight_layout()
plt.savefig('federation_events_v2.pdf')
plt.show()