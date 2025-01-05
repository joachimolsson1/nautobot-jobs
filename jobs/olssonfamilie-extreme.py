from nautobot.jobs import Job, register_jobs
import requests
from nautobot.extras.jobs import Job
from nautobot.dcim.models import Device, DeviceRole, DeviceType, Site, Interface, Location
from nautobot.ipam.models import IPAddress
from nautobot.extras.models import Status

class FetchAndAddExtremeCloudIQDevices(Job):
    class Meta:
        name = "Fetch and Add Devices from ExtremeCloud IQ"
        description = "Fetches devices from ExtremeCloud IQ and adds them to Nautobot."

    api_token = StringVar(
        description="API Token for ExtremeCloud IQ",
    )

    def run(self, data, commit):
        api_token = data["api_token"]
        base_url = 'https://api.extremecloudiq.com'
        headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        }

        url = f'{base_url}/devices'
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            devices = response.json()
            for device in devices:
                self.log_info(message=f"Fetched Device: {device}")

                # Example of adding a device to Nautobot
                # Adjust the fields according to your device data and Nautobot setup
                device_name = device.get('name')
                device_serial = device.get('serial')
                device_model = device.get('model')
                device_ip = device.get('ip_address')  # Adjust according to actual field name
                device_role_name = 'default-role'  # Replace with actual role name
                site_name = 'default-site'  # Replace with actual site name
                location_hierarchy = ['Region', 'Building', 'Campus']  # Example hierarchy

                # Fetch or create the necessary related objects
                device_role, _ = DeviceRole.objects.get_or_create(name=device_role_name)
                device_type, _ = DeviceType.objects.get_or_create(model=device_model)
                site, _ = Site.objects.get_or_create(name=site_name)
                status = Status.objects.get(name='Active')  # Adjust status as needed

                # Create or fetch location hierarchy
                parent_location = None
                for location_name in location_hierarchy:
                    location, _ = Location.objects.get_or_create(
                        name=location_name,
                        parent=parent_location,
                        site=site
                    )
                    parent_location = location

                # Check for existing device
                existing_device = Device.objects.filter(serial=device_serial).first()
                if existing_device:
                    # Update existing device
                    existing_device.name = device_name
                    existing_device.device_role = device_role
                    existing_device.device_type = device_type
                    existing_device.site = site
                    existing_device.status = status
                    existing_device.location = parent_location  # Set the last location as campus
                    existing_device.save()
                    self.log_success(message=f"Updated Device in Nautobot: {device_name}")
                else:
                    # Create new device
                    nautobot_device = Device(
                        name=device_name,
                        serial=device_serial,
                        device_role=device_role,
                        device_type=device_type,
                        site=site,
                        status=status,
                        location=parent_location  # Set the last location as campus
                    )
                    nautobot_device.save()
                    self.log_success(message=f"Added Device to Nautobot: {device_name}")

                # Add IP address and associate with management interface
                if device_ip:
                    ip_address, _ = IPAddress.objects.get_or_create(address=device_ip)
                    management_interface, created = Interface.objects.get_or_create(
                        device=nautobot_device,
                        name='mgmt0',  # Adjust interface name as needed
                        defaults={'type': 'virtual'}  # Adjust interface type as needed
                    )
                    if not created:
                        self.log_info(message=f"Management interface already exists for {device_name}")
                    management_interface.ip_addresses.add(ip_address)
                    management_interface.save()
                    self.log_success(message=f"Assigned IP {device_ip} to {device_name} management interface")
        else:
            self.log_error(message=f"Error: {response.status_code}")

        return "Job completed successfully!"

# Register the job
register_jobs(FetchAndAddExtremeCloudIQDevices)