import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

# Define distinct colors and markers
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
markers = ['o', 's', '^', 'D', 'x']

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

# List of MEC systems to compare
participants_to_compare = ["2", "6", "10", "20", "30"]

# Initialize the plot
fig, ax = plt.subplots(figsize=(12, 8))

for idx, mec_systems in enumerate(participants_to_compare):
    merged_dir = f'../1-offer/{mec_systems}-mec-systems/merged'
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
            'Service Deployed': ('confirm_deployment_sent', 'confirm_deployment_received'),
            'Federated Service Running': ('establish_vxlan_connection_with_provider_start', 'establish_vxlan_connection_with_provider_finished')
        }
        for step, (start, end) in steps_definitions.items():
            if start in df.step.values and end in df.step.values:
                start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
                end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
                times_data.append({'Step': step, 'Start Time': start_time, 'End Time': end_time})

    # Filter to include only the specified steps
    filtered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployed', 'Federated Service Running']
    times_df = pd.DataFrame(times_data)
    times_df = times_df[times_df['Step'].isin(filtered_steps)]
    times_df = times_df.groupby('Step').agg({'Start Time': 'mean', 'End Time': 'mean'}).reset_index()
    ordered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployed', 'Federated Service Running']
    times_df['Order'] = times_df['Step'].apply(lambda x: ordered_steps.index(x))
    times_df = times_df.sort_values('Order', ascending=True)

    # Extract the mean start times for each step
    mean_starts = times_df['Start Time'].values

    # Plot the mean start times
    ax.plot(mean_starts, ordered_steps, marker=markers[idx], markersize=8, linewidth=2, color=colors[idx], label=f'{mec_systems}')

# Add a zoomed-in section for 2 participants
zoom_ax = inset_axes(ax, width="40%", height="30%", loc='lower right', borderpad=4)

# Process data for 2 participants for zoomed-in plot
merged_dir = '../1-offer/2-mec-systems/merged'
times_data = []
for filename in os.listdir(merged_dir):
    filepath = os.path.join(merged_dir, filename)
    df = pd.read_csv(filepath)
    steps_definitions = {
        'Service Announced': ('service_announced', 'announce_received'),
        'Bid Offered': ('bid_offer_sent', 'bid_offer_received'),
        'Winner Choosen': ('winner_choosen', 'winner_received'),
        'Service Deployed': ('confirm_deployment_sent', 'confirm_deployment_received'),
        'Federated Service Running': ('establish_vxlan_connection_with_provider_start', 'establish_vxlan_connection_with_provider_finished')
    }
    for step, (start, end) in steps_definitions.items():
        if start in df.step.values and end in df.step.values:
            start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
            end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
            times_data.append({'Step': step, 'Start Time': start_time, 'End Time': end_time})

filtered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployed', 'Federated Service Running']
times_df = pd.DataFrame(times_data)
times_df = times_df[times_df['Step'].isin(filtered_steps)]
times_df = times_df.groupby('Step').agg({'Start Time': 'mean', 'End Time': 'mean'}).reset_index()
ordered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployed', 'Federated Service Running']
times_df['Order'] = times_df['Step'].apply(lambda x: ordered_steps.index(x))
times_df = times_df.sort_values('Order', ascending=True)
mean_starts = times_df['Start Time'].values

# Plot the mean start times in the zoomed-in section
zoom_ax.plot(mean_starts, ordered_steps, marker='o', markersize=10, linewidth=2, color=colors[0])

# Formatting for the zoomed-in section
zoom_ax.set_yticks(range(len(ordered_steps)))
zoom_ax.set_yticklabels([])
zoom_ax.tick_params(axis='x', labelsize=10)  # Set x-axis tick label size
zoom_ax.grid(True, linestyle=(0, (5, 10)), color='grey', alpha=0.7)  # More discontinuous lines
zoom_ax.spines['top'].set_color('black')
zoom_ax.spines['right'].set_color('black')
zoom_ax.spines['bottom'].set_color('black')
zoom_ax.spines['left'].set_color('black')

# Main plot formatting
ax.set_ylabel('Federation Procedures', fontsize=14)
ax.set_xlabel('Time (s)', fontsize=14)
ax.set_yticks(range(len(ordered_steps)))
ax.set_yticklabels(ordered_steps, fontsize=12)
ax.tick_params(axis='x', labelsize=12)
ax.grid(True, linestyle=(0, (5, 10)), color='grey', alpha=0.7)  # More discontinuous lines
ax.spines['top'].set_color('black')
ax.spines['right'].set_color('black')
ax.spines['bottom'].set_color('black')
ax.spines['left'].set_color('black')
ax.legend(title='MEC systems', loc='upper left', fontsize=12)

plt.tight_layout()
plt.savefig('federation_events_composite_graph.pdf')
plt.show()
