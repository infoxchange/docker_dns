Docker DNS
==========

A simple TwistD DNS server using custom TLD and Docker as the back end for IP
resolution.

To look up a container:
 - 'A' record query container's hostname with no TLD. Must be an exact match
 - 'A' record query an ID that will match a container with a docker inspect
   command with '.docker' as the TLD. eg: 0949efde23b.docker

Examples
--------
For these examples, we have Docker containers like this:

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

    dig @localhost 0949efde23bf017.docker +noall +answer
    0949efde23bf017.docker.	10	IN	A	172.17.0.2


    dig @localhost 0949.docker +noall +answer
    0949.docker.		10	IN	A	172.17.0.2


    dig @localhost 26ed50b1bf59.docker +noall +answer
    26ed50b1bf59.docker.	10	IN	A	172.17.0.3


    dig @localhost nothing.docker +noall +answer
(no answer given)


    dig @localhost 0949efde23bf +noall +answer
    0949efde23bf.		10	IN	A	172.17.0.2


    dig @localhost my-thing +noall +answer
    my-thing.		10	IN	A	172.17.0.3


    dig @localhost 26ed50b1bf59 +noall +answer
(no answer given)