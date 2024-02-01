# relayPod-ICSM

## Overview
This repository provides a Kubernetes Pod designed for use within an Information-Centric Service Mesh (ICSM) using NDN.

RelayPod simply passes through the received content and returns the content without any modification.

## Deployment
1. Clone the repositories:
```sh
git clone https://github.com/hydrokhoos/relayPod-ICSM.git
```

2. Deploy NDN network: \
For NDN network deployment, refer to the instructions at https://github.com/hydrokhoos/nlsr-sample-k8s.

3. Deploy the pod:
```sh
cd relayPod-ICSM
kubectl apply -f relayPod.yaml
```

## Usage
1. Provide content:
```sh
kubeclt exec deployment/ndn-node1 -- /bin/bash -c "echo 'Hello, world' > /sample.txt"
kubeclt exec deployment/ndn-node1 -- /bin/bash -c "nlsrc advertise /sample.txt"
kubeclt exec deployment/ndn-node1 -- /bin/bash -c "ndnputchunks /sample.txt < /sample.txt"
```

2. Request relaid content from another node:
```sh
kubectl deployment/ndn-node3 -- /bin/bash -c "ndncatchunks /relay/sample.txt"
```
```plain text
All segments have been received.
Time elapsed: 0.0024145 seconds
Segments received: 1
Transferred size: 0.013 kB
Goodput: 43.073100 kbit/s
Congestion marks: 0 (caused 0 window decreases)
Timeouts: 0 (caused 0 window decreases)
Retransmitted segments: 0 (0%), skipped: 0
RTT min/avg/max = 2.388/2.388/2.388 ms
Hello, world
```

## Undeploy
To remove the deployment, execute the following command:
```sh
kubectl delete -f relayPod.yaml
```
