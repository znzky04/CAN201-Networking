#!/usr/bin/python
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.node import Host, OVSKernelSwitch
from mininet.log import setLogLevel, info

def myTopo():
    net = Mininet(topo=None, autoSetMacs=True, build=False, ipBase='10.21.156.00/24')

    h1 = net.addHost('h1', cls=Host, defaultRoute=None)
    h2 = net.addHost('h2', cls=Host, defaultRoute=None)

    s1 = net.addSwitch('Switch1', cls=OVSKernelSwitch, failMode='standalone')
    s2 = net.addSwitch('Switch2', cls=OVSKernelSwitch, failMode='standalone')
    s3 = net.addSwitch('Switch3', cls=OVSKernelSwitch, failMode='standalone')

    net.addLink(h1, s1)
    net.addLink(h1, s2)
    net.addLink(h1, s3)

    net.addLink(h2, s1)
    net.addLink(h2, s2)
    net.addLink(h2, s3)

    net.build()

    h1.setIP(ip='10.21.156.11/24', intf="h1-eth0")
    h1.setIP(ip='10.21.156.33/24', intf="h1-eth2")
    h1.setIP(ip='10.21.156.22/24', intf="h1-eth1")
    
    h2.setIP(ip='10.21.156.111/24', intf="h2-eth0")
    h2.setIP(ip='10.21.156.113/24', intf="h2-eth2")
    h2.setIP(ip='10.21.156.112/24', intf="h2-eth1")

    net.start()
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    myTopo()

