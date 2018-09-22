# -*- coding: utf-8 -*-
"""
Module for handling maas calls.

:optdepends:    pyapi-maas Python adapter
:configuration: This module is not usable until the following are specified
                either in a pillar or in the minion's config file::

        maas.url: 'https://maas.domain.com/'
        maas.token: fdsfdsdsdsfa:fsdfae3fassd:fdsfdsfsafasdfsa

"""

from __future__ import absolute_import

import collections
import copy
import hashlib
import io
import json
import logging
import time
import urllib2
# Salt utils
from salt.exceptions import CommandExecutionError, SaltInvocationError

LOG = logging.getLogger(__name__)

SIZE = {
    "M": 1000000,
    "G": 1000000000,
    "T": 1000000000000,
}

RAID = {
    0: "raid-0",
    1: "raid-1",
    5: "raid-5",
    10: "raid-10",
}

# Import third party libs
HAS_MASS = False
try:
    from maas_client import MAASClient, MAASDispatcher, MAASOAuth
    HAS_MASS = True
except ImportError:
    LOG.debug('Missing MaaS client module is Missing. Skipping')


def __virtual__():
    """
    Only load this module if maas-client
    is installed on this minion.
    """
    if HAS_MASS:
        return 'maasng'
    return False


APIKEY_FILE = '/var/lib/maas/.maas_credentials'


def _format_data(data):
    class Lazy:
        def __str__(self):
            return ' '.join(['{0}={1}'.format(k, v)
                             for k, v in data.iteritems()])
    return Lazy()


def _create_maas_client(api_url=None):
    if not api_url:
        api_url = 'http://localhost:5240/MAAS'
    global APIKEY_FILE
    try:
        api_token = file(APIKEY_FILE).read().splitlines()[-1].strip()\
            .split(':')
    except:
        LOG.exception('token')
    auth = MAASOAuth(*api_token)
    dispatcher = MAASDispatcher()
    return MAASClient(auth, dispatcher, api_url)


def _get_blockdevice_id_by_name(hostname, device):

    # TODO validation
    return list_blockdevices(hostname)[device]["id"]


def _get_volume_group_id_by_name(hostname, device):

    # TODO validation
    return list_volume_groups(hostname)[device]["id"]


def _get_volume_id_by_name(hostname, volume_name, volume_group, maas_volname=True):

    if not maas_volname:
        # MAAS-like name
        volume_name = str("%s-%s" % (volume_group, volume_name))
    # TODO validation
    return get_volumes(hostname, volume_group)[volume_name]["id"]


def _get_partition_id_by_name(hostname, device, partition):

    # TODO validation
    return list_partitions(hostname, device)[partition]["id"]

# MACHINE SECTION


def get_machine(hostname):
    """
    Get information aboout specified machine

    CLI Example:

    .. code-block:: bash

        salt-call maasng.get_machine server_hostname
    """
    try:
        return list_machines()[hostname]
    except KeyError:
        return {"error": "Machine not found on MaaS server"}


def list_machines(status_filter=None):
    """
    Get list of all machines from maas server

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.list_machines
        salt 'maas-node' maasng.list_machines status_filter=[Deployed,Ready]
    """
    machines = {}
    maas = _create_maas_client()
    json_res = json.loads(maas.get(u'api/2.0/machines/').read())
    for item in json_res:
        if not status_filter or item['status_name'] in status_filter:
            machines[item["hostname"]] = item
    return machines


def create_machine():
    # TODO

    return False


def update_machine():
    # TODO

    return False

def delete_machine(hostname):
    """
    Delete specified machine

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.delete_machine server_hostname
        salt-call maasng.delete_machine server_hostname
    """
    result = {}
    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.debug('delete_machine: {}'.format(system_id))
    maas.delete(
        u"api/2.0/machines/{0}/".format(system_id)).read()

    result["new"] = "Machine {0} deleted".format(hostname)
    return result

def action_machine(hostname, action, comment=None):
    """
    Send simple action (e.g. mark_broken, mark_fixed) to machine.

    :param action:  Action to send for machine (one of MaaS' op codes)
    :param comment: Optional comment for the event log.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.action_machine server_hostname mark_broken comment='dead'
    """
    result = {}
    data = {}
    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.debug('action_machine: {}'.format(system_id))

    # TODO validation
    if comment:
        data["comment"] = comment
    json_res = json.loads(maas.post(
        u"api/2.0/machines/{0}/".format(system_id), action, **data).read())
    LOG.info(json_res)
    result["new"] = "Machine {0} action {1} executed".format(hostname, action)

    return result

# END MACHINE SECTION
# RAID SECTION


def create_raid(hostname, name, level, disks=[], partitions=[], **kwargs):
    """
    Create new raid on machine.

    CLI Example:

    .. code-block:: bash

        salt-call maasng.create_raid hostname=kvm03 name=md0 level=1 disks=[vdb,vdc] partitions=[vdd-part1,vde-part1]
    """

    result = {}

    if len(disks) == 0 and len(partitions) == 0:
        result["error"] = "Disks or partitions need to be provided"

    disk_ids = []
    partition_ids = []

    for disk in disks:
        try:
            disk_ids.append(str(_get_blockdevice_id_by_name(hostname, disk)))
        except KeyError:
            result["error"] = "Device {0} does not exists on machine {1}".format(
                disk, hostname)
            return result

    for partition in partitions:
        try:
            device = partition.split("-")[0]
            device_part = list_partitions(hostname, device)
            partition_ids.append(str(device_part[partition]["id"]))
        except KeyError:
            result["error"] = "Partition {0} does not exists on machine {1}".format(
                partition, hostname)
            return result

    data = {
        "name": name,
        "level": RAID[int(level)],
        "block_devices": disk_ids,
        "partitions": partition_ids,
    }

    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.info(system_id)

    # TODO validation
    LOG.info(data)
    json_res = json.loads(
        maas.post(u"api/2.0/nodes/{0}/raids/".format(system_id), None, **data).read())
    LOG.info(json_res)
    result["new"] = "Raid {0} created".format(name)

    return result


def list_raids(hostname):
    """
    Get list all raids on machine

    CLI Example:

    .. code-block:: bash

        salt-call maasng.list_raids server_hostname
    """

    raids = {}
    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    # TODO validation
    json_res = json.loads(
        maas.get(u"api/2.0/nodes/{0}/raids/".format(system_id)).read())
    LOG.debug('list_raids:{} {}'.format(system_id, json_res))
    for item in json_res:
        raids[item["name"]] = item
    return raids


def get_raid(hostname, name):
    """
    Get information about specific raid on machine

    CLI Example:

    .. code-block:: bash

        salt-call maasng.get_raids server_hostname md0
    """

    return list_raids(hostname)[name]


def _get_raid_id_by_name(hostname, raid_name):
    return get_raid(hostname, raid_name)['id']


def delete_raid(hostname, raid_name):
    """
    Delete RAID on a machine.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.delete_raid server_hostname raid_name
        salt-call maasng.delete_raid server_hostname raid_name
    """
    result = {}
    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    raid_id = _get_raid_id_by_name(hostname, raid_name)
    LOG.debug('delete_raid: {} {}'.format(system_id, raid_id))
    maas.delete(
        u"api/2.0/nodes/{0}/raid/{1}/".format(system_id, raid_id)).read()

    result["new"] = "Raid {0} deleted".format(raid_name)
    return result

# END RAID SECTION
# BLOCKDEVICES SECTION


def list_blockdevices(hostname):
    """
    Get list of all blockdevices (disks) on machine

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.list_blockdevices server_hostname
        salt-call maasng.list_blockdevices server_hostname
    """
    ret = {}

    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.info(system_id)

    # TODO validation if exists

    json_res = json.loads(
        maas.get(u"api/2.0/nodes/{0}/blockdevices/".format(system_id)).read())
    LOG.info(json_res)
    for item in json_res:
        ret[item["name"]] = item

    return ret


def get_blockdevice(hostname, name):
    """
    Get information about blockdevice (disk) on machine

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.get_blockdevice server_hostname sda
        salt-call maasng.get_blockdevice server_hostname sda
    """

    return list_blockdevices(hostname)[name]

# END BLOCKDEVICES SECTION
# PARTITIONS


def list_partitions(hostname, device):
    """
    Get list of all partitions on specific device located on specific machine

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.list_partitions server_hostname sda
        salt-call maasng.list_partitions server_hostname sda
    """
    ret = {}
    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.info(system_id)

    partitions = get_blockdevice(hostname, device)["partitions"]
    LOG.info(partitions)

    #json_res = json.loads(maas.get(u"api/2.0/nodes/{0}/blockdevices/{1}/partitions/".format(system_id, device_id)).read())
    # LOG.info(json_res)

    if len(device) > 0:
        for item in partitions:
            name = item["path"].split('/')[-1]
            ret[name] = item

    return ret


def get_partition(hostname, device, partition):
    """
    Get information about specific parition on device located on machine

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.get_partition server_hostname disk_name partition
        salt-call maasng.get_partition server_hostname disk_name partition

        root_size = size in GB
    """

    return list_partitions(partition)[name]


def create_partition(hostname, disk, size, fs_type=None, mount=None):
    """
    Create new partition on device.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.create_partition server_hostname disk_name 10 ext4 "/"
        salt-call maasng.create_partition server_hostname disk_name 10 ext4 "/"
    """
    # TODO validation
    result = {}
    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.info(system_id)

    device_id = _get_blockdevice_id_by_name(hostname, disk)
    LOG.info(device_id)

    value, unit = size[:-1], size[-1]
    calc_size = str(int(value) * SIZE[unit])
    LOG.info(calc_size)

    data = {
        "size": calc_size
    }

    # TODO validation
    partition = json.loads(maas.post(
        u"api/2.0/nodes/{0}/blockdevices/{1}/partitions/".format(system_id, device_id), None, **data).read())
    LOG.info(partition)
    result["partition"] = "Partition created on {0}".format(disk)

    if fs_type != None:
        data_fs_type = {
            "fstype": fs_type
        }
        partition_id = str(partition["id"])
        LOG.info("Partition id: " + partition_id)
        # TODO validation
        json_res = json.loads(maas.post(u"api/2.0/nodes/{0}/blockdevices/{1}/partition/{2}".format(
            system_id, device_id, partition_id), "format", **data_fs_type).read())
        LOG.info(json_res)
        result["filesystem"] = "Filesystem {0} created".format(fs_type)

    if mount != None:
        data = {
            "mount_point": mount
        }

        # TODO validation
        json_res = json.loads(maas.post(u"api/2.0/nodes/{0}/blockdevices/{1}/partition/{2}".format(
            system_id, device_id, str(partition['id'])), "mount", **data).read())
        LOG.info(json_res)
        result["mount"] = "Mount point {0} created".format(mount)

    return result


def delete_partition(hostname, disk, partition_name):
    """
    Delete partition on device.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.delete_partition server_hostname disk_name partition_name
        salt-call maasng.delete_partition server_hostname disk_name partition_name

        root_size = size in GB
    """
    result = {}
    data = {}
    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.info(system_id)

    device_id = _get_blockdevice_id_by_name(hostname, disk)
    LOG.info(device_id)

    partition_id = _get_partition_id_by_name(hostname, disk, partition_name)

    maas.delete(u"api/2.0/nodes/{0}/blockdevices/{1}/partition/{2}".format(
        system_id, device_id, partition_id)).read()
    result["new"] = "Partition {0} deleted".format(partition_name)
    return result


def delete_partition_by_id(hostname, disk, partition_id):
    """
    Delete partition on device. Partition spefified by id of parition

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.delete_partition_by_id server_hostname disk_name partition_id
        salt-call maasng.delete_partition_by_id server_hostname disk_name partition_id

        root_size = size in GB
    """
    result = {}
    data = {}
    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.info(system_id)

    device_id = _get_blockdevice_id_by_name(hostname, disk)
    LOG.info(device_id)

    maas.delete(u"api/2.0/nodes/{0}/blockdevices/{1}/partition/{2}".format(
        system_id, device_id, partition_id)).read()
    result["new"] = "Partition {0} deleted".format(partition_id)
    return result
# END PARTITIONS
# DISK LAYOUT


def drop_storage_schema(hostname, disk=None):
    """
    #1. Drop lv
    #2. Drop vg
    #3. Drop md # need to zero-block?
    #3. Drop part
    """

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Storage schema on {0} will be removed'.format(
            hostname)
        return ret
    # TODO validation if exists
    vgs = list_volume_groups(hostname)
    for vg in vgs:
        delete_volume_group(hostname, vg)

    raids = list_raids(hostname)
    for raid in raids:
        delete_raid(hostname, raid)

    blocks = list_blockdevices(hostname)
    for block_d in blocks:
        partitions = __salt__['maasng.list_partitions'](hostname, block_d)
        for partition_name, partition in partitions.iteritems():
            LOG.info('delete partition:\n{}'.format(partition))
            __salt__['maasng.delete_partition_by_id'](
                hostname, block_d, partition["id"])


def update_disk_layout(hostname, layout, root_size=None, root_device=None, volume_group=None, volume_name=None, volume_size=None):
    """
    Update disk layout. Flat or LVM layout supported.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.update_disk_layout server_hostname lvm root_size=None, root_device=None, volume_group=None, volume_name=None, volume_size=None
        salt-call maasng.update_disk_layout server_hostname lvm root_size=None, root_device=None, volume_group=None, volume_name=None, volume_size=None

        root_size = size in GB
    """
    result = {}
    data = {
        "storage_layout": layout,
    }

    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.info(system_id)

    if layout == 'custom':
        drop_storage_schema(hostname)
        result["new"] = {
            "storage_layout": layout,
        }

        return result

    if root_size != None:
        bit_size = str(root_size * 1073741824)
        LOG.info(bit_size)
        data["root_size"] = bit_size

    if root_device != None:
        LOG.info(root_device)
        data["root_device"] = str(
            _get_blockdevice_id_by_name(hostname, root_device))

    if layout == 'lvm':
        if volume_group != None:
            LOG.info(volume_group)
            data["vg_name"] = volume_group
        if volume_name != None:
            LOG.info(volume_name)
            data["lv_name"] = volume_name
        if volume_size != None:
            vol_size = str(volume_size * 1073741824)
            LOG.info(vol_size)
            data["lv_size"] = vol_size

    # TODO validation
    json_res = json.loads(maas.post(
        u"api/2.0/machines/{0}/".format(system_id), "set_storage_layout", **data).read())
    LOG.info(json_res)
    result["new"] = {
        "storage_layout": layout,
    }

    return result

# END DISK LAYOUT
# LVM


def list_volume_groups(hostname):
    """
    Get list of all volume group on machine.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.list_volume_groups server_hostname
        salt-call maasng.list_volume_groups server_hostname
    """
    volume_groups = {}

    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.info(system_id)

    # TODO validation if exists

    json_res = json.loads(
        maas.get(u"api/2.0/nodes/{0}/volume-groups/".format(system_id)).read())
    LOG.info(json_res)
    for item in json_res:
        volume_groups[item["name"]] = item
    # return
    return volume_groups


def get_volume_group(hostname, name):
    """
    Get information about specific volume group on machine.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.list_blockdevices server_hostname
        salt-call maasng.list_blockdevices server_hostname
    """
    # TODO validation that exists
    return list_volume_groups(hostname)[name]


def create_volume_group(hostname, volume_group_name, disks=[], partitions=[]):
    """
    Create new volume group on machine. Disks or partitions needs to be provided.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.create_volume_group volume_group_name, disks=[sda,sdb], partitions=[]
        salt-call maasng.create_volume_group server_hostname
    """
    result = {}

    data = {
        "name": volume_group_name,
    }

    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.info(system_id)

    disk_ids = []
    partition_ids = []

    for disk in disks:
        p_disk = get_blockdevice(hostname, disk)
        if p_disk["partition_table_type"] == None:
            disk_ids.append(str(p_disk["id"]))
        else:
            result["error"] = "Device {0} on" \
                              "machine {1} cointains partition" \
                              "table".format(disk, hostname)
            return result

    for partition in partitions:
        try:
            device = partition.split("-")[0]
            device_part = list_partitions(hostname, device)
            partition_ids.append(str(device_part[partition]["id"]))
        except KeyError:
            result["error"] = "Partition {0} does" \
                              "not exists on " \
                              "machine {1}".format(partition, hostname)
            return result

    data["block_devices"] = disk_ids
    data["partitions"] = partition_ids
    LOG.info(partition_ids)
    LOG.info(partitions)

    # TODO validation
    json_res = json.loads(maas.post(
        u"api/2.0/nodes/{0}/volume-groups/".format(system_id), None, **data).read())
    LOG.info(json_res)
    result["new"] = "Volume group {0} created".format(json_res["name"])

    return result


def delete_volume_group(hostname, name):
    """
    Delete volume group on machine.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.delete_volume_group server_hostname vg0
        salt-call maasng.delete_volume_group server_hostname vg0
    """

    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.debug('delete_volume_group:{}'.format(system_id))

    vg_id = str(_get_volume_group_id_by_name(hostname, name))
    for vol in get_volumes(hostname, name):
        delete_volume(hostname, vol, name)

    # TODO validation
    json_res = json.loads(maas.delete(
        u"api/2.0/nodes/{0}/volume-group/{1}/".format(system_id, vg_id)).read() or 'null')
    LOG.info(json_res)

    return True


def create_volume(hostname, volume_name, volume_group, size, fs_type=None,
                  mount=None):
    """
    Create volume on volume group.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.create_volume server_hostname volume_name, volume_group, size, fs_type=None, mount=None
        salt-call maasng.create_volume server_hostname volume_name, volume_group, size, fs_type=None, mount=None
    """

    data = {
        "name": volume_name,
    }

    value, unit = size[:-1], size[-1]
    bit_size = str(int(value) * SIZE[unit])
    LOG.info(bit_size)

    data["size"] = bit_size

    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.info(system_id)

    volume_group_id = str(_get_volume_group_id_by_name(hostname, volume_group))

    LOG.info(volume_group_id)

    # TODO validation
    json_res = json.loads(maas.post(u"api/2.0/nodes/{0}/volume-group/{1}/".format(
        system_id, volume_group_id), "create_logical_volume", **data).read())
    LOG.info(json_res)

    if fs_type != None or mount != None:
        ret = create_volume_filesystem(
            hostname, volume_group + "-" + volume_name, fs_type, mount)

    return True


def delete_volume(hostname, volume_name, volume_group):
    """
    Delete volume from volume group.
    Tips: maas always use 'volume_group-volume_name' name schema.Example: 'vg0-glusterfs'
          This function expexts same format.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.delete_volume server_hostname volume_name volume_group
        salt 'maas-node' maasng.delete_volume server_hostname vg0-vol0 vg0
        salt-call maasng.delete_volume server_hostname volume_name volume_group
    """

    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    LOG.debug('delete_volume:{}'.format(system_id))

    volume_group_id = str(_get_volume_group_id_by_name(hostname, volume_group))
    volume_id = str(_get_volume_id_by_name(
        hostname, volume_name, volume_group))

    if None in [volume_group_id, volume_id]:
        return False

    data = {
        "id": volume_id,
    }

    # TODO validation
    json_res = json.loads(maas.post(u"api/2.0/nodes/{0}/volume-group/{1}/".format(
        system_id, volume_group_id), "delete_logical_volume", **data).read() or 'null')
    return True


def get_volumes(hostname, vg_name):
    """
    Get list of volumes in volume group.
    """
    volumes = {}
    _volumes = list_volume_groups(
        hostname)[vg_name].get('logical_volumes', False)
    if _volumes:
        for item in _volumes:
            volumes[item["name"]] = item
    return volumes

# END LVM


def create_volume_filesystem(hostname, device, fs_type=None, mount=None):

    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]

    blockdevices_id = _get_blockdevice_id_by_name(hostname, device)
    data = {}
    if fs_type != None:
        data["fstype"] = fs_type
        # TODO validation
        json_res = json.loads(maas.post(u"/api/2.0/nodes/{0}/blockdevices/{1}/".format(
            system_id, blockdevices_id), "format", **data).read())
        LOG.info(json_res)

    if mount != None:
        data["mount_point"] = mount
        # TODO validation
        json_res = json.loads(maas.post(u"/api/2.0/nodes/{0}/blockdevices/{1}/".format(
            system_id, blockdevices_id), "mount", **data).read())
        LOG.info(json_res)

    return True


def set_boot_disk(hostname, name):
    """
    Create volume on volume group.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.set_boot_disk server_hostname disk_name
        salt-call maasng.set_boot_disk server_hostname disk_name
    """
    data = {}
    result = {}
    maas = _create_maas_client()
    system_id = get_machine(hostname)["system_id"]
    blockdevices_id = _get_blockdevice_id_by_name(hostname, name)

    maas.post(u"/api/2.0/nodes/{0}/blockdevices/{1}/".format(
        system_id, blockdevices_id), "set_boot_disk", **data).read()
    # TODO validation for error response
    # (disk does not exists and node does not exists)
    result["new"] = "Disk {0} was set as bootable".format(name)

    return result

# NETWORKING


def list_fabric():
    """
    Get list of all fabric

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.list_fabric
    """
    fabrics = {}
    maas = _create_maas_client()
    json_res = json.loads(maas.get(u'api/2.0/fabrics/').read())
    LOG.info(json_res)
    for item in json_res:
        fabrics[item["name"]] = item
    return fabrics


def check_fabric(name):
    """
    Simple check that fabric already defined
    Return format:
    update  - require update
    correct - fully coincides # not implemented
    not_exist  - need's to be created
    """

    ret = 'not_exist'
    fabrics = list_fabric()
    if name in fabrics.keys():
        LOG.debug("Requested fabrics with  name:{} already exist".format(name))
        ret = 'update'
    return ret


def check_fabric_guess_with_cidr(name, cidrs):
    """
     Check, that fabric  already defined OR it was autodiscovered
     WA to fix issue with hardcoded 'fabric-0'
     - Find all auto-discovered subnets by cidr
     - find all subnets, that SHOULD be configured to THIS subent
     Warning: most probably, will fail if some subnet defined
     to another fabric :(

    { 'update'    : ID }  - require update
    { 'correct'   : ID } - fully coincides # not implemented
    { 'not_exist' : None }  - need's to be created

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.check_fabric_guess_with_cidr name='' cidrs=[]
    """

    ret = {'not_exist': None}
    fabrics = list_fabric()
    # Simple check
    if name in fabrics:
        LOG.debug("Requested fabrics with name:{} already exist".format(name))
        f_id = fabrics[name]['id']
        ret = {'update': f_id}
    # Cidr check
    # All discovered subnets by cidr
    d_subnets = list_subnets(sort_by='cidr')
    # Check, that requested cidr already in discovered.
    # If it is - it would mean that fabric already
    # exist(fabric-0,most probably) but should be renamed.
    # Works only for first shot ;(
    # due curren-single-maas logic for 'vlan-subnet' mapping.
    # Probably, it will fail with future MAAS releases.
    for cidr in cidrs:
        if cidr in d_subnets:
            f_id = d_subnets[cidr]['vlan']['fabric_id']
            f_name = d_subnets[cidr]['vlan']['fabric']
            LOG.warning("Detected cidr:{} in fabric:{}".format(cidr, f_name))
            LOG.warning("Guessing, that fabric "
                        "with current name:{}\n should be "
                        "renamed to:{}".format(f_name, name))
            ret = {'update': f_id}
            return ret
    return ret


def create_fabric(name, description=None, fabric_id=None, update=False):
    """
    Create new fabric.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.create_fabric name='123'
    """
    result = {}
    data = {
        "name": name,
        "class_type": '',

    }
    if description:
        data['description'] = description

    maas = _create_maas_client()
    json_res = None
    try:
        if update:
            json_res = json.loads(
                maas.put(u"api/2.0/fabrics/{0}/".format(fabric_id),
                         **data).read())
            result["new"] = "Fabric  {0} created".format(json_res["name"])
        else:
            json_res = json.loads(
                maas.post(u"api/2.0/fabrics/", None, **data).read())
            result["changes"] = "Fabric  {0} updated".format(json_res["name"])
    except Exception as inst:
        LOG.debug("create_fabric data:{}".format(data))
        try:
            m = inst.readlines()
        except:
            m = inst.message
        LOG.error("Message:{0}".format(m))
        result['result'] = False
        result['comment'] = 'Error creating fabric: {0}'.format(name)
        result['error'] = m
        return result
    LOG.debug("crete_fabric:{}".format(json_res))
    result['result'] = True
    return result


def list_subnets(sort_by='name'):
    """
    Get list of subnets from maas server

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.list_subnets
    """
    subnets = {}
    maas = _create_maas_client()
    json_res = json.loads(maas.get(u'api/2.0/subnets/').read())
    for item in json_res:
        subnets[item[sort_by]] = item
    return subnets


def list_vlans(fabric, sort_by='vid'):
    """
    Get list of vlans in fabric

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.list_vlans fabric_name
    """
    vlans = {}
    maas = _create_maas_client()
    fabric_id = get_fabricid(fabric)

    try:
        json_res = json.loads(
            maas.get(u'api/2.0/fabrics/{0}/vlans/'.format(fabric_id)).read())
    except Exception as inst:
        m = inst.readlines()
        LOG.error("Message:{0}".format(m))
    LOG.debug(json_res)
    for item in json_res:
        vlans[item[sort_by]] = item
    return vlans


def get_fabricid(fabric):
    """
    Get id for specific fabric

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.get_fabricid fabric_name
    """
    try:
        return list_fabric()[fabric]['id']
    except KeyError:
        return {"error": "Fabric not found on MaaS server"}


def check_vlan_in_fabric(fabric, vlan):
    """
    Check that VLAN exactly defined
    Return format:
    update  - require update
    correct - fully coincides # not implemented
    not_exist  - need's to be created
    """

    ret = 'not_exist'
    vlans = list_vlans(fabric)
    if vlan in vlans.keys():
        LOG.debug("Requested VLAN:{} already exist"
                  "in FABRIC:{}".format(vlan, fabric))
        ret = 'update'
    return ret


def create_vlan_in_fabric(name, fabric, vlan, description, primary_rack, mtu=1500,
                          dhcp_on=False, update=False, vlan_id=""):
    """
    Update vlan
    CLI Example:
    .. code-block:: bash
        salt 'maas-node' maasng.update_vlan name, fabric, vid, description, dhcp_on
    """
    result = {}

    data = {
        "name": name,
        "dhcp_on": str(dhcp_on),
        "description": description,
        "primary_rack": list_racks()[primary_rack]['system_id'],
    }
    if mtu:
        data['mtu'] = str(mtu)
    vlan = str(vlan)
    maas = _create_maas_client()
    fabric_id = get_fabricid(fabric)
    try:
        if update:
            # MAAS have buggy logic here. Fallowing api reference, here should
            # be passed VID - which mean, API ID for vlan.
            # Otherwise, at least for maas 2.3.3-6498-ge4db91d exactly VLAN
            # should be passed. so, make temp.backward-convertation.
            # json_res = json.loads(maas.put(u'api/2.0/fabrics/{0}/vlans/{1}/'.format(fabric_id,vlan_id), **data).read())
            json_res = json.loads(maas.put(
                u'api/2.0/fabrics/{0}/vlans/{1}/'.format(fabric_id, vlan),
                **data).read())
        else:
            data['vid'] = str(vlan)
            json_res = json.loads(maas.post(
                u'api/2.0/fabrics/{0}/vlans/'.format(fabric_id), None, **data).read())
    except Exception as inst:
        LOG.debug("create_vlan_in_fabric data:{}".format(data))
        try:
            m = inst.readlines()
        except:
            m = inst.message
        LOG.error("Message:{0}".format(m))
        result['result'] = False
        result['comment'] = 'Error updating vlan: {0}'.format(name)
        result['error'] = m
        return result
    LOG.debug("create_vlan_in_fabric:{}".format(json_res))
    result["new"] = "Vlan {0} was updated".format(json_res["name"])

    return result


def check_subnet(cidr, name, fabric, gateway_ip):
    """
    Check that subnet exactly defined
    Return format:
    update  - require update
    correct - fully coincides # not implemented
    not_exist  - need's to be created
    """

    ret = 'not_exist'
    subnets = list_subnets(sort_by='cidr')
    if cidr in subnets.keys():
        LOG.debug("Requested subnet cidr:{} already exist".format(cidr))
        ret = 'update'
    return ret


def create_subnet(cidr='', name='', fabric='', gateway_ip='', vlan='',
                  update=False, subnet_id=''):
    """
    Create subnet

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.create_subnet cidr, name, fabric, gateway_ip
    """

    fabric_id = get_fabricid(fabric)
    result = {}
    vlan = str(vlan)
    data = {
        "cidr": cidr,
        "name": name,
        "fabric": str(fabric_id),
        "gateway_ip": gateway_ip,
        'vlan': vlan,
    }
    maas = _create_maas_client()
    # FIXME: vlan definition not work in 2.3.3-6498-ge4db91d.
    LOG.warning("Ignoring parameter vlan:{}".format(vlan))
    data.pop('vlan', '')
    try:
        if update:
            json_res = json.loads(
                maas.put(u"api/2.0/subnets/{0}/".format(subnet_id), **data).read())
        else:
            json_res = json.loads(
                maas.post(u"api/2.0/subnets/", None, **data).read())
    except Exception as inst:
        LOG.debug("create_subnet data:{}".format(data))
        try:
            m = inst.readlines()
        except:
            m = inst.message
        LOG.error("Message:{0}".format(m))
        result['result'] = False
        result['comment'] = 'Error creating subnet: {0}'.format(name)
        result['error'] = m
        return result
    LOG.debug("create_subnet:{}".format(json_res))
    result["new"] = "Subnet {0} with CIDR {1}" \
                    "and gateway {2} was created".format(
                        name, cidr, gateway_ip)

    return result


def get_subnet(subnet):
    """
    Get details for specific subnet

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.get_subnet subnet_name
    """
    try:
        return list_subnets()[subnet]
    except KeyError:
        return {"error": "Subnet not found on MaaS server"}


def get_subnetid(subnet):
    """
    Get id for specific subnet

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.get_subnetid subnet_name
    """
    try:
        return list_subnets()[subnet]['id']
    except KeyError:
        return {"error": "Subnet not found on MaaS server"}


def list_ipranges():
    """
    Get list of all ipranges from maas server

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.list_ipranges
    """
    ipranges = {}
    maas = _create_maas_client()
    json_res = json.loads(maas.get(u'api/2.0/ipranges/').read())
    for item in json_res:
        ipranges[item["start_ip"]] = item
    return ipranges


def create_iprange(type_range, start_ip, end_ip, subnet=None, comment=None):
    """
    Create ip range

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.create_iprange type, start ip, end ip, comment
    """
    result = {}

    data = {
        "type": type_range,
        "start_ip": start_ip,
        "end_ip": end_ip,
    }
    if comment:
        data['comment'] = comment
    if subnet:
        subnet_id = list_subnets()[subnet]['id']
        data['subnet'] = str(subnet_id)
    maas = _create_maas_client()
    _name = "Type:{}: {}-{}".format(type_range, start_ip, end_ip)
    try:
        json_res = json.loads(
            maas.post(u"api/2.0/ipranges/", None, **data).read())
    except Exception as inst:
        try:
            m = inst.readlines()
        except:
            m = inst.message
        LOG.error("Message:{0}".format(m))
        result['result'] = False
        result['comment'] = 'Error creating iprange:{0}'.format(_name)
        result['error'] = m
        return result
    result["new"] = "Iprange: {0} has been created".format(_name)
    LOG.debug("create_iprange:{}".format(json_res))

    return result


def get_iprangeid(start_ip):
    """
    Get id for ip range from maas server

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.get_iprangeid start_ip
    """
    try:
        return list_ipranges()[start_ip]['id']
    except KeyError:
        return {"error": "Ip range not found on MaaS server"}


def get_startip(start_ip):
    """
    Get start ip for ip range

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.get_startip start ip
    """
    try:
        return list_ipranges()[start_ip]
    except KeyError:
        return {"error": "Ip range not found on MaaS server"}
# END NETWORKING

# MAAS CONFIG SECTION


def _getHTTPCode(url):
    code = '003'
    m = ''
    try:
        connection = urllib2.urlopen(url)
        code = connection.getcode()
        connection.close()
    except (urllib2.HTTPError, urllib2.URLError) as e:
        try:
            code = e.getcode()
        except:
            m = e.reason
            pass
        LOG.debug("Unexpected http code:{} from "
                  "url:{}\nwith message:{}".format(code, url, m))
        pass
    return code


def wait_for_http_code(url=None, expected=[200]):
    """
    Simple function, which just wait for avaible api, aka wait for 200.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.wait_for_http_code url expected=[200]

    """
    ret = {}
    started_at = time.time()
    poll_time = 5
    timeout = 60 * 2
    while _getHTTPCode(url) not in expected:
        c_timeout = timeout - (time.time() - started_at)
        if c_timeout <= 0:
            ret['result'] = False
            ret["comment"] = "api:{} not answered in time".format(url)
            return ret
        LOG.info(
            "Waiting for api:{0}\n"
            "sleep for:{1}s "
            "Left:{2}/{3}s".format(url, poll_time, round(c_timeout),
                                   timeout))
        time.sleep(poll_time)
    ret['result'] = True
    ret["comment"] = "MAAS API:{} up.".format(url)
    return ret


def _get_boot_source_id_by_url(url):
    # FIXME: fix ret\validation
    try:
        bs_id = get_boot_source(url=url)["id"]
    except KeyError:
        return {"error": "boot-source:{0} not exist!".format(url)}
    return bs_id


def get_boot_source(url=None):
    """
    Read a boot source by url. If url not specified - return all.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.get_boot_source url

    """
    boot_sources = {}
    maas = _create_maas_client()
    json_res = json.loads(maas.get(u'api/2.0/boot-sources/').read() or 'null')
    for item in json_res:
        boot_sources[str(item["url"])] = item
    if url:
        return boot_sources.get(url, {})
    return boot_sources


def delete_boot_source(url, bs_id=None):
    """
    Delete a boot source by url.

    CLI Example:

    .. code-block:: bash

        sal 'maas-node' maasng.delete url

    """
    result = {}
    if not bs_id:
        bs_id = _get_boot_source_id_by_url(url)
    maas = _create_maas_client()
    json_res = json.loads(maas.delete(
        u'/api/2.0/boot-sources/{0}/'.format(bs_id)).read() or 'null')
    LOG.debug("delete_boot_source:{}".format(json_res))
    result["new"] = "Boot-resource {0} deleted".format(url)
    return result


def boot_sources_delete_all_others(except_urls=[]):
    """
    Delete all boot-sources, except defined in 'except_urls' list.
    """
    result = {}
    maas_boot_sources = get_boot_source()
    if 0 in [len(except_urls), len(maas_boot_sources)]:
        result['result'] = None
        result[
            "comment"] = "Exclude or maas sources for delete empty. No changes goinng to be."
        return result
    for url in maas_boot_sources.keys():
        if url not in except_urls:
            LOG.info("Removing boot-source:{}".format(url))
            boot_resources_import(action='stop_import', wait=True)
            result["changes"] = delete_boot_source(url)
    return result


def create_boot_source(url, keyring_filename='', keyring_data='', wait=False):
    """
    Create and import maas boot-source: link to maas-ephemeral repo
    Be aware, those step will import resource to rack ctrl, but you also need to import
    them into the region!


    :param url:               The URL of the BootSource.
    :param keyring_filename:  The path to the keyring file for this BootSource.
    :param keyring_data:      The GPG keyring for this BootSource, base64-encoded data.

    """

    # TODO: not work with 'update' currently => keyring update may fail.
    result = {}

    data = {
        "url": url,
        "keyring_filename": keyring_filename,
        "keyring_data": str(keyring_data),
    }

    maas = _create_maas_client()
    if url in get_boot_source():
        result['result'] = None
        result["comment"] = "boot resource already exist"
        return result

    # NOTE: maas.post will return 400, if url already defined.
    json_res = json.loads(
        maas.post(u'api/2.0/boot-sources/', None, **data).read())
    if wait:
        LOG.debug(
            "Sleep for 5s,to get MaaS some time to process previous request")
        time.sleep(5)
        ret = boot_resources_is_importing(wait=True)
        if ret is dict:
            return ret
    LOG.debug("create_boot_source:{}".format(json_res))
    result["new"] = "boot resource {0} was created".format(json_res["url"])

    return result


def boot_resources_import(action='import', wait=False):
    """
    import/stop_import the boot resources.

    :param action:  import\stop_import
    :param wait:    True\False. Wait till process finished.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.boot_resources_import action='import'

    """
    maas = _create_maas_client()
    # Have no idea why, but usual jsonloads not work here..
    imp = maas.post(u'api/2.0/boot-resources/', action)
    if imp.code == 200:
        LOG.debug('boot_resources_import:{}'.format(imp.readline()))
        if wait:
            boot_resources_is_importing(wait=True)
        return True
    else:
        return False


def boot_resources_is_importing(wait=False):
    maas = _create_maas_client()
    result = {}
    if wait:
        started_at = time.time()
        poll_time = 5
        timeout = 60 * 15
        while boot_resources_is_importing(wait=False):
            c_timeout = timeout - (time.time() - started_at)
            if c_timeout <= 0:
                result['result'] = False
                result["comment"] = "Boot-resources import not finished in time"
                return result
            LOG.info(
                "Waiting boot-resources import done\n"
                "sleep for:{}s "
                "Left:{}/{}s".format(poll_time, round(c_timeout), timeout))
            time.sleep(poll_time)
        return json.loads(
            maas.get(u'api/2.0/boot-resources/', 'is_importing').read())
    else:
        return json.loads(
            maas.get(u'api/2.0/boot-resources/', 'is_importing').read())

#####
# def boot_sources_selections_delete_all_others(except_urls=[]):
#    """
#    """
#    result = {}
#    return result


def is_boot_source_selections_in(dict1, list1):
    """
    Check that requested boot-selection already in maas bs selections,
    if True- return bss id.
    # FIXME: those hack check doesn't look good.
    """
    for bs in list1:
        same = set(dict1.keys()) & set(bs.keys())
        if all(elem in same for elem in
               ['os', 'release', 'arches', 'subarches', 'labels']):
            LOG.debug("boot-selection in maas:{0}\n"
                      "looks same to requested:{1}".format(bs, dict1))
            return bs['id']
    return False


def get_boot_source_selections(bs_url):
    """
    Get boot-source selections.
    """
    # check for key_error!
    bs_id = _get_boot_source_id_by_url(bs_url)
    maas = _create_maas_client()
    json_res = json.loads(
        maas.get(u'/api/2.0/boot-sources/{0}/selections/'.format(bs_id)).read())
    LOG.debug(
        "get_boot_source_selections for url:{} \n{}".format(bs_url, json_res))
    return json_res


def create_boot_source_selections(bs_url, os, release, arches="*",
                                  subarches="*", labels="*", wait=True):
    """
         Create a new boot source selection for bs_url.
        :param os:        The OS (e.g. ubuntu, centos) for which to import resources.Required.
        :param release:   The release for which to import resources. Required.
        :param arches:    The architecture list for which to import resources.
        :param subarches: The subarchitecture list for which to import resources.
        :param labels:    The label lists for which to import resources.
    """

    result = {"result": True, 'name': bs_url, 'changes': None}

    data = {
        "os": os,
        "release": release,
        "arches": arches,
        "subarches": subarches,
        "labels": labels,
    }

    maas = _create_maas_client()
    bs_id = _get_boot_source_id_by_url(bs_url)
    # TODO add pre-create verify
    maas_bs_s = get_boot_source_selections(bs_url)
    if is_boot_source_selections_in(data, maas_bs_s):
        result["result"] = True
        result["comment"] = 'Requested boot-source selection ' \
                            'for {0} already exist.'.format(
            bs_url)
        return result

    # NOTE: maas.post will return 400, if url already defined.
    # Also, maas need's some time to import info about stream.
    # unfortunatly, maas don't have any call to check stream-import-info - so, we need to implement
    # at least simple retry ;(
    json_res = False
    poll_time = 5
    for i in range(0, 5):
        try:
            json_res = json.loads(
                maas.post(u'api/2.0/boot-sources/{0}/selections/'.format(bs_id), None,
                          **data).read())
        except Exception as inst:
            m = inst.readlines()
            LOG.warning("boot_source_selections "
                        "catch error during processing. Most-probably, "
                        "streams not imported yet.\nSleep:{}s"
                        "Retry:{}/5".format(poll_time, i))
            LOG.warning("Message:{0}".format(m))
            time.sleep(poll_time)
            continue
        break
    LOG.debug("create_boot_source_selections:{}".format(json_res))
    if not json_res:
        result["result"] = False
        result["comment"] = 'Failed to create requested boot-source selection' \
                            ' for {0}.'.format(bs_url)
        return result
    if wait:
        LOG.debug(
            "Sleep for 5s,to get MaaS some time to process previous request")
        time.sleep(5)
        ret = boot_resources_import(action='import', wait=True)
        if ret is dict:
            return ret
    result["comment"] = "boot-source selection for {0} was created".format(
        bs_url)
    result["new"] = data

    return result

# END MAAS CONFIG SECTION

# RACK CONTROLLERS SECTION


def get_rack(hostname):
    """
    Get information about specified rackd

    CLI Example:

    .. code-block:: bash

        salt-call maasng.get_rack rack_hostname
    """
    try:
        return list_racks()[hostname]
    except KeyError:
        return {"error": "rack:{} not found on MaaS server".format(hostname)}


def list_racks(sort_by='hostname'):
    """
    Get list of all rack controllers from maas server

    CLI Example:

    .. code-block:: bash

        salt-call maasng.list_racks
    """
    racks = {}
    maas = _create_maas_client()
    json_res = json.loads(
        maas.get(u"/api/2.0/rackcontrollers/").read() or 'null')
    for item in json_res:
        racks[item[sort_by]] = item
    return racks


def sync_bs_to_rack(hostname=None):
    """
    Sync RACK boot-sources with REGION. If no hostname probided  - sync to all.

    CLI Example:

    .. code-block:: bash

        salt-call maasng.sync_bs_to_rack rack_hostname
    """
    ret = {}
    maas = _create_maas_client()
    if not hostname:
        LOG.info("boot-sources sync initiated for ALL Rack's")
        # Convert to json-like format
        json_res = json.loads('["{0}"]'.format(
            maas.post(u"/api/2.0/rackcontrollers/",
                      'import_boot_images').read()))
        LOG.debug("sync_bs_to_rack:{}".format(json_res))
        ret['result'] = True
        ret['comment'] = "boot-sources sync initiated for ALL Rack's"
        return ret
    LOG.info("boot-sources sync initiated for RACK:{0}".format(hostname))
    # Convert to json-like format
    json_res = json.loads('["{0}"]'.format(maas.post(
        u"/api/2.0/rackcontrollers/{0}/".format(
            get_rack(hostname)['system_id']),
        'import_boot_images').read()))
    LOG.debug("sync_bs_to_rack:{}".format(json_res))
    ret['result'] = True
    ret['comment'] = "boot-sources sync initiated for {0} Rack's".format(
        hostname)
    return


def rack_list_boot_imgs(hostname):
    ret = {}
    maas = _create_maas_client()
    LOG.debug("rack_list_boot_imgs:{}".format(hostname))
    ret = json.loads(maas.get(u"/api/2.0/rackcontrollers/{0}/".format(
        get_rack(hostname)['system_id']), 'list_boot_images').read() or 'null')
    return ret


def is_rack_synced(hostname):
    rez = rack_list_boot_imgs(hostname)['status']
    if rez == 'synced':
        return True
    return False

# TODO do we actually need _exact_ check per-pack?
# def wait_for_images_on_rack(hostname):
#
#    """
#    WA function, to be able check that RACK actually done SYNC images
#    for REQUIRED images at least.
#    Required image to be fetched from
#    reclass:maas:region:boot_sources_selections:[keys]:os/release formation
#
#    CLI Example:
#
#    .. code-block:: bash
#
#        salt-call maasng.wait_for_sync_bs_to_rack rack_hostname
#    """
#    try:
#        bss = __salt__['config.get']('maas')['region']['boot_sources_selections']
#    except KeyError:
#        ret['result'] = None
#        ret['comment'] = "boot_sources_selections definition for sync not found."
#        return ret
#    s_names = []
#    # Format  u'name': u'ubuntu/xenial'
#    for v in bss.values():s_names.append("{0}/{1}".format(v['os'],v['release']))
#    # Each names, should be in rack and whole rack should be in  sync-ed state


def sync_and_wait_bs_to_all_racks():
    """
    Sync ALL rack's with regions source images.

    CLI Example:

    .. code-block:: bash

        salt-call maasng.sync_and_wait_bs_to_all_racks
    """
    sync_bs_to_rack()
    for rack in list_racks().keys():
        wait_for_sync_bs_to_rack(hostname=rack)
    return True


def wait_for_sync_bs_to_rack(hostname=None):
    """
    Wait for boot images sync finished, on exact rack

    CLI Example:

    .. code-block:: bash

        salt-call maasng.wait_for_sync_bs_to_rack rack_hostname
    """
    ret = {}
    started_at = time.time()
    poll_time = 5
    timeout = 60 * 15
    while not is_rack_synced(hostname):
        c_timeout = timeout - (time.time() - started_at)
        if c_timeout <= 0:
            ret['result'] = False
            ret[
                "comment"] = "Boot-resources sync on rackd:{0}" \
                             "not finished in time".format(
                hostname)
            return ret
        LOG.info(
            "Waiting boot-resources sync done to rack:{0}\n"
            "sleep for:{1}s "
            "Left:{2}/{3}s".format(hostname, poll_time, round(c_timeout),
                                   timeout))
        time.sleep(poll_time)
    ret['result'] = is_rack_synced(hostname)
    ret["comment"] = "Boot-resources sync on rackd:{0} finished".format(
        hostname)
    return ret

# END RACK CONTROLLERS SECTION
# SSHKEYS


def list_sshkeys():
    """
    Get list of all sshkeys

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.list_sshkeys
        salt-call maasng.list_sshkeys
    """
    ssh = {}
    maas = _create_maas_client()
    json_res = json.loads(maas.get(u'api/2.0/account/prefs/sshkeys/').read())
    LOG.info(json_res)
    for item in json_res:
        ssh[item["key"]] = item
    return ssh


def add_sshkey(sshkey):
    """
    Add SSH key for user to MAAS.

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.add_sshkey sshkey
        salt-call maasng.add_sshkey sshkey
    """
    data = {
        "key": sshkey,
    }
    result = {}
    maas = _create_maas_client()

    maas.post(u"/api/2.0/account/prefs/sshkeys/", None, **data).read()
    result["new"] = "SSH Key {0} was added.".format(sshkey)

    return result


def get_sshkey(sshkey):
    """
    Get start ip for ip range

    CLI Example:

    .. code-block:: bash

        salt 'maas-node' maasng.get_sshkey sshkey
        salt-call maasng.get_sshkey sshkey
    """
    try:
        return list_sshkeys()[sshkey]
    except KeyError:
        return {"error": "SSH key not found on MaaS server"}
# END SSHKEYS
