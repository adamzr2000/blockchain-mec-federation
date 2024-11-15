import logging
import subprocess
# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def configure_docker_network_and_vxlan(local_ip, remote_ip, interface_name, vxlan_id, dst_port, subnet, ip_range, sudo_password='netcom;', docker_net_name = 'federation-net'):
    script_path = './utils/docker_host_setup_vxlan.sh'
    
    # Construct the command with arguments
    command = [
        'sudo', '-S', 'bash', script_path,
        '-l', local_ip,
        '-r', remote_ip,
        '-i', interface_name,
        '-v', vxlan_id,
        '-p', dst_port,
        '-s', subnet,
        '-d', ip_range,
        '-n', docker_net_name
    ]
    
    try:
        # Run the command with sudo and password
        result = subprocess.run(command, input=sudo_password.encode() + b'\n', check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Print the output of the script
        print(result.stdout.decode())
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occurred while running the script: {e.stderr.decode()}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")


configure_docker_network_and_vxlan("10.5.99.1", "10.5.99.2", "ens3", "200", "4789", "10.0.0.0/16", "10.0.1.0/24",'netcom;', "federation-net")
