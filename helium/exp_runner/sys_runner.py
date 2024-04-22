import docker
import sys

EXP_CONTAINER_LABEL = "helium-exp"

def host_to_docker_host_url(host):
    return 'unix://var/run/docker.sock' if host == 'localhost' else "ssh://root@%s" % host

def log(str, end="\n"):
    print(str, file=sys.stderr, end=end, flush=True)

class DockerNodeSystem:
    def __init__(self, N, T, parties_host, cloud_host, rate_limit, delay, circuit_rounds):
        self.N = N
        self.T = T
        self.rate_limit = rate_limit
        self.delay = delay
        self.circuit_rounds = circuit_rounds
        self.parties_host = parties_host
        self.cloud_host = cloud_host
        self.parties_docker_host = docker.DockerClient(base_url=host_to_docker_host_url(parties_host), use_ssh_client= parties_host != 'localhost')
        self.cloud_docker_host = self.parties_docker_host if cloud_host == parties_host else docker.DockerClient(base_url=host_to_docker_host_url(cloud_host), use_ssh_client= cloud_host != 'localhost')
        
        self.clean_all()
        self.nodes = [self.create_player(i) for i in range(N)]

        nets = [net.name for net in self.parties_docker_host.networks.list(names=["expnet"])]
        if "expnet" not in nets:
            log("creating network")
            self.parties_docker_host.networks.create("expnet", driver="bridge")
        
        log("new docker system")

    def get_all(self):
        all_containers =  self.parties_docker_host.containers.list(filters={"label": EXP_CONTAINER_LABEL}, all=True, ignore_removed=True)
        if self.parties_docker_host != self.cloud_docker_host:
            all_containers += self.cloud_docker_host.containers.list(filters={"label": EXP_CONTAINER_LABEL}, all=True, ignore_removed=True)
        return all_containers

    def stop_all(self):
        for container in self.get_all():
            container.kill()

    def clean_all(self):
        for container in self.get_all():
            try:
                container.remove(force=True)
            except:
                continue

    def start_cloud(self):
        cmd = '-node_id cloud -n_party %d -threshold %d -cloud_address %s -expRounds %d' % (self.N, self.T, "%s:40000" % self.cloud_host, self.circuit_rounds)
        net = "expnet" if self.cloud_docker_host == self.parties_docker_host else "host"
        #net = "host"
        return self.cloud_docker_host.containers.run('exp:helium',
                                        name="cloud",
                                        hostname="cloud",
                                        command=cmd,
                                        network=net,
                                        labels=[EXP_CONTAINER_LABEL],
                                        detach=True)

    def create_player(self, i):
        container_name = "node-%d" % i
        cloud_host = "cloud" if self.cloud_host == 'localhost' else self.cloud_host
        cmd = "./shape_traffic_and_start.sh -node_id node-%d -n_party %d -threshold %d -cloud_address %s -expRounds %d" % (i, self.N, self.T, "%s:40000" % cloud_host, self.circuit_rounds)
        caps = ["NET_ADMIN"]
        net = "expnet"
        env = {"RATE_LIMIT": self.rate_limit, "DELAY": self.delay}
        container =  self.parties_docker_host.containers.create('exp:helium',
                                                name=container_name,
                                                hostname=container_name,
                                                entrypoint=cmd,
                                                cap_add=caps,
                                                network=net,
                                                environment=env,
                                                labels=[EXP_CONTAINER_LABEL],
                                                detach=True)
        log("created node-%d" % i)
        return container


    def start_player(self, i):
        self.nodes[i].start()

    def kill_player(self, i):
        self.nodes[i].kill()