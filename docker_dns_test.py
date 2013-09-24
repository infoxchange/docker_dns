#!/usr/bin/python

import docker, fudge, itertools, unittest
from docker_dns import dict_lookup, DockerMapping, DockerResolver

# FIXME I can not believe how disgusting this is
def in_generator(gen, val):
    return reduce(
        lambda old,new: old or new == val,
        gen,
        False
    )


class MockDockerClient(object):
    inspect_container_pandas = {
        'ID': 'cidpandaslong',
        'Same': 'Value',
        'Config': {
            'Hostname': 'cuddly-pandas',
        },
        'NetworkSettings': {
            'IPAddress': '127.0.0.1'
        },
    }
    inspect_container_foxes = {
        'ID': 'cidfoxeslong',
        'Same': 'Value',
        'Config': {
            'Hostname': 'sneaky-foxes',
        },
        'NetworkSettings': {
            'IPAddress': '8.8.8.8'
        }
    }
    inspect_container_returns = {
        'cidpandas': inspect_container_pandas,
        'cidpandaslong': inspect_container_pandas,
        'cidfoxes': inspect_container_foxes,
        'cidfoxeslong': inspect_container_foxes,
    }


    containers_return = [
        {'Id': 'cidpandas'},
        {'Id': 'cidfoxes'},
    ]

    def inspect_container(self, cid):
        self.inspect_container_id = cid

        try:
            return self.inspect_container_returns[cid]
        except KeyError:
            response = fudge.Fake()
            response.has_attr(status_code=404, content='PANDAS!')

            exception = docker.client.APIError('bad', response)
            raise exception

    def containers(self, *args, **kwargs):
        return self.containers_return


class DictLookupTest(unittest.TestCase):
    theDict = {
        'pandas': {
            'are': 'cuddly',
            'and': 'awesome',
        },
        'foxes': {
            'are': 'sneaky',
            'and': 'orange',
        },
        'badgers': {
            'are': None,
        },
    }

    def test_basic_one(self):
        self.assertEqual(
            dict_lookup(
                self.theDict,
                ['pandas', 'and']
            ),
            'awesome'
        )

    def test_basic_two(self):
        self.assertEqual(
            dict_lookup(
                self.theDict,
                ['foxes', 'are']
            ),
            'sneaky'
        )

    def test_basic_none(self):
        self.assertEqual(
            dict_lookup(
                self.theDict,
                ['badgers', 'are'],
                'Badgers are none? What?'
            ),
            None
        )

    def test_dict(self):
        self.assertEqual(
            dict_lookup(
                self.theDict,
                ['foxes']
            ),
            self.theDict['foxes']
        )

    def test_default_single_depth(self):
        self.assertEqual(
            dict_lookup(
                self.theDict,
                ['nothing']
            ),
            None
        )

    def test_user_default_single_depth(self):
        self.assertEqual(
            dict_lookup(
                self.theDict,
                ['nothing'],
                'Nobody here but us chickens'
            ),
            'Nobody here but us chickens'
        )

    def test_default_multi_depth(self):
        self.assertEqual(
            dict_lookup(
                self.theDict,
                ['pandas', 'bad']
            ),
            None
        )

    def test_user_default_multi_depth(self):
        self.assertEqual(
            dict_lookup(
                self.theDict,
                ['pandas', 'bad'],
                'NO, THAT\'S A DAMN DIRTY LIE'
            ),
            'NO, THAT\'S A DAMN DIRTY LIE'
        )


class DockerMappingTest(unittest.TestCase):

    def setUp(self):
        self.client  = MockDockerClient()
        self.mapping = DockerMapping(self.client)

    #
    # TEST _ids_from_prop
    #
    def test__ids_from_prop_single_depth(self):
        ids_gen1, ids_gen2 = itertools.tee(
            self.mapping._ids_from_prop(
                ['ID'],
                'cidpandaslong'
            )
        )
        self.assertEqual(sum(1 for _ in ids_gen1), 1)
        self.assertEqual(
            ids_gen2.next(),
            'cidpandaslong'
        )

    def test__ids_from_prop_multi_depth(self):
        ids_gen1, ids_gen2 = itertools.tee(
            self.mapping._ids_from_prop(
                ['NetworkSettings', 'IPAddress'],
                '8.8.8.8'
            )
        )
        self.assertEqual(sum(1 for _ in ids_gen1), 1)
        self.assertEqual(
            ids_gen2.next(),
            'cidfoxeslong'
        )

    def test__ids_from_prop_multi_match(self):
        # FIXME I can not believe how disgusting this is
        ids_gen1, ids_gen2, ids_gen3 = itertools.tee(
            self.mapping._ids_from_prop(
                ['Same'],
                'Value'
            ), 3
        )
        self.assertEqual(sum(1 for _ in ids_gen1), 2)
        self.assertTrue(in_generator(ids_gen2, 'cidpandaslong'))
        self.assertTrue(in_generator(ids_gen3, 'cidfoxeslong'))

    #
    # TEST lookup_container
    #
    def test_lookup_container_hostname(self):
        self.assertEqual(
            self.mapping.lookup_container('cuddly-pandas'),
            self.client.inspect_container_pandas
        )

    def test_lookup_container_id(self):
        self.assertEqual(
            self.mapping.lookup_container('cidfoxes.docker'),
            self.client.inspect_container_foxes
        )

    def test_lookup_container_hostname_none(self):
        self.assertEqual(
            # Raises an APIError 404
            self.mapping.lookup_container('invalid'),
            None
        )

    def test_lookup_container_id_none(self):
        self.assertEqual(
            # Raises an APIError 404
            self.mapping.lookup_container('invalid.docker'),
            None
        )

    #
    # TEST get_a
    #
    def test_get_a_hostname(self):
        self.assertEqual(
            self.mapping.get_a('sneaky-foxes'),
            '8.8.8.8'
        )

    def test_get_a_id(self):
        self.assertEqual(
            self.mapping.get_a('cidpandas.docker'),
            '127.0.0.1'
        )

    def test_get_a_hostname_none(self):
        pass

    def test_get_a_id_none(self):
        pass




def main():
    unittest.main()


if __name__ == '__main__':
    main()