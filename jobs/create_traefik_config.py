import requests
import json

from nautobot.dcim.models import Device
from nautobot.apps.jobs import JobHookReceiver, register_jobs
from nautobot.extras.choices import ObjectChangeActionChoices

class CreateTraefikConfig(JobHookReceiver):
    class Meta:
        name = "Create Traefik Conf"
        description = "When new Firewall or Panorama is created. Generate config and push to loopback."

    def receive_job_hook(self, change, action, changed_object):
        if action == ObjectChangeActionChoices.ACTION_DELETE:
            return
        
        if action == ObjectChangeActionChoices.ACTION_UPDATE:
            snapshots = change.get_snapshots()
            self.logger.info("DIFF: %s", snapshots['differences'])
            return

        # log diff output
        snapshots = change.get_snapshots()
        self.logger.info("DIFF: %s", snapshots['differences'])

        # log info about host creation
        if action == ObjectChangeActionChoices.ACTION_CREATE:
            self.logger.info("Host created: %s", changed_object)
            self.logger.info("Host details: %s", snapshots['differences']['added'])

            # check if custom field "Services" exists and is set to "Firewall as a Service"
            loopback_custom_url = changed_object.custom_field_data["loopback_url"]
            if  loopback_custom_url:
                data = {
                    'loopbackhostname': f'{loopback_custom_url}',
                    'routename': f'{changed_object.id}',
                    'fehostname': f'{changed_object.id}.{loopback_custom_url}',
                    'servicename': f'{changed_object.id}',
                    'behostname': f'{changed_object.custom_field_data["backend_ip"]}'
                }

                # Convert the data to JSON format
                json_data = json.dumps(data)

                self.logger.info(f"{json_data}")
            else:
                self.logger.info("Custom field 'Services' does not exist or is not set to 'Firewall as a Service'.")
            return
    # Register the job
register_jobs(CreateTraefikConfig)