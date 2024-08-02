import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Patch

# Define step definitions globally to avoid repetition
steps_definitions = {
    'Registration': ('send_registration_transaction', 'confirm_registration_transaction'),
    'Request Federation': ('service_announced', 'announce_received'),
    'Bid Offered': ('bid_offer_sent', 'bid_offer_received'),
    'Provider Chosen': ('winner_choosen', 'winner_received'),
    'Service Deployed\nand Running': ('deployment_start', 'establish_vxlan_connection_with_provider_finished')
}

# Function to calculate mean accumulated time
def calculate_mean_accumulated_time(directory):
    accumulated_times = []
    for filename in os.listdir(directory):
        if filename.endswith(".csv"):
            df = pd.read_csv(os.path.join(directory, filename))
            if not df.empty:
                accumulated_time = df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
                accumulated_times.append(accumulated_time)
    if accumulated_times:
        return np.mean(accumulated_times)
    else:
        return np.nan

# Function to calculate step times for a given directory
def calculate_step_times(directory):
    step_times = {step: [] for step in steps_definitions.keys()}
    step_times['Total Federation\nTime'] = []
    
    for filename in os.listdir(directory):
        if filename.endswith(".csv"):
            df = pd.read_csv(os.path.join(directory, filename))
            total_time = 0
            for step, (start, end) in steps_definitions.items():
                if start in df['step'].values and end in df['step'].values:
                    start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
                    end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
                    duration = end_time - start_time
                    if step != 'Registration':  # Exclude the registration step
                        total_time += duration
                    step_times[step].append(duration)
            step_times['Total Federation\nTime'].append(total_time)
    return step_times

# Plot 1: Mean start and end times of each federation step
def plot_mean_start_end_times(directory):
    times_data = []

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        df = pd.read_csv(filepath)
        for step, (start, end) in steps_definitions.items():
            if start in df['step'].values and end in df['step'].values:
                start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
                end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
                times_data.append({'Step': step, 'Start Time': start_time, 'End Time': end_time})

    times_df = pd.DataFrame(times_data)
    times_df = times_df.groupby('Step').agg({'Start Time': 'mean', 'End Time': 'mean'}).reset_index()
    ordered_steps = list(steps_definitions.keys()) + ['Total Federation\nTime']
    times_df['Order'] = times_df['Step'].apply(lambda x: ordered_steps.index(x))
    times_df = times_df.sort_values('Order', ascending=True)
    return times_df

# Process additional dataset
additional_dir = '../10-offer/30-mec-systems/merged-with-registration'
additional_step_times = calculate_step_times(additional_dir)

additional_mean_times = {step: np.mean(additional_step_times[step]) if additional_step_times[step] else np.nan for step in additional_step_times.keys()}
additional_std_times = {step: np.std(additional_step_times[step]) if additional_step_times[step] else np.nan for step in additional_step_times.keys()}

# Plot 5: Comparison of federation steps
def plot_federation_steps_comparison(participants_to_compare, steps_colors, additional_mean_times, additional_std_times):
    mean_times = {step: [] for step in list(steps_definitions.keys()) + ['Total Federation\nTime']}
    std_times = {step: [] for step in list(steps_definitions.keys()) + ['Total Federation\nTime']}
    
    hatches = ['///', 'xxx', '\\\\\\', '...', '---', '|||', 'xxx', 'ooo', '***', '...', '---']
    
    for mec_systems in participants_to_compare:
        merged_dir = f'../1-offer/{mec_systems}-mec-systems/merged-with-registration'
        step_times = calculate_step_times(merged_dir)

        for step in mean_times.keys():
            if step_times[step]:  # Ensure there are values to calculate mean and std
                mean_times[step].append(np.mean(step_times[step]))
                std_times[step].append(np.std(step_times[step]))
            else:
                mean_times[step].append(np.nan)
                std_times[step].append(np.nan)

    # Debugging: Print mean and std times
    print("Mean Times:", mean_times)
    print("Standard Deviation Times:", std_times)

    # Set the seaborn style for aesthetics
    sns.set_style('ticks')

    plt.figure(figsize=(16, 10))  # Automatically adjusted figure size
    x = np.arange(len(mean_times))  # the label locations
    width = 0.1  # the width of the bars
    group_width = 0.12  # the total width of each group of bars

    for i, mec_systems in enumerate(participants_to_compare):
        for j, (step, color) in enumerate(steps_colors.items()):
            means = mean_times[step][i]
            stds = std_times[step][i]
            # Plot error bars first
            plt.errorbar(x[j] + i * group_width, means, yerr=stds, fmt='none', ecolor='black', capsize=5, zorder=0)
            # Plot bars on top
            plt.bar(x[j] + i * group_width, means, width, color=color, hatch=hatches[i], edgecolor='black', zorder=1, label=f'{mec_systems} MEC systems' if j == 0 else "")

    # Plot additional dataset with distinctive hatch pattern
    additional_hatch = '++'
    for j, (step, color) in enumerate(steps_colors.items()):
        additional_means = additional_mean_times[step]
        additional_stds = additional_std_times[step]
        # Plot error bars first
        plt.errorbar(x[j] + group_width * len(participants_to_compare), additional_means, yerr=additional_stds, fmt='none', ecolor='black', capsize=5, zorder=0)
        # Plot bars on top
        plt.bar(x[j] + group_width * len(participants_to_compare), additional_means, width, color=color, hatch=additional_hatch, edgecolor='black', zorder=1, label='30 MEC systems [10 consumers, 20 providers]' if j == 0 else "")

    plt.xlabel('Federation Procedures', fontsize=18, labelpad=20)  # Add more space between label and axis names
    plt.ylabel('Time (s)', fontsize=18, labelpad=20)
    plt.xticks(x + group_width * (len(participants_to_compare) - 1) / 2, list(mean_times.keys()), fontsize=16)
    plt.yticks(fontsize=16)
    plt.tick_params(axis='x', labelsize=16, length=10, width=1.1)  # Increase tick length and set width
    plt.tick_params(axis='y', labelsize=16, length=10, width=1.1)  # Increase tick length and set width
    plt.grid(True, linestyle='--', color='grey', alpha=0.5)  # More discontinuous lines
    plt.gca().spines['top'].set_color('black')
    plt.gca().spines['right'].set_color('black')
    plt.gca().spines['bottom'].set_color('black')
    plt.gca().spines['left'].set_color('black')
    plt.gca().spines['top'].set_linewidth(1.1)  # Set the same width for all spines
    plt.gca().spines['right'].set_linewidth(1.1)
    plt.gca().spines['bottom'].set_linewidth(1.1)
    plt.gca().spines['left'].set_linewidth(1.1)

    # Create custom legend handles
    custom_legend_handles = [Patch(facecolor='white', edgecolor='black', hatch=hatch, label=f'{mec_systems} MEC systems') for mec_systems, hatch in zip(participants_to_compare, hatches)]
    custom_legend_handles.append(Patch(facecolor='white', edgecolor='black', hatch=additional_hatch, label='30 MEC systems [10 consumers, 20 providers]'))
    
    legend = plt.legend(handles=custom_legend_handles, loc='upper left', fontsize=16, frameon=True, bbox_to_anchor=(0.02, 0.98), borderaxespad=0.)
    legend.get_frame().set_edgecolor('black')
    legend.get_frame().set_linewidth(1.1)
    plt.setp(legend.get_frame(), boxstyle="square")

    plt.tight_layout(pad=2)  # Add more padding to avoid label collision
    plt.savefig('comparison_federation_steps.pdf')
    plt.show()

# Example usage
mec_systems = 30
merged_dir = f'../1-offer/{mec_systems}-mec-systems/merged-with-registration'
times_df = plot_mean_start_end_times(merged_dir)
print(times_df)  # Debugging: Print the times_df to ensure the steps are being captured

participants_to_compare = ["2", "6", "10", "20", "30"]
steps_colors = {
    'Registration': '#1f77b4',
    'Request Federation': '#ff7f0e',
    'Bid Offered': '#2ca02c',
    'Provider Chosen': '#d62728',
    'Service Deployed\nand Running': '#9467bd',
    'Total Federation\nTime': '#8c564b'
}
plot_federation_steps_comparison(participants_to_compare, steps_colors, additional_mean_times, additional_std_times)