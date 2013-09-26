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

import docker
import re

from requests.exceptions import RequestException
from twisted.application import internet, service
from twisted.internet import defer
from twisted.names import common, dns, server
from twisted.names.error import DNSQueryTimeoutError, DomainError
from twisted.python import failure
from warnings import warn


# FIXME replace with a more generic solution like operator.attrgetter
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
            dic = dic[k]
        else:
            return default
    return dic


class DockerMapping(object):
    """
    Look up docker container data
    """

    id_re = re.compile(r'([a-z0-9]+)\.docker')

    def __init__(self, api):
        """
        Args:
            api: Docker Client instance used to do API communication
        """

        self.api = api

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
                self.api.inspect_container(c_lite['Id'])
                for c_lite in self.api.containers(all=True)
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
            # FIXME Should be able to support multiple
            try:
                container_id = ids.next()
            except StopIteration:
                return None

        try:
            return self.api.inspect_container(container_id)

        except docker.client.APIError as ex:
            # 404 is valid, others aren't
            if ex.response.status_code != 404:
                warn(ex)

            return None

        except RequestException as ex:
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

        container = self.lookup_container(name)

        if container is None:
            return None

        addr = container['NetworkSettings']['IPAddress']

        if addr is '':
            return None

        return addr


# pylint:disable=too-many-public-methods
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

        # Change to this ASAP when Twisted uses object base
        # super(DockerResolver, self).__init__()
        common.ResolverBase.__init__(self)
        self.ttl = 10

    def _a_records(self, name):
        """
        Get A records from a query name

        Args:
            name: DNS query name to look up

        Returns:
            Tuple of formatted DNS replies
        """

        addr = self.mapping.get_a(name)
        if not addr:
            raise DomainError(name)

        return tuple([
            dns.RRHeader(name, dns.A, dns.IN, self.ttl,
                         dns.Record_A(addr, self.ttl),
                         CONFIG['authoritive'])
        ])

    def lookupAddress(self, name, timeout=None):
        try:
            records = self._a_records(name)
            return defer.succeed((records, (), ()))

        # We need to catch everything. Uncaught exceptian will make the server
        # stop responding
        except:  # pylint:disable=bare-except
            if CONFIG['no_nxdomain']:
                # FIXME surely there's a better way to give SERVFAIL
                exception = DNSQueryTimeoutError(name)
            else:
                exception = DomainError(name)

            return defer.fail(failure.Failure(exception))


def main():
    """
    Set everything up
    """

    # Create docker
    if CONFIG['docker_url']:
        docker_client = docker.Client(CONFIG['docker_url'])
    else:
        docker_client = docker.Client()

    # Create our custom mapping and resolver
    mapping = DockerMapping(docker_client)
    resolver = DockerResolver(mapping)

    # Create twistd stuff to tie in our custom components
    factory = server.DNSServerFactory(clients=[resolver])
    factory.noisy = False

    # Protocols to bind
    bind_list = []
    if 'tcp' in CONFIG['bind_protocols']:
        bind_list.append((internet.TCPServer, factory))  # noqa pylint:disable=no-member

    if 'udp' in CONFIG['bind_protocols']:
        proto = dns.DNSDatagramProtocol(factory)
        proto.noisy = False
        bind_list.append((internet.UDPServer, proto))  # noqa pylint:disable=no-member

    # Register the service
    ret = service.MultiService()
    for (klass, arg) in bind_list:
        svc = klass(
            CONFIG['bind_port'],
            arg,
            interface=CONFIG['bind_interface']
        )
        svc.setServiceParent(ret)

    # DO IT NOW
    ret.setServiceParent(service.IServiceCollection(application))

# Load the config
try:
    from config import CONFIG  # pylint:disable=no-name-in-module,import-error
except ImportError:
    CONFIG = {}

# Merge user config over defaults
DEFAULT_CONFIG = {
    'docker_url': None,
    'bind_interface': '',
    'bind_port': 53,
    'bind_protocols': ['tcp', 'udp'],
    'no_nxdomain': True,
    'authoritive': True,
}
CONFIG = dict(DEFAULT_CONFIG.items() + CONFIG.items())

application = service.Application('dnsserver', 1, 1)  # noqa pylint:disable=invalid-name
main()


# Doin' it wrong
if __name__ == '__main__':
    import sys
    print "Usage: twistd -y %s" % sys.argv[0]
