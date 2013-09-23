#!/usr/bin/python

import docker, re

from requests.exceptions import ConnectionError
from twisted.application import internet, service
from twisted.internet import defer
from twisted.names import cache, client, common, dns, server
from twisted.python import failure

def dict_lookup(dic, key_path, default=None):
    for k in key_path:
        if k in dic:
            dic = dic.get(k, default)
        else:
            return default
    return dic

class DockerMapping(object):
    """
    Look up docker container data
    """

    id_re = re.compile('([a-z0-9]+)\.docker')

    def __init__(self, client):
        self.client = client

    def __contains__(self, name):
        c = self.get_container(name)
        if not c:
            return False

        try:
            c['NetworkSettings']['IPAddress']
            return True
        except KeyError:
            return False

    def _ids_from_prop(self, key_path, value):
        return (
            c['ID']
            for c in (
                self.client.inspect_container(c_lite['Id'])
                for c_lite in self.client.containers(all=True)
            )
            if dict_lookup(c, key_path, None) == value
            if 'ID' in c
        )

    def get_container(self, name):

        match = self.id_re.match(name)
        if match:
            container_id = match.group(1)
        else:
            ids = self._ids_from_prop(('Config', 'Hostname'), unicode(name))
            try:
                container_id = ids.next()
            except StopIteration:
                return None

        try:
            return self.client.inspect_container(container_id)
        except docker.client.APIError as ex:
            print ex
            return None
        except ConnectionError as ex:
            print ex
            return None

    def get_a(self, name):
        addr = self.get_container(name)['NetworkSettings']['IPAddress']
        return addr


class DockerResolver(common.ResolverBase):
    """
    DNS resolver to resolve queries with a DockerMapping instance.
    """

    def __init__(self, mapping):
        self.mapping = mapping
        common.ResolverBase.__init__(self)
        self.ttl = 10

    def _aRecords(self, name):
        addr = self.mapping.get_a(name)
        return tuple([
            dns.RRHeader(name, dns.A, dns.IN, self.ttl,
                         dns.Record_A(addr, self.ttl))
        ])

    def lookupAddress(self, name, timeout = None):
        if name in self.mapping:
            return defer.succeed((self._aRecords(name), (), ()))
        else:
            return defer.fail(failure.Failure(dns.DomainError(name)))


application = service.Application('dnsserver', 1, 1)
mapping = DockerMapping(docker.Client())
resolver = DockerResolver(mapping)


# create the protocols
f = server.DNSServerFactory(clients=[resolver])
p = dns.DNSDatagramProtocol(f)
f.noisy = p.noisy = False


# register as tcp and udp
ret = service.MultiService()
PORT=53

for (klass, arg) in [(internet.TCPServer, f), (internet.UDPServer, p)]:
    s = klass(PORT, arg)
    s.setServiceParent(ret)


# run all of the above as a twistd application
ret.setServiceParent(service.IServiceCollection(application))


# run it through twistd!
if __name__ == '__main__':
    import sys
    print "Usage: twistd -y %s" % sys.argv[0]