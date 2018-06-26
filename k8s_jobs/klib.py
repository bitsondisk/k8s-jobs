import json
import os
import random
import string
import tempfile
import pkgutil
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
    'volume_name': 'VOLUME_NAME'
}

yaml_tolerate_preemptible = '''
      tolerations:
      - key: gke-preemptible
        operator: Equal
        value: "true"
        effect: NoSchedule
'''

yaml_disk_mount_containers = '''
        volumeMounts:
          - mountPath: $(MOUNT_PATH)
            name: $(VOLUME_NAME)
            readOnly: true
'''

yaml_disk_mount_spec = '''
      volumes:
        - name: $(VOLUME_NAME)
          gcePersistentDisk:
            pdName: $(PD_NAME)
            fsType: ext4
'''


def replace_template(lines, key, value):
    if value is None:
        # Remove line(s)
        return [l for l in lines if f'$({key})' not in l]
    else:
        # Substitute value(s)
        return [l.replace(f'$({key})', value) for l in lines]


def convert_template_yaml(data, args):
    template_values = {template: getattr(args, attr) for attr, template in arg_templates.items()}

    # Ensure that the command and args are in the format ["command", "arg1", "arg2", ...]
    cmd_args = template_values['CMD_ARGS']
    if cmd_args:
        config_template = yaml.load(data)
        containers_config = config_template.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
        for i, container_config in enumerate(containers_config):
            command = container_config['command']
            if isinstance(command, list):
                new_command = []
                for command_segment in command:
                    if command_segment == '$(CMD_ARGS)':
                        new_command += cmd_args
                    elif '$(CMD_ARGS)' in command_segment:
                        new_command.append(command_segment.replace('$(CMD_ARGS)', ' '.join(cmd_args)))
                    else:
                        new_command.append(command_segment)

                cmd_args_name = f'CMD_ARGS{i}'
                config_template['spec']['template']['spec']['containers'][i]['command'] = f'$({cmd_args_name})'
                template_values[cmd_args_name] = json.dumps(new_command)

        template_values['CMD_ARGS'] = json.dumps(cmd_args)

    data = yaml.dump(config_template)
    lines = data.split('\n')

    if not template_values['JOB_NAME']:
        template_values['JOB_NAME'] = 'kjob'

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

    if args.persistent_disk_name:
        # Remove the extra newline in the file
        data = data[:-1] + yaml_disk_mount_containers

    if args.preemptible:
        data = data[:-1] + yaml_tolerate_preemptible

    if args.persistent_disk_name:
        data = data[:-1] + yaml_disk_mount_spec

    data = convert_template_yaml(data, args)

    temp_yaml = tempfile.NamedTemporaryFile()

    # Write the templated yaml to disk in a temporary file
    temp_yaml.write(data.encode('utf-8'))
    temp_yaml.flush()
    os.fsync(temp_yaml.fileno())

    return temp_yaml


def random_string(size):
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(size))
