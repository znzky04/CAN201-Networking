#!/usr/bin/python

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSController
from mininet.node import OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
from mininet.term import makeTerm

def createNetwork():
    # Create network
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch, link=TCLink)
    
    # Add controller
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6633)
    
    # Add switch
    s1 = net.addSwitch('s1')
    
    # Add hosts
    client = net.addHost('client', ip='10.0.1.5/24', mac='00:00:00:00:00:03')
    server1 = net.addHost('server1', ip='10.0.1.2/24', mac='00:00:00:00:00:01')
    server2 = net.addHost('server2', ip='10.0.1.3/24', mac='00:00:00:00:00:02')
    
    # Add links
    net.addLink(client, s1)
    net.addLink(server1, s1)
    net.addLink(server2, s1)
    
    # Start network
    net.build()
    c0.start()
    s1.start([c0])
    
    # Open xterm windows automatically
    # Open xterm for all hosts
    for host in net.hosts:
        makeTerm(host)
    # Open xterm for switch
    makeTerm(s1)
    # Open xterm for controller
    makeTerm(c0)
    
    # Start Mininet CLI
    CLI(net)
    
    # Stop network
    net.stop()

if __name__ == '__main__':
    setLogLevel('warning')
    createNetwork() 