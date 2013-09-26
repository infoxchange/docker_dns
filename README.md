Docker DNS
==========
[![Build Status](https://travis-ci.org/infoxchange/docker_dns.png?branch=master)](https://travis-ci.org/infoxchange/docker_dns)

A simple Twisted DNS server using custom TLD and Docker as the back end for IP
resolution.

To look up a container:
 - 'A' record query container's hostname with no TLD. Must be an exact match
 - 'A' record query an ID that will match a container with a docker inspect
   command with '.docker' as the TLD. eg: 0949efde23b.docker

Install/Run
-----------

Just install from requirements (in a virtualenv if you'd like)

   pip install -r requirements.txt --use-mirrors

That's it! To run, just

    twistd -y docker_dns.py

This will start a DNS server on port 53 (default DNS port). To make this
useful, you probably want to combine it with your regular DNS in something like
Dnsmasq.

Examples
--------
Dig output is shortened for brevity. We have Docker containers like this:

    ID                  IMAGE               COMMAND             CREATED             STATUS              PORTS
    26ed50b1bf59        ubuntu:12.04        /bin/bash           4 seconds ago       Up 4 seconds
    0949efde23bf        ubuntu:12.04        /bin/bash           18 hours ago        Up 18 hours

0949efde23bf has:

 - ID: 0949efde23bf01727203638dafb0ac15b2e68db9effe03b90687d67a96ab6ee7
 - IP: 172.17.0.2
 - Hostname: 0949efde23bf

26ed50b1bf59 has:

 - ID: 26ed50b1bf5947727bee4910f3d93674d823496c615940238219b5346cc0fc4e
 - IP: 172.17.0.3
 - Hostname: my-thing

Container IDs are variable length. They can be long:

    dig 0949efde23bf017.docker
    ;; Got answer:
    ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 51840
    ;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

    ;; ANSWER SECTION:
    0949efde23bf017.docker. 10  IN  A   172.17.0.2


Or they can be short:

    dig 0949.docker
    ;; Got answer:
    ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 42797
    ;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

    ;; ANSWER SECTION:
    0949.docker.		10	IN	A	172.17.0.2

And the other container:

    dig 26ed50b1bf59.docker
    ;; Got answer:
    ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 25901
    ;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

    ;; ANSWER SECTION:
    26ed50b1bf59.docker.	10	IN	A	172.17.0.3

When a container doesn't exist, no answer is given:

    dig nothing.docker
    ;; Got answer:
    ;; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 24269
    ;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0

You can look up by hostname by removing the .docker TLD:

    dig 0949efde23bf
    ;; Got answer:
    ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 61822
    ;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

    ;; ANSWER SECTION:
    0949efde23bf.		10	IN	A	172.17.0.2

Here's a manually defined hostname:

    dig my-thing
    ;; Got answer:
    ;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 3355
    ;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

    ;; ANSWER SECTION:
    my-thing.		10	IN	A	172.17.0.3

And the host name that would have been automatically assigned for the above
container:

    dig 26ed50b1bf59
    ;; Got answer:
    ;; ->>HEADER<<- opcode: QUERY, status: SERVFAIL, id: 12687
    ;; flags: qr rd ra; QUERY: 1, ANSWER: 0, AUTHORITY: 0, ADDITIONAL: 0

Configuration
-------------
Config is done in the `config.py` file. There's a skeleton in
`config.py.sample`. Below are the default config values. Currently,
configuration is rather limited.

    CONFIG = {
        # URL to connect to the Docker API. docker-py defaults to
        # unix://var/run/docker.sock
        'docker_url': None

        # socket.bind defaults to 0.0.0.0
        'bind_interface': '',
        'bind_port': 53,
        'bind_protocols': ['tcp', 'udp'],

        # When the request matches no docker container, we should return
        # NXDOMAIN, however the OS interprets this as "doesn't exist anywhere"
        # so things like google.com fail. This will return SERVFAIL rather than
        # NXDOMAIN so secondary DNS is used
        'no_nxdomain': True,

        # Makes successful requests authoritive
        'authoritive': True,
    }

Contributing
------------
There are plenty of FIXME comments dotted around the code. No list of feature
ideas yet, but there is scope for big improvements to current simple
functionality.

All pull requests should 10/10 in pylint, have no PEP8 warnings and should
include reasonable test coverage.

To run:

 - `pip install -r test_requirements.txt --use-mirrors`
 - `pylint --rcfile=pylint.conf *.py`
 - `pep8 *.py`
