{%- from "maas/map.jinja" import region with context %}

maas_login_admin:
  cmd.run:
  - name: "maas-region apikey --username {{ region.admin.username }} > /var/lib/maas/.maas_credentials"

wait_for_machines_ready_or_deployed:
  module.run:
  - name: maas.wait_for_machine_status
  - kwargs:
        req_status: "Ready|Deployed"
        timeout: {{ region.timeout.ready }}
        attempts: {{ region.timeout.attempts }}
  - require:
    - cmd: maas_login_admin
