import requests
import json

from nautobot.apps.jobs import JobHookReceiver, register_jobs
from nautobot.extras.choices import ObjectChangeActionChoices

class CreateTraefikConfig(JobHookReceiver):
    class Meta:
        name = "Create Traefik Conf"
        description = "When new Firewall or Panorama is created. Generate config and push to loopback."

    def receive_job_hook(self, change, action, changed_object):
        #Not used at the moment. To check if we can clean up config if we delete devices.
        if action == ObjectChangeActionChoices.ACTION_DELETE:
            return
        #If loopback URL is updated on the device. For example if customers have multiple proxies. This part cleanup the old config and upload
        #new one.
        if action == ObjectChangeActionChoices.ACTION_UPDATE:
            snapshots = change.get_snapshots()
            if snapshots['differences']['added']['loopback_url'] == snapshots['differences']['removed']['loopback_url']:
                self.logger.info("Loopback url have not been changed. No further changes applied to this automation.")

            else:
                #Cleanup config from old loopback.
                data_delete = {
                    'loopbackhostname': f'{snapshots['differences']['removed']['loopback_url']}',
                    'fehostname': f'{changed_object.id}.{snapshots['differences']['removed']['loopback_url']}'
                }
                json_data_delete = json.dumps(data_delete)
                url_delete = f"https://10.70.0.23:5500/trafik-delete-config/?apikey={API_KEY}"
                response = requests.post(url_delete, headers={'Content-Type': 'application/json'}, data=json_data_delete)
                if response.status_code == 200:
                    self.logger.info(f"Traefik configuration was deleted successfully.")
                else:
                    self.logger.info(f"Request failed with status code: {response.status_code}")
                    self.logger.error(response.text)
                #Add config to new loopback.
                data_new = {
                    'loopbackhostname': f'{snapshots['differences']['added']['loopback_url']}',
                    'routename': f'{changed_object.id}',
                    'fehostname': f'{changed_object.id}.{snapshots['differences']['added']['loopback_url']}',
                    'servicename': f'{changed_object.id}',
                    'behostname': f'{changed_object.custom_field_data["backend_ip"]}'
                }
                json_data_new = json.dumps(data_new)
                url_new = f"https://10.70.0.23:5500/trafik-upload-config/?apikey={API_KEY}"
                response = requests.post(url_new, headers={'Content-Type': 'application/json'}, data=json_data_new)
                if response.status_code == 200:
                    self.logger.info(f"Traefik configuration was uploaded successfully.")
                else:
                    self.logger.info(f"Request failed with status code: {response.status_code}")
                    self.logger.error(response.text)
                
            return
        #New device created with loopback URL defined.
        if action == ObjectChangeActionChoices.ACTION_CREATE:
            # check if custom field "Loopback URL" exists and is not empty.
            loopback_custom_url = changed_object.custom_field_data["loopback_url"]
            if  loopback_custom_url:
                snapshots = change.get_snapshots()
                self.logger.info("Host created: %s", changed_object)
                self.logger.info("Host details: %s", snapshots['differences']['added'])
                data = {
                    'loopbackhostname': f'{loopback_custom_url}',
                    'routename': f'{changed_object.id}',
                    'fehostname': f'{changed_object.id}.{loopback_custom_url}',
                    'servicename': f'{changed_object.id}',
                    'behostname': f'{changed_object.custom_field_data["backend_ip"]}'
                }
                json_data = json.dumps(data)
                url = f"https://10.70.0.23:5500/trafik-upload-config/?apikey={API_KEY}"
                response = requests.post(url, headers={'Content-Type': 'application/json'}, data=json_data)
                if response.status_code == 200:
                    self.logger.info(f"Traefik configuration was added successfully.")
                else:
                    self.logger.info(f"Request failed with status code: {response.status_code}")
                    self.logger.error(response.text)

                
            else:
                self.logger.info("Custom field 'Loopback URL' does not exist or is not set.")
            return
    # Register the job
register_jobs(CreateTraefikConfig)