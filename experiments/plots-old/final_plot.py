import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns

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
sns.set_style('ticks')

# List of MEC systems to compare
participants_to_compare = ["2", "6", "10", "20", "30"]

# Initialize the plot
fig, ax = plt.subplots(figsize=(14, 10))

for idx, mec_systems in enumerate(participants_to_compare):
    merged_dir = f'../1-offer/{mec_systems}-mec-systems/merged'
    times_data = []

    # Process each merged file
    for filename in os.listdir(merged_dir):
        filepath = os.path.join(merged_dir, filename)
        df = pd.read_csv(filepath)

        # Capture start and end times for each step
        steps_definitions = {
            'Request Federation': ('service_announced', 'announce_received'),
            'Bid Offered': ('bid_offer_sent', 'bid_offer_received'),
            'Provider Chosen': ('winner_choosen', 'winner_received'),
            'Service Deployed': ('confirm_deployment_sent', 'confirm_deployment_received'),
            'Federation Completed': ('establish_vxlan_connection_with_provider_start', 'establish_vxlan_connection_with_provider_finished')
        }
        for step, (start, end) in steps_definitions.items():
            if start in df.step.values and end in df.step.values:
                start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
                end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
                times_data.append({'Step': step, 'Start Time': start_time, 'End Time': end_time})

    # Filter to include only the specified steps
    filtered_steps = ['Request Federation', 'Bid Offered', 'Provider Chosen', 'Service Deployed', 'Federation Completed']
    times_df = pd.DataFrame(times_data)
    times_df = times_df[times_df['Step'].isin(filtered_steps)]
    times_df = times_df.groupby('Step').agg({'Start Time': 'mean', 'End Time': 'mean'}).reset_index()
    ordered_steps = ['Request Federation', 'Bid Offered', 'Provider Chosen', 'Service Deployed', 'Federation Completed']
    times_df['Order'] = times_df['Step'].apply(lambda x: ordered_steps.index(x))
    times_df = times_df.sort_values('Order', ascending=True)

    # Extract the mean start times for each step
    mean_starts = times_df['Start Time'].values
    mean_ends = times_df['End Time'].values

    # Adjust the mean times for plotting
    mean_times = np.copy(mean_starts)
    mean_times[ordered_steps.index('Federation Completed')] = mean_ends[ordered_steps.index('Federation Completed')]

    # Plot the mean start times
    ax.plot(mean_times, ordered_steps, marker=markers[idx], markersize=8, linewidth=2, color=colors[idx], label=f'{mec_systems} MEC systems')

# Main plot formatting
ax.set_ylabel('Federation Procedures', fontsize=18)
ax.set_xlabel('Time (s)', fontsize=18)
ax.set_yticks(range(len(ordered_steps)))
ax.set_yticklabels(ordered_steps, fontsize=16)
ax.tick_params(axis='x', labelsize=16, length=10, width=1.1)  # Increase tick length and set width
ax.tick_params(axis='y', labelsize=16, length=10, width=1.1)  # Increase tick length and set width
ax.grid(True, linestyle='--', color='grey', alpha=0.5)  # More discontinuous lines
ax.spines['top'].set_color('black')
ax.spines['right'].set_color('black')
ax.spines['bottom'].set_color('black')
ax.spines['left'].set_color('black')
ax.spines['top'].set_linewidth(1.1)  # Set the same width for all spines
ax.spines['right'].set_linewidth(1.1)
ax.spines['bottom'].set_linewidth(1.1)
ax.spines['left'].set_linewidth(1.1)
legend = ax.legend(loc='upper left', fontsize=16, frameon=True, bbox_to_anchor=(0.02, 0.98), borderaxespad=0.)
legend.get_frame().set_edgecolor('black')
legend.get_frame().set_linewidth(1.1)
plt.setp(legend.get_frame(), boxstyle="square")

plt.tight_layout()
plt.savefig('federation_events_composite_graph.pdf')
plt.show()
