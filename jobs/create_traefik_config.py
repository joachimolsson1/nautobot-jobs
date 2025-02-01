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

        # log diff output
        snapshots = change.get_snapshots()
        self.logger.info("DIFF: %s", snapshots['differences'])

        # log info about host creation
        if action == ObjectChangeActionChoices.ACTION_CREATE:
            self.logger.info("Host created: %s", changed_object)
            self.logger.info("Host details: %s", snapshots['differences']['added'])

            # check if custom field "Services" exists and is set to "Firewall as a Service"
            custom_fields = changed_object.custom_field_data["Services"]
            self.logger.info("TESTING %s", custom_fields)
            if "Services" in custom_fields and custom_fields["Services"] == "Firewall as a Service":
                self.logger.info("Services: Firewall as a Service")
            else:
                self.logger.info("Custom field 'Services' does not exist or is not set to 'Firewall as a Service'.")


    def validate_serial(self, serial):
        # add business logic to validate serial
        return True
    # Register the job
register_jobs(CreateTraefikConfig)