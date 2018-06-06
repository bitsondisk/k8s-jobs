import json
import os
import random
import string
import tempfile
import pkgutil


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
}

yaml_tolerate_preemptible = '''
      tolerations:
      - key: cloud.google.com/gke-preemptible
        operator: Equal
        value: "true"
        effect: NoSchedule
'''


def replace_template(lines, key, value):
    if value is None:
        # Remove line(s)
        return [l for l in lines if f'$({key})' not in l]
    else:
        # Substitute value(s)
        return [l.replace(f'$({key})', value) for l in lines]


def convert_template_yaml(data, args):
    lines = data.split('\n')

    template_values = {template: getattr(args, attr) for attr, template in arg_templates.items()}

    # Ensure that the command and args are in the format ["command", "arg1", "arg2", ...]
    if template_values['CMD_ARGS']:
        template_values['CMD_ARGS'] = json.dumps(template_values['CMD_ARGS'])

    if not template_values['JOB_NAME']:
        template_values['JOB_NAME'] = 'kjob'

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

        data = convert_template_yaml(data, args)
    else:
        if not args.image:
            raise RuntimeError('A pre-defined yaml file or docker image must be specified!')

        data = convert_template_yaml(pkgutil.get_data("k8s_jobs.klib", "default.yaml").decode('utf-8'), args)

    if args.preemptible:
        # Remove the extra newline in the file
        data = data[:-1] + yaml_tolerate_preemptible

    temp_yaml = tempfile.NamedTemporaryFile()

    # Write the templated yaml to disk in a temporary file
    temp_yaml.write(data.encode('utf-8'))
    temp_yaml.flush()
    os.fsync(temp_yaml.fileno())

    return temp_yaml


def random_string(size):
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(size))
