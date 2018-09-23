=====
Usage
=====

Metal as a Service

Sample pillars
==============

Single maas service:

.. code-block:: yaml

    maas:
      server:
        enabled: true

Single MAAS region service [single UI/API]:

.. code-block:: yaml

  maas:
    salt_master_ip: 192.168.0.10
    region:
      upstream_proxy:
        address: 10.0.0.1
        port: 8080
        user: username      #OPTIONAL
        password: password  #OPTIONAL
      theme: mirantis
      bind:
        host: 192.168.0.10:5240
        port: 5240
      admin:
        username: exampleuser
        password: examplepassword
        email:  email@example.com
      database:
        engine: null
        host: localhost
        name: maasdb
        password: qwqwqw
        username: maas
      enabled: true
      user: mirantis
      token: "89EgtWkX45ddjMYpuL:SqVjxFG87Dr6kVf4Wp:5WLfbUgmm9XQtJxm3V2LUUy7bpCmqmnk"
      fabrics:
        fabric1:
          name: 'tf2'
          description: "Test fabric"
        fabric2:
          name: 'tf2'
          description: "Test fabric2"
        deploy_network:
          name: 'deploy_network'
          description: Fabric for deploy_network
          vlans:
            0:
              name: 'vlan 0'
              description: Deploy VLAN
              mtu: 1500
              dhcp: true
              # FIXME: after refactoring domain module, it should be
              # fixed exactly for FQDN, not only 'hostname'
              primary_rack: "${linux:network:hostname}"

      subnets:
        subnet1:
          fabric: ${maas:region:fabrics:deploy_network:name}
          cidr: 2.2.3.0/24
          gateway_ip: 2.2.3.2
          vlan: 150
          ipranges:
            1:
              end: "2.2.3.40"
              start: "2.2.3.20"
              type: dynamic
            2:
              end: "2.2.3.250"
              start: "2.2.3.45"
              type: reserved
      dhcp_snippets:
        test-snippet:
          value: option bootfile-name "tftp://192.168.0.10/snippet";
          description: Test snippet
          enabled: true
          subnet: subnet1
      boot_sources_delete_all_others: true
      boot_sources:
        resources_mirror:
          url: http://images.maas.io/ephemeral-v3/
          keyring_file: /usr/share/keyrings/ubuntu-cloudimage-keyring.gpg
      boot_sources_selections:
        xenial:
          url: "http://images.maas.io/ephemeral-v3/" # should be same in boot_sources, or other already defined.
          os: "ubuntu"
          release: "xenial"
          arches: "amd64"
          subarches: '"*"'
          labels: '"*"'
      package_repositories:
        Saltstack:
          url: http://repo.saltstack.com/apt/ubuntu/14.04/amd64/2016.3/
          distributions:
               - trusty
          components:
              - main
          arches: amd64
          key: "-----BEGIN PGP PUBLIC KEY BLOCK-----
               Version: GnuPG v2

               mQENBFOpvpgBCADkP656H41i8fpplEEB8IeLhugyC2rTEwwSclb8tQNYtUiGdna9
                ......
               fuBmScum8uQTrEF5+Um5zkwC7EXTdH1co/+/V/fpOtxIg4XO4kcugZefVm5ERfVS
               MA==
               =dtMN
               -----END PGP PUBLIC KEY BLOCK-----"
          enabled: true
      machines:
        machine1_new_schema:
          pxe_interface_mac: "11:22:33:44:55:66" # Node will be identified by those mac
          interfaces:
            nic01: # could be any, used for iterate only
              type: eth # NotImplemented
              name: eth0 # Override default nic name. Interface to rename will be identified by mac
              mac: "11:22:33:44:55:66"
              mode: "static"
              ip: "2.2.3.19"  # ip should be out of reserved subnet range, but still in subnet range
              subnet: "subnet1"
              gateway: "2.2.3.2" # override default gateway from subnet
            nic02:
              type: eth # Not-implemented
              mac: "11:22:33:44:55:78"
              subnet: "subnet2"
              mode: "dhcp"
          power_parameters:
            power_type: ipmi
            power_address: '192.168.10.10'
            power_user: bmc_user
            # power_password: bmc_password  # Old format,please use new one
            power_pass: bmc_password
            #Optional (for legacy HW)
            power_driver: LAN
          distro_series: xenial
          hwe_kernel: hwe-16.04
        machine1_old_schema:
          interface:
              mac: "11:22:33:44:55:88"  # Node will be identified by those mac
              mode: "static"
              ip: "2.2.3.15"
              subnet: "subnet1"
              gateway: "2.2.3.2"
          power_parameters:
            power_type: ipmi
            power_address: '192.168.10.10'
            power_user: bmc_user
            # power_password: bmc_password  # Old format,please use new one
            power_pass: bmc_password
            #Optional (for legacy HW)
            power_driver: LAN
          distro_series: xenial
          hwe_kernel: hwe-16.04
        virsh_example:
          pxe_interface_mac: "52:54:00:00:01:01"
          interfaces:
            nic01:
              type: eth
              name: eth0
              mac: "52:54:00:00:01:01"
              subnet: "${maas:region:subnets:deploy_network:name}"
              mode: "dhcp"
          power_parameters:
            power_type: virsh
            power_address: "qemu+tcp://my-kvm-node-hostname/system"
            power_id: "kvm01-pxe01"
      devices:
        machine1-ipmi:
          interface:
            ip_address: 192.168.10.10
            subnet: cidr:192.168.10.0/24
          mac: '66:55:44:33:22:11'
      commissioning_scripts:
        00-maas-05-simplify-network-interfaces: /etc/maas/files/commisioning_scripts/00-maas-05-simplify-network-interfaces
      maas_config:
        # domain: mydomain.local # This function broken
        http_proxy: http://192.168.0.10:3142
        commissioning_distro_series: xenial
        default_distro_series: xenial
        default_osystem: 'ubuntu'
        default_storage_layout: lvm
        disk_erase_with_secure_erase: true
        dnssec_validation: 'no'
        enable_third_party_drivers: true
        maas_name: cfg01
        network_discovery: 'enabled'
        active_discovery_interval: '600'
        ntp_external_only: true
        ntp_servers: 10.10.11.23 10.10.11.24
        upstream_dns: 192.168.12.13
        enable_http_proxy: true
        default_min_hwe_kernel: ''
       sshprefs:
        - 'ssh-rsa ASD.........dfsadf blah@blah'

Update VLAN:

.. note:: Vid 0 has default name untagged in the MaaS UI.

.. code-block:: yaml

  maas:
    region:
      fabrics:
        test-fabric:
          description: "Test fabric"
          vlan:
            0:
              description: "Your VLAN 0"
              dhcp: True
            13:
              description: "Your VLAN 13"
              dhcp: False

Create disk schema per machine via ``maas/client.sls`` with
default lvm schema + default values.

.. note:: This should be used mostly for custom root
          partitioning and RAID configuration. For
          not-root partitions, use ``salt-formula-linux``.

.. code-block:: yaml

  maas:
    region:
      machines:
        server1:
          disk_layout:
            type: lvm
            root_size: 20G
            root_device: vda
            volume_group: vg1
            volume_name: root
            volume_size: 8
            bootable_device: vda

FLAT layout with custom root size:

.. code-block:: yaml

  maas:
    region:
      machines:
        server2:
          disk_layout:
            type: flat
            root_size: 20
            physical_device: vda
            bootable_device: vda

Size specification with ``%`` char used is not yet supported.

.. code-block:: yaml

  maas:
    region:
      machines:
        server3:
          disk_layout:
            type: flat
            bootable_device: sda
            disk:
              sda:
                type: physical
                partition_schema:
                  part1:
                    size: 100%
                    type: ext4
                    mount: '/'

Define more complex layout:

.. code-block:: yaml

  maas:
    region:
      machines:
        server3:
          disk_layout:
            type: custom
            bootable_device: vda
            disk:
              vda:
                type: physical
                partition_schema:
                  part1:
                    size: 10G
                    type: ext4
                    mount: '/'
                  part2:
                    size: 2G
                  part3:
                    size: 3G
              vdc:
                type: physical
                partition_schema:
                  part1:
                    size: 100G
              vdd:
                type: physical
                partition_schema:
                  part1:
                    size: 100G
              raid0:
                type: raid
                level: 10
                devices:
                  - vde
                  - vdf
                partition_schema:
                  part1:
                    size: 10G
                  part2:
                    size: 2G
                  part3:
                    size: 3G
              raid1:
                type: raid
                level: 1
                partitions:
                  - vdc-part1
                  - vdd-part1
              volume_group2:
                type: lvm
                devices:
                  - raid1
                volume:
                  tmp:
                    size: 5G
                    type: ext4
                    mount: '/tmp'
                  log:
                    size: 7G
                    type: ext4
                    mount: '/var/log'

Raid setup, 4x HDD:

.. code-block:: yaml

  maas:
    region:
      machines:
        serverWithRaidExample:
          disk_layout:
            type: custom
            bootable_device: sda
            disk:
              md0:
                type: raid
                level: 1
                devices:
                  - sda
                  - sdb
                partition_schema:
                  part1:
                    size: 230G
                    type: ext4
                    mount: /
              md1:
                type: raid
                level: 1
                devices:
                  - sdc
                  - sdd
                partition_schema:
                  part1:
                    size: 1890G
                    type: ext4
                    mount: /var/lib/libvirt

Raid + LVM setup, 2xSSD + 2xHDD:

.. note:: This setup lacks the ability run state twice,
          as of now when ``disk_partition_present`` is called,
          it tries blindly to delete the partition and then
          recreated. That fails as MAAS rejects remove
          partition used in RAID/LVM.

.. code-block:: yaml

  maas:
    region:
      machines:
        serverWithRaidExample2:
          disk_layout:
            type: custom
            #bootable_device: vgssd-root
            disk:
              sda: &maas_disk_physical_ssd
                type: physical
                partition_schema:
                  part1:
                    size: 239G
              sdb: *maas_disk_physical_ssd
              sdc: &maas_disk_physical_hdd
                type: physical
                partition_schema:
                  part1:
                    size: 1990G
              sdd: *maas_disk_physical_hdd
              md0:
                type: raid
                level: 1
                partitions:
                  - sda-part1
                  - sdb-part1
              md1:
                type: raid
                level: 1
                partitions:
                  - sdc-part1
                  - sdd-part1
              vgssd:
                type: lvm
                devices:
                  - md0
                volume:
                  root:
                    size: 230G
                    type: ext4
                    mount: '/'
              vghdd:
                type: lvm
                devices:
                  - md1
                volume:
                  libvirt:
                    size: 1800G
                    type: ext4
                    mount: '/var/lib/libvirt'


LVM setup using partition


.. code-block:: yaml


  maas:
    region:
      machines:
        serverWithLvmExample3:
          disk_layout:
            type: custom
            bootable_device: sda
            disk:
              sda:
                type: physical
                partition_schema:
                  part1:
                    size: 50G
                  part2:
                    mount: /var/lib/libvirt/images/
                    size: 10G
                    type: ext4
              vg0:
                partitions:
                  - sda-part1
                type: lvm
                volume:
                  root:
                    mount: /
                    size: 40G
                    type: ext4


Setup image mirror (Maas boot resources):

.. code-block:: yaml

  maas:
    mirror:
      enabled: true
      image:
        sections:
          bootloaders:
            keyring: /usr/share/keyrings/ubuntu-cloudimage-keyring.gpg
            upstream: http://images.maas.io/ephemeral-v3/daily/
            local_dir: /var/www/html/maas/images/ephemeral-v3/daily
            count: 1
            # i386 need for pxe
            filters: ['arch~(i386|amd64)', 'os~(grub*|pxelinux)']
          xenial:
            keyring: /usr/share/keyrings/ubuntu-cloudimage-keyring.gpg
            upstream: http://images.maas.io/ephemeral-v3/daily/
            local_dir: /var/www/html/maas/images/ephemeral-v3/daily
            count: 1
            filters: ['release~(xenial)', 'arch~(amd64)', 'subarch~(generic|hwe-16.04$|ga-16.04)']
          count: 1

Usage of local deb repos

.. code-block:: yaml

  maas:
    cluster:
      enabled: true
      region:
        port: 80
        host: localhost
      saltstack_repo_key: |
        -----BEGIN PGP PUBLIC KEY BLOCK-----
        Version: GnuPG v2

        mQENBFOpvpgBCADkP656H41i8fpplEEB8IeLhugyC2rTEwwSclb8tQNYtUiGdna9
        .....
        fuBmScum8uQTrEF5+Um5zkwC7EXTdH1co/+/V/fpOtxIg4XO4kcugZefVm5ERfVS
        MA==
        =dtMN
        -----END PGP PUBLIC KEY BLOCK-----
      saltstack_repo_xenial: "deb [arch=amd64] http://${_param:local_repo_url}/ubuntu-xenial stable salt"
      saltstack_repo_trusty: "deb [arch=amd64] http://${_param:local_repo_url}/ubuntu-trusty stable salt"

Single MAAS cluster service [multiple racks]

.. code-block:: yaml

    maas:
      cluster:
        enabled: true
        role: master/slave

.. code-block:: yaml

    maas:
      cluster:
        enabled: true
        role: master/slave

MAAS region service with backup data:

.. code-block:: yaml

    maas:
      region:
        database:
          initial_data:
            source: cfg01.local
            host: 192.168.0.11

MAAS service power_parameters defintion with OpenStack Nova power_type:

.. code-block:: yaml

    maas:
      region:
        machines:
          cmp1:
            power_type: nova
            power_parameters: # old style, deprecated
              power_nova_id: hostuuid
              power_os_tenantname: tenant
              power_os_username: user
              power_os_password: password
              power_os_authurl: http://url


.. code-block:: yaml

    maas:
      region:
        machines:
          cmp1:
            power_type: nova
            power_parameters: # new style
              nova_id: hostuuid
              os_tenantname: tenant
              os_username: user
              os_password: password
              os_authurl: http://url

Test pillars
==============

Mind the PostgreSQL and rsyslog ``.sls``. Database and
syslog service are required for MAAS to properly install
and work.

* https://github.com/salt-formulas/salt-formula-rsyslog/tree/master/tests/pillar


Module function's example:
==========================

Wait for status of selected machine's:

.. code-block:: bash

    > cat maas/machines/wait_for_machines_ready.sls

    ...

    wait_for_machines_ready:
      module.run:
      - name: maas.wait_for_machine_status
      - kwargs:
            machines:
              - kvm01
              - kvm02
            timeout: {{ region.timeout.ready }}
            attempts: {{ region.timeout.attempts }}
            req_status: "Ready"
      - require:
        - cmd: maas_login_admin
      ...

The timeout setting is taken from the reclass pillar data.
If the pillar data is not defined, it will use the default value.

If module run w/\o any extra paremeters,
``wait_for_machines_ready`` will wait for defined in salt
machines. In this case, it is usefull to skip some machines:

.. code-block:: bash

    > cat maas/machines/wait_for_machines_deployed.sls

    ...

    wait_for_machines_ready:
      module.run:
      - name: maas.wait_for_machine_status
      - kwargs:
            timeout: {{ region.timeout.deployed }}
            attempts: {{ region.timeout.attempts }}
            req_status: "Deployed"
            ignore_machines:
               - kvm01 # in case it's broken or whatever
      - require:
        - cmd: maas_login_admin
      ...

List of available ``req_status`` defined in global variable:

.. code-block:: python

    STATUS_NAME_DICT = dict([
        (0, 'New'), (1, 'Commissioning'), (2, 'Failed commissioning'),
        (3, 'Missing'), (4, 'Ready'), (5, 'Reserved'), (10, 'Allocated'),
        (9, 'Deploying'), (6, 'Deployed'), (7, 'Retired'), (8, 'Broken'),
        (11, 'Failed deployment'), (12, 'Releasing'),
        (13, 'Releasing failed'), (14, 'Disk erasing'),
        (15, 'Failed disk erasing')])

Read more
=========

* https://maas.io/

Documentation and Bugs
======================

* http://salt-formulas.readthedocs.io/
   Learn how to install and update salt-formulas

* https://github.com/salt-formulas/salt-formula-maas/issues
   In the unfortunate event that bugs are discovered, report the issue to the
   appropriate issue tracker. Use the Github issue tracker for a specific salt
   formula

* https://launchpad.net/salt-formulas
   For feature requests, bug reports, or blueprints affecting the entire
   ecosystem, use the Launchpad salt-formulas project

* https://launchpad.net/~salt-formulas-users
   Join the salt-formulas-users team and subscribe to mailing list if required

* https://github.com/salt-formulas/salt-formula-maas
   Develop the salt-formulas projects in the master branch and then submit pull
   requests against a specific formula

* #salt-formulas @ irc.freenode.net
   Use this IRC channel in case of any questions or feedback which is always
   welcome

