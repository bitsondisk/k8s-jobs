import base64
import json
import os
import random
import re
import string
import subprocess as sp
import tempfile
import pkgutil

from semantic_version import Version
import yaml


arg_templates = {
    'name': 'JOB_NAME',
    'container_name': 'CONTAINER_NAME',
    'image': 'CONTAINER_IMAGE',
    'cmd_args': 'CMD_ARGS',
    'time': 'TIME_LIMIT_SECONDS',
    'cpu': 'CPU_REQUEST',
    'memory': 'MEM_REQUEST',
    'disk': 'DISK_REQUEST',
    'cpu_limit': 'CPU_LIMIT',
    'memory_limit': 'MEM_LIMIT',
    'disk_limit': 'DISK_LIMIT',
    'persistent_disk_name': 'PD_NAME',
    'mount_path': 'MOUNT_PATH',
    'volume_name': 'VOLUME_NAME',
    'volume_read_write': 'VOLUME_READ_WRITE',
    'preemptible': 'ALLOW_PREEMPTIBLE',
    'retry_limit': 'RETRY_LIMIT',
}

# These args are only used for adding additional sections to the YAML,
# and are not replaced as templates.
arg_flags = [
    'VOLUME_READ_WRITE',
    'ALLOW_PREEMPTIBLE',
]

yaml_tolerate_preemptible = {
    'key': 'gke-preemptible',
    'operator': 'Equal',
    'value': 'true',
    'effect': 'NoSchedule'
}

yaml_disk_mount_containers = {
    'mountPath': '$(MOUNT_PATH)',
    'name': '$(VOLUME_NAME)',
    'readOnly': '$(VOLUME_READ_ONLY)'
}

yaml_disk_mount_spec = {
    'name': '$(VOLUME_NAME)',
    'gcePersistentDisk': {
        'pdName': '$(PD_NAME)',
        'fsType': 'ext4',
        'readOnly': '$(VOLUME_READ_ONLY)'
    }
}


millicpu_request_matcher = re.compile('(?P<millicpus>[0-9]+)m')
kubernetes_version_matcher = re.compile('v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)')


LABEL_ARGUMENTS = ['partition']


def adjust_cpu_request(args):
    if not args.cpu:
        return

    millicpu_request = millicpu_request_matcher.match(args.cpu)

    if millicpu_request:
        millicpu_request = millicpu_request.group('millicpus')

        args.cpu = '{millicpus}m'.format(millicpus=int(millicpu_request) - 500)
    else:
        args.cpu = str(float(args.cpu) - 0.5)


def adjust_time(args):
    if not args.time:
        return

    args.time = str(int(args.time) * 60)


def add_node_selectors(args, config_template):
    labels = {
        label_name: value for label_name, value in [
            tuple(label_arg.split('=')) for label_arg in args.labels
        ] if value
    }
    labels_from_args = {
        label_name: getattr(args, label_name)
        for label_name in LABEL_ARGUMENTS if getattr(args, label_name)
    }

    duplicate_labels = set(labels_from_args) & set(labels)

    if duplicate_labels:
        raise ValueError('You cannot specify "{duplicate_labels}" as labels since you '
                         'specified them as CLI arguments'.format(duplicate_labels=', '.join(duplicate_labels)))

    labels.update(labels_from_args)

    if labels:
        set_path(config_template, 'spec.template.spec.nodeSelector', labels)


def verify_retry_limit_supported(num_retries):
    if int(num_retries) < 1:
        return

    kubernetes_version_response, _ = sp.Popen('kubectl version -o json', shell=True, stdout=sp.PIPE).communicate()
    kubernetes_version_json = json.loads(kubernetes_version_response.decode('utf-8'))
    kubernetes_version = kubernetes_version_matcher.match(
        kubernetes_version_json['serverVersion']['gitVersion'],
    ).group('version')

    if Version.coerce(kubernetes_version) < Version('1.11.0'):
        raise RuntimeError('Your Kubernetes version is v{kubernetes_version}. '
                           'Kubernetes versions prior to v1.11.0 will retry an indefinite amount of '
                           'times with retries set to > 0'.format(kubernetes_version=kubernetes_version))


def combine_script_and_args(args):
    if args.script:
        with open(args.script, 'r+b') as script_file:
            script_contents = script_file.read()

        script_encoded = base64.b64encode(script_contents).decode('utf-8')
        script_cmd = 'echo {script_encoded} | base64 --decode | bash'.format(script_encoded=script_encoded)

        if args.cmd_args:
            args.cmd_args.insert(0, script_cmd)
        else:
            args.cmd_args = [script_cmd]


def replace_template(lines, key, value):
    if value is None:
        # Remove line(s)
        return [l for l in lines if '$({key})'.format(key=key) not in l]
    else:
        # Substitute value(s)
        return [l.replace('$({key})'.format(key=key), value) for l in lines]


def convert_template_yaml(data, args):
    adjust_cpu_request(args)
    adjust_time(args)

    template_values = {template: getattr(args, attr) for attr, template in arg_templates.items()}

    config_template = yaml.load(data)

    add_node_selectors(args, config_template)

    # Ensure that the command and args are in the format ["command", "arg1", "arg2", ...]
    cmd_args = template_values['CMD_ARGS']
    if cmd_args:
        containers_config = get_path(config_template, 'spec.template.spec.containers', [])
        for i, container_config in enumerate(containers_config):
            command = container_config['command']
            if isinstance(command, list):
                new_command = []
                sh_found = False
                for command_segment in command:
                    if command_segment.startswith('/bin/sh'):
                        sh_found = True

                    if command_segment == '$(CMD_ARGS)' and not sh_found:
                        new_command += cmd_args
                    elif '$(CMD_ARGS)' in command_segment:
                        new_command.append(command_segment.replace('$(CMD_ARGS)', ' '.join(cmd_args)))
                    else:
                        new_command.append(command_segment)

                cmd_args_name = 'CMD_ARGS{i}'.format(i=i)
                config_template['spec']['template']['spec']['containers'][i]['command'] = '$({cmd_args_name})'.format(
                    cmd_args_name=cmd_args_name,
                )
                template_values[cmd_args_name] = json.dumps(new_command)

        template_values['CMD_ARGS'] = json.dumps(cmd_args)

    if template_values['ALLOW_PREEMPTIBLE']:
        spec_config = get_path(config_template, 'spec.template.spec')

        if not spec_config:
            raise RuntimeError('Could not determine where to insert preemptible nodes yaml configuration, ensure your '
                               'yaml file contains the sections spec.template.spec')

        insert_or_append_path(config_template, 'spec.template.spec.tolerations', yaml_tolerate_preemptible)


    if template_values['PD_NAME']:
        spec_config = get_path(config_template, 'spec.template.spec')
        containers_config = get_path(config_template, 'spec.template.spec.containers')

        if not spec_config or not containers_config:
            raise RuntimeError('Could not determine where to insert preemptible nodes yaml configuration, ensure your '
                               'yaml file contains the sections spec.template.spec and spec.template.spec.containers '
                               'with at least one container')

        insert_or_append_path(config_template, 'spec.template.spec.volumes', yaml_disk_mount_spec)

        for i in range(len(containers_config)):
            insert_or_append_path(config_template,
                                  'spec.template.spec.containers.{}.volumeMounts'.format(i),
                                  yaml_disk_mount_containers)

    data = yaml.dump(config_template, default_flow_style=False)
    lines = data.split('\n')

    template_values['VOLUME_READ_ONLY'] = 'true' if not template_values['VOLUME_READ_WRITE'] else None

    for flag in arg_flags:
        del template_values[flag]

    if not template_values['JOB_NAME']:
        template_values['JOB_NAME'] = 'kjob'

    if template_values['RETRY_LIMIT']:
        verify_retry_limit_supported(template_values['RETRY_LIMIT'])

    if not template_values['MOUNT_PATH']:
        template_values['MOUNT_PATH'] = '/static'

    if not template_values['VOLUME_NAME']:
        template_values['VOLUME_NAME'] = 'k8s-job-volume'

    # Auto-set the container name if none is given
    if not template_values['CONTAINER_NAME']:
        if template_values['CONTAINER_IMAGE']:
            image_path = template_values['CONTAINER_IMAGE']
            slash_pos = image_path.rfind('/', 0, len(image_path) - 1)
            if slash_pos != -1:
                container_name = image_path[slash_pos + 1:]
            else:
                container_name = image_path

            container_name = re.sub('[^A-Za-z0-9]', '-', container_name)
            template_values['CONTAINER_NAME'] = container_name
        else:
            template_values['CONTAINER_NAME'] = 'container-job'

    for template, value in template_values.items():
        lines = replace_template(lines, template, value)

    return '\n'.join(lines)


def generate_templated_yaml(args):
    if args.file:
        with open(args.file) as f:
            data = f.read()

    else:
        if not args.image:
            raise RuntimeError('A pre-defined yaml file or docker image must be specified!')

        data = pkgutil.get_data("k8s_jobs.klib", "default.yaml").decode('utf-8')

    data = convert_template_yaml(data, args)

    temp_yaml = tempfile.NamedTemporaryFile()

    # Write the templated yaml to disk in a temporary file
    temp_yaml.write(data.encode('utf-8'))
    temp_yaml.flush()
    os.fsync(temp_yaml.fileno())

    return temp_yaml


def random_string(size):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(size))


def get_path(obj, path, default=None):
    for key in path.split('.'):
        if isinstance(obj, list):
            try:
                key_int = int(key)
            except (TypeError, ValueError):
                raise KeyError('Found a list, key "{}" is not a valid integer index.'.format(key))

            if key_int >= len(obj):
                return default

            obj = obj[key_int]

        elif isinstance(obj, dict):
            if key not in obj:
                return default
            else:
                obj = obj[key]

        elif key:
            raise KeyError('Found non-dict or list, expected to be able to index for key "{}"'.format(key))

    return obj


def get_parent_and_key_from_path(obj, path):
    last_dot = path.rfind('.')

    if last_dot == -1:
        key = path

        update_obj = obj
    else:
        key = path[last_dot + 1:]

        update_obj = get_path(obj, path[:last_dot])

    if not key:
        raise KeyError('Badly-formatted path for updates, must not end in . and contain a valid key to set')

    if not update_obj:
        raise KeyError('Path "{}" was not found in {}'.format(path, obj))

    return update_obj, key


def set_path(obj, path, value):
    update_obj, key = get_parent_and_key_from_path(obj, path)

    update_obj[key] = value


def insert_or_append_path(obj, path, value):
    update_obj, key = get_parent_and_key_from_path(obj, path)

    if key in update_obj:
        if isinstance(update_obj[key], list):
            update_obj[key].append(value)
        else:
            raise KeyError('Existing value is not a list for "{}" in {}'.format(path, update_obj))
    else:
        update_obj[key] = [value]
