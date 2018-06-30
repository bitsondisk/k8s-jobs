# Kubernetes Job System
[![Build Status](https://travis-ci.com/freenome/k8s-jobs.svg?token=qCtry4yPNxqPJJfHHJDV&branch=master)](https://travis-ci.com/freenome/k8s-jobs)

This is a set of scripts for starting kubernetes jobs and interactive shells, given the necessary options
on the command line.

## kbatch
```
usage: kbatch [-h] [--file FILE] [--image IMAGE]
              [--container-name CONTAINER_NAME] [--name NAME] [--cpu CPU]
              [--memory MEMORY] [--disk DISK] [--cpu-limit CPU_LIMIT]
              [--memory-limit MEMORY_LIMIT] [--disk-limit DISK_LIMIT]
              [--time TIME] [--preemptible]
              -- [cmd [args...]]

positional arguments:
  -- cmd [args...]      Command with arguments to run in the given container
                        Optional, if your container has a pre-defined command,
                        otherwise required or your pod/job will 'crash' as it
                        has no command to run. You can use 'sleep 6000' for
                        testing an environment, for example.
                        Also note that this command will be run using /bin/sh
                        so if your command includes shell-like syntax that you
                        do not want run in the shell, quote the command, for
                        example: 'perl -Mbignum=bpi -wle "print bpi(2000)"'

optional arguments:
  -h, --help            show this help message and exit
  --version             Show the current version of kbatch
  --file FILE, -f FILE  Config yaml file to use (optional)
  --image IMAGE, -i IMAGE
                        Docker container image to run (required unless a yaml
                        is provided)
  --container-name CONTAINER_NAME
                        Container name to use (optional)
  --name NAME, -n NAME  Name of the job (an autogenerated id will be added to
                        this name)
  --cpu CPU             CPU reservation (In CPUs: 100m (== 0.1), 4)
  --memory MEMORY       Memory reservation (In bytes: 1024, 1e6, 100M, 128Mi)
  --disk DISK           Disk reservation (In bytes: 1024, 1e6, 100M, 128Mi)
  --cpu-limit CPU_LIMIT
                        CPU limit (In CPUs: 100m (== 0.1), 4)
  --memory-limit MEMORY_LIMIT
                        Memory limit (In bytes: 1024, 1e6, 100M, 128Mi)
  --disk-limit DISK_LIMIT
                        Disk limit (In bytes: 1024, 1e6, 100M, 128Mi)
  --time TIME           Time limit (seconds)
  --persistent-disk-name PERSISTENT_DISK_NAME
                        Persistent disk name (required to use a
                        gcePersistentDisk)
  --volume-name VOLUME_NAME
                        Persistent disk volume name (optional)
  --mount-path MOUNT_PATH
                        Mount path for the persistent disk (optional, default
                        is /static)
  --preemptible, -p     Allow scheduling on preemptible nodes
  --script SCRIPT       Execute a bash script from a file from within the job
                        before the command args if they are present
```

This command will run the given docker image or yaml configuration as a batch job through kubernetes,
and returns the job id. It will fill in the appropriate fields for the command and args to run, the job name, and
memory/cpu/disk reservation and/or limits, if given. Note that whether a job name is specified or not an
auto-generated name is used (in Kubernetes) so that a job configuration can be started more than once for
different instances.

Example job command line to calculate pi using perl:

`kbatch -n kbatch-test-pi -i perl --time 100 'perl -Mbignum=bpi -wle "print bpi(2000)"'`

This example job has the name of `kbatch-test-pi`, uses the image `perl`, has a maximum execution time of 100 seconds,
and runs the command `perl -Mbignum=bpi -wle "print bpi(2000)"` inside the container. This also demonstrates the
alternative quoting of the command and args to not parse the parenthesis in the shell.

Note that in order to use preemptible nodes with node taints, you should create a kubernetes node pool with the taint
of `gke-preemptible` as the key, `true` as the value, and `NoSchedule` as the effect. This will prevent jobs that are
not specified as preemptible from being scheduled on the preemptible nodes.

## klist
`usage: klist`

This command lists all currently running jobs. See: `kubectl get jobs` for advanced options.

## kpods
`usage: kpods`

This command lists all currently running pods. See: `kubectl get pods` for advanced options. Note that `kpods -w` will
watch pods and show changes dynamically.

## kexec
`usage: kexec pod-id [-- cmd args ... (optional)]`

This command will start a bash shell in the given pod, or run the given command if specified.

## kstatus
`usage: kstatus job-id`

This command lists detailed information for a given job. See: `kubectl describe job` for advanced options.

## kcancel
`usage: kcancel job-id [additional job-ids]`

This command will cancel one or more running jobs. See: `kubectl delete` for advanced options.
Note that this command can also be used to delete old information for completed jobs.

## klogs
`usage: klogs job-id [additional log options such as -f for tailing the logs]`

This command will find one of the pods a job is running on and run `kubectl logs <POD> <EXTRA_ARGS>` on that pod,
appending any arguments passed to klogs


## krun
```
usage: krun [-h] --image IMAGE [--name NAME] [--env ENV] [--script SCRIPT]
            -- [cmd [args...]]

positional arguments:
  cmd [args...]         Command with arguments to run in the given container
                        (optional)

optional arguments:
  -h, --help            show this help message and exit
  --image IMAGE, -i IMAGE
                        Docker container image to run
  --name NAME, -n NAME  Name of the job (an autogenerated id will be added to
                        this name)
  --env ENV             Environment variable to set in the format
                        "VARIABLE=value"
  --script SCRIPT       Execute a bash script from a file from within the job
                        before the command args if they are present
```

This command will start the given container as an interactive job in kubernetes for shell commands or other interactive
processes for R&D or debugging purposes. If no command or script is specified, this will default to a bash shell.

## Installation
To install the local version for development or usage, run:
`./setup.py install`

Do note that you will need the Google Cloud SDK (for kubectl) installed to use this package.

## Running tests
To lint, run:
`flake8`

To run tests:
`pytest -m pytest . -vvv`

## Deploy new version
After developing, make sure to modify the current version in setup.py before merging.
After merging, run the following commands:
```
git tag v{YOUR_VERSION}
git push --tags
```
Your version should be a semantic version (e.i. 1.2.1)
