from mininet.topo import Topo


class IntelligentLoadBalancerTopo(Topo):

    def build(self):

        s1 = self.addSwitch(
            's1',
            protocols='OpenFlow13'
        )

        # Clients
        for i in range(1, 5):
            host = self.addHost(
                f'h{i}',
                ip=f'10.0.0.{i}/24'
            )
            self.addLink(host, s1)

        # Backend servers
        for i in range(5, 11):
            host = self.addHost(
                f'h{i}',
                ip=f'10.0.0.{i}/24'
            )
            self.addLink(host, s1)


topos = {
    'intelligent': IntelligentLoadBalancerTopo
}
