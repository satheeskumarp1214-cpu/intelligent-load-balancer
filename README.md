# SDN-Based Intelligent Load Balancer

An SDN-based intelligent load balancer using Mininet, Open vSwitch, and the Ryu SDN controller.

## Overview

The system dynamically selects backend servers using real-time server metrics instead of relying only on a fixed Round Robin policy.

The intelligent selector considers:

- CPU utilization
- Active connections
- Response time
- Network load

A weighted score is calculated for each backend server, and the controller selects the backend with the lowest score.

## Architecture

Client
  |
  v
Virtual IP: 10.0.0.100:8000
  |
  v
Open vSwitch
  |
  v
Ryu SDN Controller
  |
  v
Intelligent Backend Selection
  |
  +-- h5  10.0.0.5:8001
  +-- h6  10.0.0.6:8002
  +-- h7  10.0.0.7:8003
  +-- h8  10.0.0.8:8004
  +-- h9  10.0.0.9:8005
  +-- h10 10.0.0.10:8006

## Technologies

- Python
- Ryu SDN Controller
- Mininet
- Open vSwitch
- OpenFlow 1.3
- Ubuntu Linux
- HTML / JavaScript

## Project Structure

intelligent-load-balancer/
├── controller/
├── dashboard/
├── experiments/
├── monitoring/
├── results/
├── topology/
├── .gitignore
└── README.md

## Experiments

The project includes:

- Round Robin testing
- Intelligent load balancing testing
- Reliable intelligent request testing
- Multi-client testing
- VIP connectivity testing

## Experimental Result

The reliable intelligent load balancing experiment processed:

- Total requests: 60
- Successful requests: 60
- Failed requests: 0

The experiment results are stored in the results/ directory.

## Dashboard

The project includes a dashboard for monitoring:

- CPU utilization
- Response time
- Active connections
- Network activity
- Intelligent backend selection
- Controller events

A separate dashboard demo is also included.

## Goal

The goal is to demonstrate dynamic, resource-aware load balancing using Software Defined Networking.
