import requests

class ServerManager:
    def __init__(self, servers):
        self.servers = sorted(servers, key=lambda s: s["priority"])
        self.current_index = 0

    def current_server(self):
        return self.servers[self.current_index]

    def health_check(self, server):
        try:
            r = requests.get(server["url"] + "/health", timeout=2)
            return r.status_code == 200
        except:
            return False

    def failover(self):
        for i in range(1, len(self.servers)):
            next_index = (self.current_index + i) % len(self.servers)
            if self.health_check(self.servers[next_index]):
                self.current_index = next_index
                return self.servers[next_index]
        return None