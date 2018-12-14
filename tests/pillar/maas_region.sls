maas:
  cluster:
    enabled: true
    region:
      host: localhost
      port: 80
    role: master
    enable_iframe: True
    cluster:
      curtin_vars:
        amd64:
          xenial:
            extra_pkgs:
              enabled: true
              pkgs: [ "curl", "wget" ]
            kernel_package:
              enabled: true
              #value: 'linux-image-virtual-hwe-16.04'
              value: 'mc'
  region:
    enabled: true
    bind:
      host: localhost
      port: 80
    theme: theme
    admin:
      username: admin
      password: password
      email:  email@example.com
    database:
      engine: postgresql
      host: localhost
      name: maasdb
      password: password
      username: maas
    salt_master_ip: 127.0.0.1
    timeout:
      deployed: 900
      ready: 900
      attempts: 2
