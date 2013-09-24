#!/usr/bin/python

"""
A simple TwistD DNS server using custom TLD and Docker as the back end for IP
resolution.

To look up a container:
 - 'A' record query container's hostname with no TLD. Must be an exact match
 - 'A' record query an ID that will match a container with a docker inspect
   command with '.docker' as the TLD. eg: 0949efde23b.docker

Code heavily modified from
http://stackoverflow.com/a/4401671/509043

Author: Ricky Cook <ricky@infoxchange.net.au>
"""

import docker, re

from requests.exceptions import ConnectionError
from twisted.application import internet, service
from twisted.internet import defer
from twisted.names import cache, client, common, dns, server
from twisted.python import failure
from warnings import warn


def dict_lookup(dic, key_path, default=None):
    """
    Look up value in a nested dict

    Args:
        dic: The dictionary to search
        key_path: An iterable containing an ordered list of dict keys to
                  traverse
        default: Value to return in case nothing is found

    Returns:
        Value of the dict at the nested location given, or default if no value
        was found
    """

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
        """
        Args:
            client: Docker Client instance used to do Docker communication
        """

        self.client = client

    def __contains__(self, name):
        """
        Check to see if we have a container matching the query name

        Args:
            name: DNS query name to look up

        Returns:
            True if the query finds 1 or more containers, False otherwise
        """

        try:
            c = self.lookup_container(name)
        except:
            # Catch all is bad, but this MUST return
            return False

        if not c:
            return False

        try:
            c['NetworkSettings']['IPAddress']
            return True
        except KeyError:
            return False

    def _ids_from_prop(self, key_path, value):
        """
        Get IDs of containers where their config matches a value

        Args:
            key_path: An iterable containing an ordered list of container
                      config keys to traverse
            value: What the value at key_path must match to qualify

        Returns:
            Generator with a list of containers that match the config value
        """

        return (
            c['ID']
            for c in (
                self.client.inspect_container(c_lite['Id'])
                for c_lite in self.client.containers(all=True)
            )
            if dict_lookup(c, key_path, None) == value
            if 'ID' in c
        )

    def lookup_container(self, name):
        """
        Gets the container config from a DNS lookup name, or returns None if
        one could not be found

        Args:
            name: DNS query name to look up

        Returns:
            Container config dict for the first matching container
        """

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
            # 404 is valid, others aren't
            if ex.response.status_code != 404:
                warn(ex)

            return None

        except ConnectionError as ex:
            warn(ex)
            return None

    def get_a(self, name):
        """
        Get an IPv4 address from a query name to be used in A record lookups

        Args:
            name: DNS query name to look up

        Returns:
            IPv4 address for the query name given
        """

        addr = self.lookup_container(name)['NetworkSettings']['IPAddress']
        return addr


class DockerResolver(common.ResolverBase):
    """
    DNS resolver to resolve queries with a DockerMapping instance.
    """

    def __init__(self, mapping):
        """
        Args:
            mapping: DockerMapping instance for lookups
        """

        self.mapping = mapping
        common.ResolverBase.__init__(self)
        self.ttl = 10

    def _aRecords(self, name):
        """
        Get A records from a query name

        Args:
            name: DNS query name to look up

        Returns:
            Tuple of formatted DNS replies
        """

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


app = service.Application('dnsserver', 1, 1)

# Create our custom mapping and resolver
mapping = DockerMapping(docker.Client())
resolver = DockerResolver(mapping)

# Create twistd stuff to tie in our custom components
factory = server.DNSServerFactory(clients=[resolver])
proto = dns.DNSDatagramProtocol(factory)
factory.noisy = proto.noisy = False

# Register the service
ret = service.MultiService()
for (klass, arg) in [(internet.TCPServer, factory), (internet.UDPServer, proto)]:
    s = klass(53, arg)
    s.setServiceParent(ret)

# DO IT NOW
ret.setServiceParent(service.IServiceCollection(app))


# Doin' it wrong
if __name__ == '__main__':
    import sys
    print "Usage: twistd -y %s" % sys.argv[0]