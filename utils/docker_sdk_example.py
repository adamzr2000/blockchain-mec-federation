import docker

# Validate connectivity to Docker and get the version information
try:
    client = docker.from_env()
    version_info = client.version()
    print(f"Successfully connected to Docker daemon (version={version_info['Version']})")
except Exception as e:
    print(f"Failed to connect to Docker daemon: {e}")

def deploy_docker_containers(image, name, network, replicas):
    containers = []
    try:
        for i in range(replicas):
            container_name = f"{name}_{i+1}"
            container = client.containers.run(
                image=image,
                name=container_name,
                network=network,
                detach=True,
                command="sh -c 'while true; do sleep 3600; done'"
            )
            containers.append(container)
            print(f"Container {container_name} deployed successfully.")
        
        # Wait for containers to be ready
        for container in containers:
            container_ready = False
            for _ in range(60):  # Wait up to 60 seconds
                container.reload()
                if container.status == "running":
                    container_ready = True
                    break
                time.sleep(1)
            if container_ready:
                print(f"Container {container.name} is ready.")
            else:
                print(f"Container {container.name} failed to start within the expected time.")
        
        return containers
    except Exception as e:
        print(f"Failed to deploy containers: {e}")
        return []

def delete_docker_containers(name):
    try:
        containers = client.containers.list(all=True, filters={"name": name})
        for container in containers:
            container_name = container.name
            container.remove(force=True)
            print(f"Container {container_name} deletion initiated.")
            
            # Wait for container to be removed
            while True:
                remaining_containers = client.containers.list(all=True, filters={"name": container_name})
                if not remaining_containers:
                    print(f"Container {container_name} is confirmed deleted.")
                    break
                
    except Exception as e:
        print(f"Failed to delete containers: {e}")


def scale_docker_containers(name, action, replicas):
    try:
        existing_containers = client.containers.list(all=True, filters={"name": name})
        current_replicas = len(existing_containers)
        
        if action.lower() == "up":
            new_replicas = current_replicas + replicas
            for i in range(current_replicas, new_replicas):
                container_name = f"{name}_{i+1}"
                container = client.containers.run(
                    image=existing_containers[0].image.tags[0],
                    name=container_name,
                    network=existing_containers[0].attrs['HostConfig']['NetworkMode'],
                    detach=True,
                    command="sh -c 'while true; do sleep 3600; done'"
                )
                print(f"Container {container_name} deployed successfully.")
        elif action.lower() == "down":
            new_replicas = max(0, current_replicas - replicas)
            for i in range(current_replicas - 1, new_replicas - 1, -1):
                container_name = f"{name}_{i+1}"
                container = client.containers.get(container_name)
                container.remove(force=True)
                print(f"Container {container_name} deleted successfully.")
        else:
            print("Invalid action. Use 'up' or 'down'.")
            return
    except Exception as e:
        print(f"Failed to scale containers: {e}")

def get_container_replicas(name):
    try:
        containers = client.containers.list(all=True, filters={"name": name})
        replicas = len(containers)
        print(f"Service {name} has {replicas} replicas.")
        return replicas
    except Exception as e:
        print(f"Failed to get replicas for service {name}: {e}")

def exec_command_in_container(name, command):
    try:
        containers = client.containers.list(all=True, filters={"name": name})
        if not containers:
            print(f"No containers found with name: {name}")
            return
        
        for container in containers:
            exec_result = container.exec_run(command)
            print(f"Executed command in {container.name}:\n{exec_result.output.decode()}")
    except Exception as e:
        print(f"Failed to execute command in containers: {e}")

def get_container_ips(name):
    container_ips = {}
    try:
        containers = client.containers.list(all=True, filters={"name": name})
        if not containers:
            print(f"No containers found with name: {name}")
            return container_ips
        
        for container in containers:
            container.reload()  # Refresh container data
            network_settings = container.attrs['NetworkSettings']['Networks']
            for network_name, network_data in network_settings.items():
                ip_address = network_data['IPAddress']
                container_ips[container.name] = ip_address
                print(f"Container {container.name} in network {network_name} has IP address: {ip_address}")
        return container_ips
    except Exception as e:
        print(f"Failed to get IP addresses for containers: {e}")
        return container_ips

def interactive_menu():
    while True:
        print("\nDocker Container Manager")
        print("1. Deploy Docker Containers")
        print("2. Delete Docker Containers")
        print("3. Scale Docker Containers")
        print("4. Get Container Replicas")
        print("5. Execute Command in Container")
        print("6. Get Container IP Addresses")
        print("7. Exit")

        choice = input("Enter your choice: ")

        if choice == '1':
            image = input("Enter the Docker image: ")
            name = input("Enter the service name: ")
            network = input("Enter the network name: ")
            replicas = int(input("Enter the number of replicas: "))
            deploy_docker_containers(image, name, network, replicas)
        elif choice == '2':
            name = input("Enter the service name to delete: ")
            delete_docker_containers(name)
        elif choice == '3':
            name = input("Enter the service name to scale: ")
            action = input("Enter 'up' to scale up or 'down' to scale down: ")
            replicas = int(input("Enter the number of replicas to add or remove: "))
            scale_docker_containers(name, action, replicas)
        elif choice == '4':
            name = input("Enter the service name to get replicas: ")
            get_container_replicas(name)
        elif choice == '5':
            name = input("Enter the service name to execute command: ")
            command = input("Enter the command to execute: ")
            exec_command_in_container(name, command)
        elif choice == '6':
            name = input("Enter the service name to get container IP addresses: ")
            container_ips = get_container_ips(name)
            if container_ips:
                first_container_name = next(iter(container_ips))
                first_ip_address = container_ips[first_container_name]
                print(f"The IP address of the first container ({first_container_name}) is: {first_ip_address}")
        elif choice == '7':
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    interactive_menu()