// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

// Define the smart contract
contract Federation {

    // Define the possible states of a service
    enum ServiceState {Open, Closed, Deployed}

    struct Operator {
        string name;
        address operatorAddress;
        uint256 registrationTime;
        bool registered;
    }

    struct Service {
        address creator;
        string endpoint_consumer;
        bytes32 serviceId; // Example "service123" -> 0x7365727669636531323300000000000000000000000000000000000000000000
        address provider;
        string endpoint_provider;
        string requirements;
        ServiceState state;
    }

    struct Bid {
        address bidAddress;
        uint priceWeiPerHour; // Cost in wei per hour of service
        string endpoint_provider;
    }
    
    // Mappings
    mapping(bytes32 => uint) public bidCount;
    mapping(bytes32 => Bid[]) public bids;
    mapping(bytes32 => Service) public service;
    mapping(address => Operator) public operator;
    
    // Events
    event OperatorRegistered(address operator, string name);
    event OperatorRemoved(address operator);
    event ServiceAnnouncement(bytes32 serviceId, string requirements);
    event NewBid(bytes32 serviceId, uint256 biderIndex);
    event ServiceAnnouncementClosed(bytes32 serviceId);
    event ServiceDeployed(bytes32 serviceId);

    // Modifiers
    modifier onlyRegistered() {
        require(operator[msg.sender].registered, "Operator: not registered");
        _;
    }

    modifier serviceExists(bytes32 serviceId) {
        require(service[serviceId].serviceId == serviceId, "Service: does not exist");
        _;
    }

    modifier onlyServiceCreator(bytes32 serviceId) {
        require(service[serviceId].creator == msg.sender, "Service: caller is not creator");
        _;
    }

    function addOperator(string memory name) public {
        require(bytes(name).length > 0, "Name is not valid");
        require(!operator[msg.sender].registered, "Operator: already registered");
        
        operator[msg.sender] = Operator({
                name: name,
                operatorAddress: msg.sender,
                registrationTime: block.timestamp,
                registered: true
        });
        emit OperatorRegistered(msg.sender, name);
    }

    function removeOperator() public onlyRegistered {
        delete operator[msg.sender];
        emit OperatorRemoved(msg.sender);
    }

    function getOperatorInfo(address callAddress) public view returns (
        string memory name,
        address opAddress,
        uint256 registrationTime,
        bool registered
    ) {
        Operator storage op = operator[callAddress];
        require(op.registered == true, "Operator: not registered");
        return (op.name, op.operatorAddress, op.registrationTime, op.registered);
    }

    function announceService(
        bytes32 serviceId,
        string memory requirements,
        string memory endpoint_consumer
    ) public onlyRegistered {
        require(service[serviceId].serviceId != serviceId, "Service: ID already exists");

        Service storage newService = service[serviceId];

        newService.serviceId = serviceId;
        newService.requirements = requirements;
        newService.state = ServiceState.Open;
        newService.creator = msg.sender;
        newService.provider = msg.sender;
        newService.endpoint_consumer = endpoint_consumer;
        newService.endpoint_provider = endpoint_consumer;

        emit ServiceAnnouncement(serviceId, requirements);
    }

    function getServiceState(bytes32 serviceId) public view returns (ServiceState) {
        return service[serviceId].state;
    }

    function getServiceInfo(
        bytes32 serviceId, 
        bool isProvider, 
        address callAddress
    ) public view returns (bytes32, string memory, string memory) {
        Service storage currentService = service[serviceId];
        require(operator[callAddress].registered, "Operator: not registered");
        require(currentService.state >= ServiceState.Closed, "Service: not closed");

        if(isProvider) {
            require(currentService.provider == callAddress, "Service: not provider");
            return(currentService.serviceId, currentService.endpoint_consumer, currentService.requirements);
        } else {
            require(currentService.creator == callAddress, "Service: not creator");
            return(currentService.serviceId, currentService.endpoint_provider, currentService.requirements);
        }
    }

    function placeBid(
        bytes32 serviceId, 
        uint32 priceWeiPerHour,
        string memory endpoint_provider
    ) public onlyRegistered serviceExists(serviceId) {
        Service storage currentService = service[serviceId];
        require(currentService.state == ServiceState.Open, "Service: not open");
        require(priceWeiPerHour > 0, "Bid: price must be greater than 0");

        // require(msg.sender != currentService.creator, "Bid: cannot bid on own service");

        bids[serviceId].push(Bid(msg.sender, priceWeiPerHour, endpoint_provider));
        uint256 index = bids[serviceId].length;
        bidCount[serviceId] = index;

        emit NewBid(serviceId, index);
    }

    function getBidCount(bytes32 serviceId, address callAddress) public view serviceExists(serviceId) returns (uint256) {
        require(service[serviceId].creator == callAddress, "Service: caller not creator");
        return bidCount[serviceId];
    }

    function getBidInfo(bytes32 serviceId, uint256 index, address callAddress) public view serviceExists(serviceId) returns (address, uint, uint256) {
        require(service[serviceId].creator == callAddress, "Service: caller not creator");
        Bid[] storage bidPool = bids[serviceId];
        require(bidPool.length > 0, "Bid: no bids");
        require(index < bidPool.length, "Bid: index out of range");

        Bid storage b = bidPool[index];
        return (b.bidAddress, b.priceWeiPerHour, index);
    }

    function chooseProvider(bytes32 serviceId, uint256 biderIndex) public serviceExists(serviceId) onlyServiceCreator(serviceId) {
        Service storage currentService = service[serviceId];
        require(currentService.state == ServiceState.Open, "Service: not open");
        require(biderIndex < bids[serviceId].length, "Bid: index out of range");
    
        currentService.state = ServiceState.Closed;
        currentService.provider = bids[serviceId][biderIndex].bidAddress;
        currentService.endpoint_provider = bids[serviceId][biderIndex].endpoint_provider;
        emit ServiceAnnouncementClosed(serviceId);
    }

    function isWinner(bytes32 serviceId, address callAddress) public view serviceExists(serviceId) returns (bool) {
        Service storage currentService = service[serviceId];
        require(currentService.state == ServiceState.Closed, "Service: not closed");
        
        return currentService.provider == callAddress;
    }

    function serviceDeployed(bytes32 serviceId, string memory info) public serviceExists(serviceId) {
        Service storage currentService = service[serviceId];
        require(currentService.provider == msg.sender, "Service: not provider");
        require(currentService.state == ServiceState.Closed, "Service: not closed");
        
        currentService.state = ServiceState.Deployed;
        currentService.requirements = info;

        emit ServiceDeployed(serviceId);
    }
}
