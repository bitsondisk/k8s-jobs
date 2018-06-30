import pytest

from k8s_jobs import klib


class Namespace(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@pytest.mark.parametrize('script, cmd_args, expected_cmd_args', [
    ('tests/scripts/hello_world.sh', ['echo', '"Hello, World!"'], [
        'echo ZWNobyAnSGVsbG8sIFdvcmxkIScK | base64 --decode | bash',
        'echo',
        '"Hello, World!"',
    ]),
    ('tests/scripts/hello_world.sh', None, ['echo ZWNobyAnSGVsbG8sIFdvcmxkIScK | base64 --decode | bash']),
    ('tests/scripts/hello_world.sh', [], ['echo ZWNobyAnSGVsbG8sIFdvcmxkIScK | base64 --decode | bash']),
    (None, ['echo', '"Hello, World!"'], ['echo', '"Hello, World!"']),
    ('', ['echo', '"Hello, World!"'], ['echo', '"Hello, World!"']),
    (None, None, None),
    ('', None, None),
    (None, [], []),
])
def test_combine_script_and_args(script, cmd_args, expected_cmd_args):
    args = Namespace(script=script, cmd_args=cmd_args)
    klib.combine_script_and_args(args)

    assert args.cmd_args == expected_cmd_args


@pytest.mark.parametrize('test_template, expected_cmd', [
    ('tests/templates/default_cmd.yaml', 'command: ["ls", "-la"]'),
    ('tests/templates/interpolated_cmd.yaml', 'command: ["/bin/sh", "-c", "date; ls -la"]'),
    ('tests/templates/sh_array_cmd.yaml', 'command: ["/bin/sh", "-c", "ls -la"]'),
    ('tests/templates/array_continuation_cmd.yaml', 'command: ["date;", "ls", "-la"]'),
])
def test_generate_yaml(test_template, expected_cmd):
    args = Namespace(file=test_template,
                     cmd_args=['ls', '-la'],
                     image='syncing/the-ship',
                     preemptible=True,
                     name=None,
                     container_name=None,
                     time=None,
                     cpu=None,
                     memory=None,
                     disk=None,
                     cpu_limit=None,
                     memory_limit=None,
                     disk_limit=None,
                     persistent_disk_name=None,
                     mount_path=None,
                     volume_name=None,
                     volume_read_write=None)

    temp_yaml = klib.generate_templated_yaml(args)

    with open(temp_yaml.name) as f:
        data = f.read()

    # Test correct file
    assert 'testValue: Yep' in data

    # Test preemtible sections
    assert 'tolerations:' in data
    assert 'key: gke-preemptible' in data
    assert 'operator: Equal' in data
    assert "value: 'true'" in data
    assert 'effect: NoSchedule' in data

    # Test command and image
    assert expected_cmd in data
    assert 'name: the-ship' in data
    assert 'image: syncing/the-ship' in data

    args.file = None
    args.preemptible = None
    args.name = 'job-name'
    args.image = 'basic'
    args.persistent_disk_name = 'test-disk'

    temp_yaml2 = klib.generate_templated_yaml(args)

    with open(temp_yaml2.name) as f:
        data = f.read()

    # Test not using the test file
    assert 'testValue: Yep' not in data

    # Test preemtible sections not in the file
    assert 'tolerations:' not in data
    assert 'gke-preemptible' not in data

    # Test command and image
    assert 'command: ["/bin/sh", "-c", "ls -la"]' in data
    assert 'name: basic' in data
    assert 'image: basic' in data

    # Test job name
    assert 'generateName: job-name-' in data

    # Test volume mounts
    assert 'mountPath: /static' in data
    assert 'name: k8s-job-volume' in data
    assert 'pdName: test-disk' in data
    assert 'readOnly: true' in data

    args.mount_path = '/test'
    args.volume_name = 'test-volume-name'
    args.volume_read_write = True
    args.image = 'gcr.io/example-project/jobcontainer:image-tag'

    temp_yaml3 = klib.generate_templated_yaml(args)

    with open(temp_yaml3.name) as f:
        data = f.read()

    # Test not using the test file
    assert 'testValue: Yep' not in data

    # Test preemtible sections not in the file
    assert 'tolerations:' not in data
    assert 'gke-preemptible' not in data

    # Test command and image
    assert 'command: ["/bin/sh", "-c", "ls -la"]' in data
    assert 'name: jobcontainer-image-tag' in data
    assert 'image: gcr.io/example-project/jobcontainer:image-tag' in data

    # Test job name
    assert 'generateName: job-name-' in data

    # Test volume mounts
    assert 'mountPath: /test' in data
    assert 'name: test-volume-name' in data
    assert 'pdName: test-disk' in data
    assert 'readOnly: true' not in data

    args.image = None

    with pytest.raises(RuntimeError):
        klib.generate_templated_yaml(args)


def test_generate_yaml_sections_missing():
    args = Namespace(file='tests/templates/bogus.yaml',
                     cmd_args=['ls', '-la'],
                     image='syncing/the-ship',
                     preemptible=None,
                     name=None,
                     container_name=None,
                     time=None,
                     cpu=None,
                     memory=None,
                     disk=None,
                     cpu_limit=None,
                     memory_limit=None,
                     disk_limit=None,
                     persistent_disk_name=None,
                     mount_path=None,
                     volume_name=None,
                     volume_read_write=None)

    # This should not return an error
    klib.generate_templated_yaml(args)

    args.preemptible = True

    with pytest.raises(RuntimeError):
        klib.generate_templated_yaml(args)

    args.preemptible = None
    args.persistent_disk_name = 'example-disk'

    with pytest.raises(RuntimeError):
        klib.generate_templated_yaml(args)


def test_replace_template():
    lines = ["line1: example", "line2: $(TEST_REPLACE)", "line3: $(SOMETHING_ELSE)"]

    lines_rep1 = klib.replace_template(lines, 'TEST_REPLACE', 'value')
    assert lines_rep1 == ["line1: example", "line2: value", "line3: $(SOMETHING_ELSE)"]

    lines_del1 = klib.replace_template(lines, 'SOMETHING_ELSE', None)
    assert lines_del1 == ["line1: example", "line2: $(TEST_REPLACE)"]

    lines_rep_del = klib.replace_template(lines_rep1, 'SOMETHING_ELSE', None)
    assert lines_rep_del == ["line1: example", "line2: value"]


def test_random_string():
    assert len(klib.random_string(8)) == 8

    assert len(klib.random_string(16)) == 16

    rs8 = klib.random_string(8)

    assert rs8.lower() == rs8


example_json = {
    'test': 1,
    'sub-dict': {
        'a-list': ['a', 'b', 'c'],
        'not-list': 'd',
        'boolean': True
    },
    'another-list': [
        {
            'id': 5
        },
        {
            'name': 'example'
        }
    ]
}


def test_get_path():
    assert klib.get_path(example_json, 'test') == 1
    assert klib.get_path(example_json, 'not-present') is None
    assert klib.get_path(example_json, 'sub-dict.not-list') == 'd'
    assert klib.get_path(example_json, 'sub-dict.a-list.0') == 'a'
    assert klib.get_path(example_json, 'sub-dict.a-list.5') is None
    assert klib.get_path(example_json, 'sub-dict.boolean') is True
    assert klib.get_path(example_json, 'sub-dict.nope') is None
    assert klib.get_path(example_json, 'another-list.0.id') == 5
    assert klib.get_path(example_json, 'another-list.1.name') == 'example'
    assert klib.get_path(example_json, 'another-list.2.not-found') is None

    with pytest.raises(KeyError):
        klib.get_path(example_json, 'test.whoops')

    with pytest.raises(KeyError):
        klib.get_path(example_json, 'another-list.not-an-int')


def test_get_parent_and_key_from_path():
    assert klib.get_parent_and_key_from_path(example_json, 'sub-dict.a-list') == (example_json['sub-dict'], 'a-list')
    assert klib.get_parent_and_key_from_path(example_json, 'test') == (example_json, 'test')

    with pytest.raises(KeyError):
        assert klib.get_parent_and_key_from_path(example_json, '')

    with pytest.raises(KeyError):
        assert klib.get_parent_and_key_from_path(example_json, '.')

    with pytest.raises(KeyError):
        assert klib.get_parent_and_key_from_path(example_json, 'sub-dict.a-list.')

    with pytest.raises(KeyError):
        assert klib.get_parent_and_key_from_path(example_json, 'sub-dict.does-not-exist.key')

    with pytest.raises(KeyError):
        assert klib.get_parent_and_key_from_path(example_json, 'does-not-exist.key')


def test_set_append_path():
    test_json = {
        'example': 5,
        'path': {
            'to-set': 'old',
            'list': ['to-append', 'to']
        }
    }

    klib.set_path(test_json, 'example', 10)
    klib.set_path(test_json, 'path.to-set', 'new')
    klib.insert_or_append_path(test_json, 'path.list', 'ok')
    klib.insert_or_append_path(test_json, 'path.new-list', 'another')

    with pytest.raises(KeyError):
        klib.insert_or_append_path(test_json, 'example', 7)

    assert test_json == {
        'example': 10,
        'path': {
            'to-set': 'new',
            'list': ['to-append', 'to', 'ok'],
            'new-list': ['another']
        }
    }
