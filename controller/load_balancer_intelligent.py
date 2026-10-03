from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER,
    MAIN_DISPATCHER,
    set_ev_cls
)
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import (
    packet,
    ethernet,
    ether_types,
    arp,
    ipv4,
    tcp
)


class IntelligentLoadBalancer(app_manager.RyuApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    VIP_IP = "10.0.0.100"
    VIP_MAC = "00:00:00:00:00:64"
    VIP_PORT = 8000

    BACKENDS = [
        ("10.0.0.5", 8001),
        ("10.0.0.6", 8002),
        ("10.0.0.7", 8003),
        ("10.0.0.8", 8004),
        ("10.0.0.9", 8005),
        ("10.0.0.10", 8006),
    ]

    def __init__(self, *args, **kwargs):
        super(IntelligentLoadBalancer, self).__init__(
            *args, **kwargs
        )

        # MAC -> switch port
        self.mac_to_port = {}

        # IP -> MAC
        self.ip_to_mac = {}

        # Round-robin pointer
        self.backend_index = 0

        # -------------------------------------------------
        # TCP connection mappings
        # -------------------------------------------------

        # Client connection:
        # (client_ip, client_port)
        # ->
        # (backend_ip, backend_port)
        self.client_connections = {}

        # Reverse connection:
        # (backend_ip, backend_port, client_ip, client_port)
        # ->
        # True
        self.reverse_connections = {}

    # =====================================================
    # SWITCH FEATURES
    # =====================================================

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Table miss -> controller
        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        self.add_flow(
            datapath,
            0,
            match,
            actions,
            idle_timeout=0
        )

        self.logger.info(
            "Switch connected: datapath=%s",
            datapath.id
        )

    # =====================================================
    # FLOW INSTALLATION
    # =====================================================

    def add_flow(
        self,
        datapath,
        priority,
        match,
        actions,
        idle_timeout=30
    ):

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            cookie=0,
            cookie_mask=0,
            table_id=0,
            command=ofproto.OFPFC_ADD,
            idle_timeout=idle_timeout,
            hard_timeout=0,
            priority=priority,
            buffer_id=ofproto.OFP_NO_BUFFER,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            flags=0,
            match=match,
            instructions=instructions
        )

        datapath.send_msg(mod)

    # =====================================================
    # INSTALL TCP CONNECTION FLOWS
    # =====================================================

    def install_tcp_connection_flows(
        self,
        datapath,
        client_ip,
        client_port,
        client_mac,
        client_switch_port,
        backend_ip,
        backend_port,
        backend_mac,
        backend_switch_port
    ):

        parser = datapath.ofproto_parser

        # Client -> VIP -> Backend
        forward_match = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ip_proto=6,
            ipv4_src=client_ip,
            ipv4_dst=self.VIP_IP,
            tcp_src=client_port,
            tcp_dst=self.VIP_PORT
        )

        forward_actions = [
            parser.OFPActionSetField(
                ipv4_dst=backend_ip
            ),
            parser.OFPActionSetField(
                eth_dst=backend_mac
            ),
            parser.OFPActionSetField(
                tcp_dst=backend_port
            ),
            parser.OFPActionOutput(
                backend_switch_port
            )
        ]

        self.add_flow(
            datapath,
            100,
            forward_match,
            forward_actions,
            idle_timeout=30
        )

        # Backend -> Client -> VIP
        reverse_match = parser.OFPMatch(
            eth_type=ether_types.ETH_TYPE_IP,
            ip_proto=6,
            ipv4_src=backend_ip,
            ipv4_dst=client_ip,
            tcp_src=backend_port,
            tcp_dst=client_port
        )

        reverse_actions = [
            parser.OFPActionSetField(
                ipv4_src=self.VIP_IP
            ),
            parser.OFPActionSetField(
                eth_src=self.VIP_MAC
            ),
            parser.OFPActionSetField(
                tcp_src=self.VIP_PORT
            ),
            parser.OFPActionOutput(
                client_switch_port
            )
        ]

        self.add_flow(
            datapath,
            100,
            reverse_match,
            reverse_actions,
            idle_timeout=30
        )

        self.logger.info(
            "TCP FLOWS INSTALLED: %s:%s <-> %s:%s",
            client_ip,
            client_port,
            backend_ip,
            backend_port
        )

    # =====================================================
    # BACKEND SELECTION
    # =====================================================

    def select_backend(self):

        import csv
        import os

        csv_file = os.path.expanduser(
            "~/intelligent-load-balancer/results/server_metrics.csv"
        )

        metrics = {}

        try:
            with open(csv_file, "r") as file:
                rows = list(csv.DictReader(file))

            # Keep only the latest measurement for each backend
            for row in rows:
                server = row.get("server", "").strip()
                if server:
                    metrics[server] = row

        except Exception as e:
            self.logger.warning(
                "Could not read server metrics: %s",
                e
            )

        # Intelligent weighted selection
        CPU_WEIGHT = 0.40
        CONNECTION_WEIGHT = 0.20
        RESPONSE_WEIGHT = 0.25
        NETWORK_WEIGHT = 0.15

        values = []

        for backend_ip, backend_port in self.BACKENDS:
            server = "h" + backend_ip.split(".")[-1]
            row = metrics.get(server)

            if row:
                try:
                    cpu = float(row.get("cpu_percent", 0))
                    conn = float(row.get("active_connections", 0))
                    response = float(row.get("response_time_ms", 0))
                    network = float(row.get("network_bytes", 0))

                    values.append(
                        (backend_ip, backend_port,
                         cpu, conn, response, network)
                    )
                except (ValueError, TypeError):
                    pass

        if not values:
            backend = self.BACKENDS[
                self.backend_index
            ]

            self.backend_index = (
                self.backend_index + 1
            ) % len(self.BACKENDS)

            self.logger.warning(
                "No valid metrics available - FALLING BACK TO ROUND ROBIN: %s:%s",
                backend[0],
                backend[1]
            )

            return backend

        cpu_values = [v[2] for v in values]
        conn_values = [v[3] for v in values]
        response_values = [v[4] for v in values]
        network_values = [v[5] for v in values]

        def normalize(value, all_values):
            minimum = min(all_values)
            maximum = max(all_values)

            if maximum == minimum:
                return 0.0

            return (value - minimum) / (maximum - minimum)

        scored = []

        for backend_ip, backend_port, cpu, conn, response, network in values:

            score = (
                CPU_WEIGHT * normalize(cpu, cpu_values)
                + CONNECTION_WEIGHT * normalize(conn, conn_values)
                + RESPONSE_WEIGHT * normalize(response, response_values)
                + NETWORK_WEIGHT * normalize(network, network_values)
            )

            scored.append(
                (score, backend_ip, backend_port)
            )

        scored.sort(key=lambda x: x[0])

        score, backend_ip, backend_port = scored[0]

        self.logger.info(
            "INTELLIGENT BACKEND SELECTED: %s:%s | SCORE=%.4f",
            backend_ip,
            backend_port,
            score
        )

        return (backend_ip, backend_port)

    # =====================================================
    # PACKET OUT
    # =====================================================

    def send_packet_out(
        self,
        datapath,
        msg,
        actions
    ):

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        data = None

        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=msg.match[
                "in_port"
            ],
            actions=actions,
            data=data
        )

        datapath.send_msg(out)

    # =====================================================
    # ARP HANDLING
    # =====================================================

    def handle_arp(
        self,
        datapath,
        msg,
        pkt,
        eth
    ):

        arp_pkt = pkt.get_protocol(
            arp.arp
        )

        if arp_pkt is None:
            return False

        src_ip = arp_pkt.src_ip
        dst_ip = arp_pkt.dst_ip

        self.mac_to_port[
            datapath.id
        ][
            eth.src
        ] = msg.match["in_port"]

        self.ip_to_mac[src_ip] = eth.src

        self.logger.info(
            "ARP: %s(%s) -> %s",
            src_ip,
            eth.src,
            dst_ip
        )

        # -------------------------------------------------
        # VIP ARP REQUEST
        # -------------------------------------------------

        if (
            arp_pkt.opcode == arp.ARP_REQUEST
            and dst_ip == self.VIP_IP
        ):

            self.logger.info(
                "VIP ARP REQUEST from %s",
                src_ip
            )

            arp_reply = packet.Packet()

            arp_reply.add_protocol(
                ethernet.ethernet(
                    ethertype=ether_types.ETH_TYPE_ARP,
                    dst=eth.src,
                    src=self.VIP_MAC
                )
            )

            arp_reply.add_protocol(
                arp.arp(
                    opcode=arp.ARP_REPLY,
                    src_mac=self.VIP_MAC,
                    src_ip=self.VIP_IP,
                    dst_mac=eth.src,
                    dst_ip=src_ip
                )
            )

            arp_reply.serialize()

            actions = [
                datapath.ofproto_parser.OFPActionOutput(
                    msg.match["in_port"]
                )
            ]

            out = datapath.ofproto_parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                in_port=datapath.ofproto.OFPP_CONTROLLER,
                actions=actions,
                data=arp_reply.data
            )

            datapath.send_msg(out)

            self.logger.info(
                "VIP ARP REPLY sent to %s",
                src_ip
            )

            return True

        # -------------------------------------------------
        # Normal ARP forwarding
        # -------------------------------------------------

        dst_port = self.mac_to_port[
            datapath.id
        ].get(
            eth.dst
        )

        if dst_port is not None:

            actions = [
                datapath.ofproto_parser.OFPActionOutput(
                    dst_port
                )
            ]

            self.send_packet_out(
                datapath,
                msg,
                actions
            )

        else:

            actions = [
                datapath.ofproto_parser.OFPActionOutput(
                    datapath.ofproto.OFPP_FLOOD
                )
            ]

            self.send_packet_out(
                datapath,
                msg,
                actions
            )

        return True

    # =====================================================
    # TCP CLIENT -> VIP
    # =====================================================

    def handle_client_to_vip(
        self,
        datapath,
        msg,
        eth,
        ipv4_pkt,
        tcp_pkt
    ):

        client_ip = ipv4_pkt.src
        client_port = tcp_pkt.src_port

        connection_key = (
            client_ip,
            client_port
        )

        # -------------------------------------------------
        # NEW TCP CONNECTION
        # -------------------------------------------------

        syn = (
            tcp_pkt.bits & tcp.TCP_SYN
        ) != 0

        ack = (
            tcp_pkt.bits & tcp.TCP_ACK
        ) != 0

        if (
            syn
            and not ack
            and connection_key
            not in self.client_connections
        ):

            backend_ip, backend_port = (
                self.select_backend()
            )

            self.client_connections[
                connection_key
            ] = (
                backend_ip,
                backend_port
            )

            self.reverse_connections[
                (
                    backend_ip,
                    backend_port,
                    client_ip,
                    client_port
                )
            ] = True

            self.logger.info(
                "NEW TCP CONNECTION: "
                "%s:%s -> VIP -> %s:%s",
                client_ip,
                client_port,
                backend_ip,
                backend_port
            )

        # -------------------------------------------------
        # EXISTING CONNECTION
        # -------------------------------------------------

        backend = self.client_connections.get(
            connection_key
        )

        if backend is None:

            self.logger.warning(
                "No backend mapping for "
                "%s:%s",
                client_ip,
                client_port
            )

            return False

        backend_ip, backend_port = backend

        backend_mac = self.ip_to_mac.get(
            backend_ip
        )

        if backend_mac is None:

            self.logger.warning(
                "Backend MAC unknown for %s - sending ARP request",
                backend_ip
            )

            # -------------------------------------------------
            # ACTIVE ARP RESOLUTION FOR SELECTED BACKEND
            # -------------------------------------------------

            arp_request = packet.Packet()

            arp_request.add_protocol(
                ethernet.ethernet(
                    ethertype=ether_types.ETH_TYPE_ARP,
                    dst="ff:ff:ff:ff:ff:ff",
                    src=self.VIP_MAC
                )
            )

            arp_request.add_protocol(
                arp.arp(
                    opcode=arp.ARP_REQUEST,
                    src_mac=self.VIP_MAC,
                    src_ip=self.VIP_IP,
                    dst_mac="00:00:00:00:00:00",
                    dst_ip=backend_ip
                )
            )

            arp_request.serialize()

            arp_actions = [
                datapath.ofproto_parser.OFPActionOutput(
                    datapath.ofproto.OFPP_FLOOD
                )
            ]

            arp_out = datapath.ofproto_parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                in_port=datapath.ofproto.OFPP_CONTROLLER,
                actions=arp_actions,
                data=arp_request.data
            )

            datapath.send_msg(arp_out)

            self.logger.info(
                "BACKEND ARP REQUEST sent for %s",
                backend_ip
            )

            return True

        backend_port_number = (
            self.mac_to_port[
                datapath.id
            ].get(
                backend_mac
            )
        )

        if backend_port_number is None:

            self.logger.warning(
                "Backend switch port unknown "
                "for %s",
                backend_ip
            )

            return False

        # -------------------------------------------------
        # INSTALL CONNECTION FLOWS
        # -------------------------------------------------

        self.install_tcp_connection_flows(
            datapath,
            client_ip,
            client_port,
            eth.src,
            msg.match["in_port"],
            backend_ip,
            backend_port,
            backend_mac,
            backend_port_number
        )

        # -------------------------------------------------
        # REWRITE CLIENT -> BACKEND
        # -------------------------------------------------

        parser = datapath.ofproto_parser

        actions = [

            parser.OFPActionSetField(
                ipv4_dst=backend_ip
            ),

            parser.OFPActionSetField(
                eth_dst=backend_mac
            ),

            parser.OFPActionSetField(
                tcp_dst=backend_port
            ),

            parser.OFPActionOutput(
                backend_port_number
            )
        ]

        self.logger.info(
            "TCP VIP TRAFFIC: "
            "%s:%s -> %s:%s -> %s:%s",
            client_ip,
            client_port,
            self.VIP_IP,
            self.VIP_PORT,
            backend_ip,
            backend_port
        )

        self.send_packet_out(
            datapath,
            msg,
            actions
        )

        return True

    # =====================================================
    # TCP BACKEND -> CLIENT
    # =====================================================

    def handle_backend_to_client(
        self,
        datapath,
        msg,
        eth,
        ipv4_pkt,
        tcp_pkt
    ):

        backend_ip = ipv4_pkt.src
        backend_port = tcp_pkt.src_port

        client_ip = ipv4_pkt.dst
        client_port = tcp_pkt.dst_port

        connection_key = (
            backend_ip,
            backend_port,
            client_ip,
            client_port
        )

        if (
            connection_key
            not in self.reverse_connections
        ):

            self.logger.warning(
                "Unknown backend return flow: "
                "%s:%s -> %s:%s",
                backend_ip,
                backend_port,
                client_ip,
                client_port
            )

            return False

        client_mac = self.ip_to_mac.get(
            client_ip
        )

        if client_mac is None:

            self.logger.warning(
                "Client MAC unknown for %s",
                client_ip
            )

            return False

        client_port_number = (
            self.mac_to_port[
                datapath.id
            ].get(
                client_mac
            )
        )

        if client_port_number is None:

            self.logger.warning(
                "Client port unknown for %s",
                client_ip
            )

            return False

        parser = datapath.ofproto_parser

        actions = [

            parser.OFPActionSetField(
                ipv4_src=self.VIP_IP
            ),

            parser.OFPActionSetField(
                eth_src=self.VIP_MAC
            ),

            parser.OFPActionSetField(
                tcp_src=self.VIP_PORT
            ),

            parser.OFPActionOutput(
                client_port_number
            )
        ]

        self.logger.info(
            "TCP RETURN TRAFFIC: "
            "%s:%s -> %s:%s",
            backend_ip,
            backend_port,
            client_ip,
            client_port
        )

        self.send_packet_out(
            datapath,
            msg,
            actions
        )

        return True

    # =====================================================
    # NORMAL IP FORWARDING
    # =====================================================

    def handle_normal_ip(
        self,
        datapath,
        msg,
        eth
    ):

        parser = datapath.ofproto_parser

        dst_port = self.mac_to_port[
            datapath.id
        ].get(
            eth.dst
        )

        if dst_port is not None:

            actions = [
                parser.OFPActionOutput(
                    dst_port
                )
            ]

        else:

            actions = [
                parser.OFPActionOutput(
                    datapath.ofproto.OFPP_FLOOD
                )
            ]

        self.send_packet_out(
            datapath,
            msg,
            actions
        )

    # =====================================================
    # PACKET IN
    # =====================================================

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER
    )
    def packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath
        in_port = msg.match[
            "in_port"
        ]

        parser = datapath.ofproto_parser

        pkt = packet.Packet(
            msg.data
        )

        eth = pkt.get_protocol(
            ethernet.ethernet
        )

        if eth is None:
            return

        # -------------------------------------------------
        # Initialize MAC table
        # -------------------------------------------------

        if datapath.id not in self.mac_to_port:
            self.mac_to_port[
                datapath.id
            ] = {}

        self.mac_to_port[
            datapath.id
        ][eth.src] = in_port

        # -------------------------------------------------
        # Ignore LLDP
        # -------------------------------------------------

        if eth.ethertype == 0x88cc:
            return

        # -------------------------------------------------
        # ARP
        # -------------------------------------------------

        if eth.ethertype == 0x0806:

            self.handle_arp(
                datapath,
                msg,
                pkt,
                eth
            )

            return

        # -------------------------------------------------
        # IPv4
        # -------------------------------------------------

        if eth.ethertype != 0x0800:
            return

        ipv4_pkt = pkt.get_protocol(
            ipv4.ipv4
        )

        if ipv4_pkt is None:
            return

        src_ip = ipv4_pkt.src
        dst_ip = ipv4_pkt.dst

        self.ip_to_mac[
            src_ip
        ] = eth.src

        # -------------------------------------------------
        # TCP
        # -------------------------------------------------

        tcp_pkt = pkt.get_protocol(
            tcp.tcp
        )

        if tcp_pkt is not None:

            # Client -> VIP
            if (
                dst_ip == self.VIP_IP
                and tcp_pkt.dst_port
                == self.VIP_PORT
            ):

                self.handle_client_to_vip(
                    datapath,
                    msg,
                    eth,
                    ipv4_pkt,
                    tcp_pkt
                )

                return

            # Backend -> Client
            if (
                src_ip
                in [
                    backend[0]
                    for backend in self.BACKENDS
                ]
            ):

                self.handle_backend_to_client(
                    datapath,
                    msg,
                    eth,
                    ipv4_pkt,
                    tcp_pkt
                )

                return

        # -------------------------------------------------
        # Normal IPv4 forwarding
        # -------------------------------------------------

        self.handle_normal_ip(
            datapath,
            msg,
            eth
        )
