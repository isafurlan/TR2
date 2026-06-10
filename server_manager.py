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
        for i in range(self.current_index + 1, len(self.servers)):
            if self.health_check(self.servers[i]):
                self.current_index = i
                return self.servers[i]
        return None