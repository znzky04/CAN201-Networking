from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types, ipv4, tcp
import time

class TCPRedirect(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TCPRedirect, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.tcp_handshake_times = {}
        # Add logging output
        self.logger.info("Initializing TCPRedirect application...")
        
        # Server1 and Server2 configuration
        self.server1_mac = "00:00:00:00:00:01"
        self.server2_mac = "00:00:00:00:00:02"
        self.server1_ip = "10.0.1.2"
        self.server2_ip = "10.0.1.3"
        
        # Print configuration information
        self.logger.info(f"Server1 config - MAC: {self.server1_mac}, IP: {self.server1_ip}")
        self.logger.info(f"Server2 config - MAC: {self.server2_mac}, IP: {self.server2_ip}")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Install table-miss flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                        ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions, timeout=0)

    def add_flow(self, datapath, priority, match, actions, timeout=30):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                           actions)]
        
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                               match=match, instructions=inst,
                               idle_timeout=timeout)
        self.logger.info(f"Adding flow - Priority: {priority}, Match: {match}, Actions: {actions}")
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        self.logger.debug(f"Packet in - src: {src}, dst: {dst}, in_port: {in_port}")

        # Learn the port for source MAC address
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        # Get IP and TCP headers
        ip_header = pkt.get_protocol(ipv4.ipv4)
        tcp_header = pkt.get_protocol(tcp.tcp)

        # Handle TCP SYN packet for redirection
        if (ip_header and tcp_header and 
            tcp_header.has_flags(tcp.TCP_SYN) and 
            not tcp_header.has_flags(tcp.TCP_ACK) and 
            ip_header.dst == self.server1_ip):
            
            self.logger.info(f"Detected SYN packet to Server1, redirecting to Server2")
            
            # Ensure we know Server2's output port
            if self.server2_mac not in self.mac_to_port[dpid]:
                self.logger.error(f"Server2 MAC {self.server2_mac} port unknown!")
                return
            
            out_port = self.mac_to_port[dpid][self.server2_mac]
            
            # Create redirection actions
            actions = [
                parser.OFPActionSetField(eth_dst=self.server2_mac),
                parser.OFPActionSetField(ipv4_dst=self.server2_ip),
                parser.OFPActionOutput(out_port)
            ]

            # Create bidirectional flow entries for redirected traffic
            # Client -> Server direction
            match_forward = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_src=ip_header.src,
                ipv4_dst=self.server1_ip,
                ip_proto=ip_header.proto,
                tcp_src=tcp_header.src_port,
                tcp_dst=tcp_header.dst_port
            )
            self.add_flow(datapath, 2, match_forward, actions)

            # Server -> Client direction
            match_reverse = parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_src=self.server2_ip,
                ipv4_dst=ip_header.src,
                ip_proto=ip_header.proto,
                tcp_src=tcp_header.dst_port,
                tcp_dst=tcp_header.src_port
            )
            actions_reverse = [
                parser.OFPActionSetField(eth_src=self.server1_mac),
                parser.OFPActionSetField(ipv4_src=self.server1_ip),
                parser.OFPActionOutput(in_port)
            ]
            self.add_flow(datapath, 2, match_reverse, actions_reverse)

            # Modify original packet and forward
            ip_header.dst = self.server2_ip
            eth.dst = self.server2_mac
            
            self.logger.info(f"Redirecting packet to Server2 (IP: {self.server2_ip}, MAC: {self.server2_mac})")
            
            # Repack the packet
            pkt.serialize()
            data = pkt.data
        else:
            # Normal forwarding
            if dst in self.mac_to_port[dpid]:
                out_port = self.mac_to_port[dpid][dst]
            else:
                out_port = ofproto.OFPP_FLOOD
            actions = [parser.OFPActionOutput(out_port)]
            data = msg.data

        # Send Packet_Out message
        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)