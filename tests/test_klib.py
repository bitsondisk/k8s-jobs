import pytest
from types import SimpleNamespace

from k8s_jobs import klib


@pytest.mark.parametrize('test_template, expected_cmd', [
    ('tests/templates/default_cmd.yaml', 'command: ["ls", "-la"]'),
    ('tests/templates/interpolated_cmd.yaml', 'command: ["/bin/sh", "-c", "date; ls -la"]'),
    ('tests/templates/array_continuation_cmd.yaml', 'command: ["date;", "ls", "-la"]'),
])
def test_generate_yaml(test_template, expected_cmd):
    args = SimpleNamespace(file=test_template,
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
                           volume_name=None)

    temp_yaml = klib.generate_templated_yaml(args)

    with open(temp_yaml.name) as f:
        data = f.read()

    # Test correct file
    assert 'testValue: Yep' in data

    # Test preemtible sections
    assert 'tolerations:' in data
    assert 'gke-preemptible' in data

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
    assert 'command: ["ls", "-la"]' in data
    assert 'name: basic' in data
    assert 'image: basic' in data

    # Test job name
    assert 'generateName: job-name-' in data

    # Test volume mounts
    assert 'mountPath: /static' in data
    assert 'name: k8s-job-volume' in data
    assert 'pdName: test-disk' in data

    args.mount_path = '/test'
    args.volume_name = 'test-volume-name'

    temp_yaml3 = klib.generate_templated_yaml(args)

    with open(temp_yaml3.name) as f:
        data = f.read()

    # Test not using the test file
    assert 'testValue: Yep' not in data

    # Test preemtible sections not in the file
    assert 'tolerations:' not in data
    assert 'gke-preemptible' not in data

    # Test command and image
    assert 'command: ["ls", "-la"]' in data
    assert 'name: basic' in data
    assert 'image: basic' in data

    # Test job name
    assert 'generateName: job-name-' in data

    # Test volume mounts
    assert 'mountPath: /test' in data
    assert 'name: test-volume-name' in data
    assert 'pdName: test-disk' in data

    args.image = None

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

    assert rs8.upper() == rs8
