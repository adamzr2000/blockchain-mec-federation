import pandas as pd
import os
import re

def merge_and_save_files(base_dir, system_dir):
    consumer_dir = os.path.join(system_dir, 'consumer')
    output_dir = os.path.join(system_dir, 'merged')

    print(f"Consumer dir: {consumer_dir}")
    print(f"Output dir: {output_dir}")

    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    order = [
        'service_announced',
        'announce_received',  
        'bid_offer_sent',     
        'bid_offer_received',
        'winner_choosen',
        'winner_received',    
        'deployment_start',
        'deployment_finished',
        'confirm_deployment_sent',
        'confirm_deployment_received',
        'establish_vxlan_connection_with_provider_start',
        'establish_vxlan_connection_with_provider_finished'
    ]

    # Pattern to match the files and extract the test number
    pattern = r"federation_events_(consumer|provider(_\d+)?)_test_(\d+)\.csv"

    # Discover all consumer test files
    consumer_files = [f for f in os.listdir(consumer_dir) if re.search(pattern, f)]
    test_numbers = list(set([re.search(pattern, f).group(3) for f in consumer_files]))

    # Process each test file
    for test_num in test_numbers:
        consumer_file = os.path.join(consumer_dir, f'federation_events_consumer_test_{test_num}.csv')
        provider_dirs = [d for d in os.listdir(system_dir) if d.startswith('provider')]

        print(f"Processing: {consumer_file}")
        for provider_dir in provider_dirs:
            print(f"Looking for provider files in: {provider_dir}")

        # Check if consumer file exists
        if os.path.exists(consumer_file):
            # Read the consumer file
            consumer_df = pd.read_csv(consumer_file)

            provider_dfs = []
            for provider_dir in provider_dirs:
                provider_file = os.path.join(system_dir, provider_dir, f'federation_events_provider_test_{test_num}.csv')
                if os.path.exists(provider_file):
                    print(f"Found provider file: {provider_file}")
                    provider_dfs.append(pd.read_csv(provider_file))
                else:
                    print(f"Provider file not found: {provider_file}")

            if provider_dfs:
                # Aggregate provider data according to the specified rules
                provider_df = pd.concat(provider_dfs)
                announce_received_max = provider_df[provider_df['step'] == 'announce_received']['timestamp'].max()
                bid_offer_sent_min = provider_df[provider_df['step'] == 'bid_offer_sent']['timestamp'].min()
                winner_received_max = provider_df[provider_df['step'] == 'winner_received']['timestamp'].max()

                # announce_received_max = provider_df[provider_df['step'] == 'announce_received']['timestamp'].mean()
                # bid_offer_sent_min = provider_df[provider_df['step'] == 'bid_offer_sent']['timestamp'].mean()
                # winner_received_max = provider_df[provider_df['step'] == 'winner_received']['timestamp'].mean()

                # Filter provider-1 for the rest of the steps
                provider1_dir = os.path.join(system_dir, 'provider-1')
                provider1_file = os.path.join(provider1_dir, f'federation_events_provider_test_{test_num}.csv')
                provider1_df = pd.read_csv(provider1_file)

                # Update timestamps in provider1_df
                provider1_df.loc[provider1_df['step'] == 'announce_received', 'timestamp'] = announce_received_max
                provider1_df.loc[provider1_df['step'] == 'bid_offer_sent', 'timestamp'] = bid_offer_sent_min
                provider1_df.loc[provider1_df['step'] == 'winner_received', 'timestamp'] = winner_received_max

                # Merge the consumer and filtered provider1 dataframes
                merged_df = pd.concat([consumer_df, provider1_df])
                merged_df = merged_df.set_index('step').reindex(order).reset_index()

                # Save the merged dataframe
                output_file = os.path.join(output_dir, f'federation_events_merged_test_{test_num}.csv')
                merged_df.to_csv(output_file, index=False)

                print(f"Merged file saved to {output_file}")
            else:
                print(f"No provider files found for test {test_num}.")
        else:
            print(f"Consumer file for test {test_num} does not exist.")

def main():
    base_dir = './1-offer'
    system_dirs = [d for d in os.listdir(base_dir) if re.match(r'\d+-mec-systems', d)]

    print("Available system directories:")
    for i, d in enumerate(system_dirs, 1):
        print(f"{i}. {d}")

    choice = int(input("Enter the number corresponding to the directory you want to process: ")) - 1
    system_dir = os.path.join(base_dir, system_dirs[choice])

    merge_and_save_files(base_dir, system_dir)

if __name__ == "__main__":
    main()
